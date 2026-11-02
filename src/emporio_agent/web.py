"""Web demo: the same agent behind a chat that looks like a phone messenger.

Uses only the standard library HTTP server, so no web framework is needed.
Each browser tab gets its own conversation, kept in memory.

Usage:
    uv run emporio-web    # then open http://localhost:8000
"""

import json
import os
import sys
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dotenv import load_dotenv

from .agent import Agent
from .cli import DEFAULT_FALLBACK_MODEL, DEFAULT_MODEL

PAGE = Path(__file__).parent / "static" / "index.html"
PORT = int(os.getenv("PORT", "8000"))


class ChatHandler(BaseHTTPRequestHandler):
    agents: dict[str, Agent] = {}
    api_key = ""

    def do_GET(self):
        if self.path != "/":
            self.send_error(404)
            return
        self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        session = str(body.get("session_id", ""))[:64]
        if not session:
            self._json(400, {"error": "session_id obrigatório"})
            return

        if self.path == "/api/reset":
            self.agents.pop(session, None)
            self._json(200, {"ok": True})
        elif self.path == "/api/chat":
            message = str(body.get("message", "")).strip()[:2000]
            if not message:
                self._json(400, {"error": "mensagem vazia"})
                return
            agent = self.agents.setdefault(
                session,
                Agent(
                    self.api_key,
                    os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
                    os.getenv("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL),
                ),
            )
            reply = agent.reply(message)
            self._json(200, {"text": reply.text, "model": reply.model, "tool_calls": [asdict(c) for c in reply.tool_calls]})
        else:
            self.send_error(404)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _send(self, status: int, payload: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def main() -> None:
    load_dotenv(".env")
    ChatHandler.api_key = os.getenv("GEMINI_API_KEY", "")
    if not ChatHandler.api_key:
        sys.exit("Defina GEMINI_API_KEY no arquivo .env (veja .env.example).")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), ChatHandler)
    except OSError:
        sys.exit(f"A porta {PORT} já está em uso. Feche o outro servidor ou use outra porta: PORT=8001 uv run emporio-web")
    print(f"Empório da Música: abra http://localhost:{PORT} (Ctrl+C para sair)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
