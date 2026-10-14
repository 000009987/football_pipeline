"""Local, read-only web server for the predictions dashboard."""

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from config import OUTPUT_JSON

ROOT = Path(__file__).parent.parent
PREDICTIONS_PATH = Path(OUTPUT_JSON)
if not PREDICTIONS_PATH.is_absolute():
    PREDICTIONS_PATH = ROOT / PREDICTIONS_PATH
DASHBOARD_PATH = ROOT / "dashboard.html"


class DashboardHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, content_type: str, content: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path in ("/", "/dashboard.html"):
            try:
                content = DASHBOARD_PATH.read_bytes()
            except OSError as exc:
                self.log_error("No se pudo leer dashboard.html: %s", exc)
                self._send(500, "text/plain; charset=utf-8",
                           b"No se pudo cargar dashboard.html")
                return
            self._send(200, "text/html; charset=utf-8", content)
            return

        if path == "/api/predictions":
            try:
                content = (PREDICTIONS_PATH.read_bytes()
                           if PREDICTIONS_PATH.exists()
                           else json.dumps({
                               "generated_at": None,
                               "days_ahead": None,
                               "count": 0,
                               "matches": [],
                           }).encode("utf-8"))
            except OSError as exc:
                self.log_error("No se pudieron leer las predicciones: %s", exc)
                self._send(500, "application/json; charset=utf-8",
                           b'{"error":"No se pudieron leer las predicciones"}')
                return
            self._send(200, "application/json; charset=utf-8", content)
            return

        self._send(404, "text/plain; charset=utf-8", b"No encontrado")


def serve_dashboard(port: int = 8765) -> None:
    if not 1 <= port <= 65535:
        raise ValueError("El puerto debe estar entre 1 y 65535.")

    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Dashboard disponible en {url} (Ctrl+C para detener)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor del dashboard detenido.")
    finally:
        server.server_close()
