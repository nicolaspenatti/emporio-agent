# Conversa 2: devolução por arrependimento

- **Cenário:** cliente quer devolver uma compra. O agente precisa verificar o pedido e aplicar a política de arrependimento.
- **Data e hora simuladas:** 30/10/2025 10:00 (`EMPORIO_NOW=2025-10-30T10:00`), 5 dias depois da entrega do pedido 1.
- **Modelo:** `gemini-flash-lite-latest` (reserva; o modelo principal estava sobrecarregado)
- **O que observar:** o agente não promete a devolução antes de verificar. Pede número e e-mail, e o prazo vem calculado pela ferramenta (`policy_checks`). Ele explica a regra completa e encaminha para a equipe, porque não executa devoluções.

---

**Cliente:** Me arrependi da minha compra, posso devolver?

**Assistente:** Olá! Tudo bem?

Para eu conferir se o seu pedido está no prazo de devolução por arrependimento, você pode me informar o número do pedido e o e-mail que usou na compra?

**Cliente:** Pedido 1, email pedro.oliveira@jmail.com

> 🔧 `get_order({"email": "pedro.oliveira@jmail.com", "order_id": 1})`

**Assistente:** Pedro, o prazo para devolução por arrependimento em compras online é de até 7 dias corridos após o recebimento do produto. O seu pedido foi entregue no dia 25/10/2025, então o prazo vai até 01/11/2025. Como ainda estamos em 30/10/2025, *você está dentro do prazo*!

O produto precisa estar na embalagem original, sem sinais de uso, com todos os acessórios e manuais. O reembolso é feito na mesma forma de pagamento em até 10 dias úteis, e o frete de devolução é por nossa conta.

Como nós do assistente virtual não conseguimos executar o processo de devolução por aqui, por favor fale com a nossa equipe pelo WhatsApp no número (67) 3341-4444 para eles seguirem com o atendimento para você, beleza?

---

**Evolução:** na primeira versão do prompt, o agente respondia "Pode sim!" antes de saber se o cliente estava no prazo. A regra "não afirme que o cliente tem direito a algo antes de consultar o sistema" corrigiu isso.
