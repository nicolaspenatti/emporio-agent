"""Command-line chat with the agent.

Usage:
    uv run emporio-agent           # normal chat
    uv run emporio-agent --debug   # also shows tool calls and errors
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from .agent import Agent

DEFAULT_MODEL = "gemini-3.5-flash"
DEFAULT_FALLBACK_MODEL = "gemini-flash-lite-latest"


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat com o assistente da Empório da Música.")
    parser.add_argument("--debug", action="store_true", help="mostra as ferramentas chamadas e erros")
    args = parser.parse_args()

    load_dotenv(".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("Defina GEMINI_API_KEY no arquivo .env (veja .env.example).")

    agent = Agent(
        api_key=api_key,
        model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        fallback_model=os.getenv("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL),
    )
    print("Empório da Música: assistente virtual")
    print("Digite sua mensagem. Comandos: /nova (nova conversa), /sair\n")

    while True:
        try:
            message = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message:
            continue
        if message == "/sair":
            break
        if message == "/nova":
            agent.reset()
            print("(nova conversa)\n")
            continue

        reply = agent.reply(message)
        if args.debug:
            for call in reply.tool_calls:
                print(f"  [ferramenta] {call.name}({json.dumps(call.args, ensure_ascii=False)})")
                print(f"  [resultado] {json.dumps(call.result, ensure_ascii=False)[:300]}")
            if reply.error:
                print(f"  [erro] {reply.error}")
            if reply.model:
                print(f"  [modelo] {reply.model}")
        print(f"\nEmpório: {reply.text}\n")
