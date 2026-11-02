"""The agent loop: Gemini with function calling, written by hand.

The SDK can run tools automatically, but the loop is short and keeping it
explicit makes every step visible: which tool was called, with which
arguments, and what came back. That is also what the CLI debug mode shows.
"""

import time
from dataclasses import dataclass, field

from google import genai
from google.genai import errors, types

from .data import load_store, now
from .prompt import build_system_prompt
from .tools import get_order, payment_options, search_products

MAX_TOOL_ROUNDS = 5
MAX_FAILED_ORDER_LOOKUPS = 3
RETRIES_PER_MODEL = 3
REQUEST_TIMEOUT_MS = 30_000
UNAVAILABLE_MESSAGE = (
    "Opa, estou com uma instabilidade aqui e não consegui responder agora. "
    "Pode tentar de novo em instantes? Se preferir, fale com a equipe pelo WhatsApp (67) 3341-4444."
)

TOOL_FUNCTIONS = {
    "search_products": search_products,
    "payment_options": payment_options,
    "get_order": get_order,
}


def _tool_declarations() -> list[types.FunctionDeclaration]:
    categories = [c.name for c in load_store().categories.values()]
    return [
        types.FunctionDeclaration(
            name="search_products",
            description=(
                "Busca instrumentos no catálogo da loja. Retorna preço original, promoção ativa, preço final, "
                "preço no PIX, disponibilidade e especificações. Use para qualquer pergunta sobre produto, "
                "preço, estoque ou promoção."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Marca, modelo ou característica (ex.: 'Takamine GD20', 'nylon', 'eletroacústico').",
                    },
                    "category": {"type": "string", "enum": categories},
                    "max_price": {"type": "number", "description": "Preço final máximo em reais."},
                    "min_price": {"type": "number", "description": "Preço final mínimo em reais."},
                    "only_available": {
                        "type": "boolean",
                        "description": "true para trazer só produtos disponíveis para compra.",
                    },
                },
            },
        ),
        types.FunctionDeclaration(
            name="payment_options",
            description=(
                "Calcula o total de uma compra em cada forma de pagamento (PIX, débito, boleto, crédito), "
                "as parcelas permitidas sem juros e o frete. Use quando o cliente perguntar sobre "
                "pagamento, parcelamento, valor no PIX ou frete."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "product_id": {"type": "integer"},
                                "quantity": {"type": "integer"},
                            },
                            "required": ["product_id"],
                        },
                    },
                    "city": {"type": "string", "description": "Cidade de entrega, se o cliente informou."},
                },
                "required": ["items"],
            },
        ),
        types.FunctionDeclaration(
            name="get_order",
            description=(
                "Consulta um pedido: status, itens, rastreio, previsão de entrega e prazos de troca, "
                "devolução e garantia. Exige o número do pedido e o e-mail do cliente."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "email": {"type": "string"},
                },
                "required": ["order_id", "email"],
            },
        ),
    ]


@dataclass
class ToolCall:
    name: str
    args: dict
    result: dict


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str | None = None
    error: str | None = None


class Agent:
    def __init__(self, api_key: str, model: str, fallback_model: str | None = None):
        self.client = genai.Client(api_key=api_key)
        self.models = [m for m in (model, fallback_model) if m]
        self.tools = [types.Tool(function_declarations=_tool_declarations())]
        self.history: list[types.Content] = []
        self.failed_order_lookups = 0

    def reset(self) -> None:
        self.history = []
        self.failed_order_lookups = 0

    def reply(self, message: str) -> Reply:
        turn_start = len(self.history)
        self.history.append(types.Content(role="user", parts=[types.Part.from_text(text=message)]))
        tool_calls: list[ToolCall] = []
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                response, model = self._generate()
                content = response.candidates[0].content
                # The model's content goes back as-is: Gemini needs its thought
                # signatures to keep reasoning across tool calls.
                self.history.append(content)
                if not response.function_calls:
                    return Reply(response.text or UNAVAILABLE_MESSAGE, tool_calls, model)
                parts = []
                for call in response.function_calls:
                    result = self._run_tool(call.name, dict(call.args or {}))
                    tool_calls.append(ToolCall(call.name, dict(call.args or {}), result))
                    parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(id=call.id, name=call.name, response=result)
                        )
                    )
                self.history.append(types.Content(role="user", parts=parts))
            error = f"Limite de {MAX_TOOL_ROUNDS} rodadas de ferramentas atingido"
        except (errors.APIError, IndexError, AttributeError) as exc:
            error = repr(exc)
        # Failed turn: drop it so the history never has dangling messages.
        del self.history[turn_start:]
        return Reply(UNAVAILABLE_MESSAGE, tool_calls, error=error)

    def _generate(self) -> tuple[types.GenerateContentResponse, str]:
        config = types.GenerateContentConfig(
            system_instruction=build_system_prompt(now()),
            tools=self.tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
        last_error: Exception | None = None
        for model in self.models:
            for attempt in range(RETRIES_PER_MODEL):
                try:
                    response = self.client.models.generate_content(
                        model=model, contents=self.history, config=config
                    )
                    return response, model
                except errors.APIError as error:
                    # 429 (rate limit) and 5xx (overloaded) are temporary; anything else is a bug.
                    if error.code != 429 and error.code < 500:
                        raise
                    last_error = error
                    if attempt < RETRIES_PER_MODEL - 1:
                        time.sleep(2**attempt)
        raise last_error

    def _run_tool(self, name: str, args: dict) -> dict:
        function = TOOL_FUNCTIONS.get(name)
        if function is None:
            return {"error": f"Ferramenta desconhecida: {name}"}
        # Enforced in code, not in the prompt, so a manipulated model still
        # cannot be used to guess order numbers and e-mails.
        if name == "get_order" and self.failed_order_lookups >= MAX_FAILED_ORDER_LOOKUPS:
            return {
                "found": False,
                "blocked": True,
                "message": (
                    "Limite de tentativas de consulta atingido nesta conversa. Não tente de novo: "
                    "oriente o cliente a falar com a equipe pelo WhatsApp ou e-mail."
                ),
            }
        try:
            result = function(**args)
        except (TypeError, ValueError, KeyError) as error:
            return {"error": f"Argumentos inválidos para {name}: {error}"}
        if name == "get_order" and not result["found"]:
            self.failed_order_lookups += 1
        return result
