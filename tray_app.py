"""
Inicializador com ícone na bandeja do sistema (área de notificação do Windows).

- Sobe o servidor Flask em segundo plano (sem janela de console).
- Abre o navegador automaticamente.
- Ícone na bandeja com: Abrir painel / Abrir site (Vercel) / Encerrar servidor.
"""
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path

from PIL import Image, ImageDraw
import pystray
from werkzeug.serving import make_server

from app import create_app
from app.config import Config, BASE_DIR

APP_NAME = "VOXEL LAB · Cadastro de Produtos"


def resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / rel


def load_icon() -> Image.Image:
    ico = resource_path("icon.ico")
    if ico.exists():
        try:
            return Image.open(ico)
        except Exception:
            pass
    # Fallback: desenha um ícone simples
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((2, 2, 62, 62), radius=12, fill=(124, 58, 237))
    d.polygon([(14, 16), (24, 16), (32, 40), (40, 16), (50, 16), (36, 50), (28, 50)], fill="white")
    return img


def port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def setup_logging():
    # Em modo janela (sem console) stdout/stderr são None; redireciona para arquivo de log
    if sys.stdout is None or sys.stderr is None:
        log = open(BASE_DIR / "servidor.log", "a", encoding="utf-8", buffering=1)
        sys.stdout = log
        sys.stderr = log


def main():
    setup_logging()
    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    url = f"http://{host}:{port}"

    # Instância única: se já estiver rodando, só abre o navegador
    if port_in_use(host, port):
        webbrowser.open_new_tab(url)
        return

    flask_app = create_app()
    flask_app.debug = False  # reloader/debugger não funcionam empacotado
    server = make_server(host, port, flask_app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    threading.Timer(1.0, lambda: webbrowser.open_new_tab(url)).start()

    def abrir_painel(icon, item):
        webbrowser.open_new_tab(url)

    def abrir_site(icon, item):
        webbrowser.open_new_tab(Config.VERCEL_DEPLOY_URL)

    def encerrar(icon, item):
        icon.visible = False
        server.shutdown()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Abrir painel", abrir_painel, default=True),
        pystray.MenuItem("Abrir site (Vercel)", abrir_site),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"Servidor: {url}", None, enabled=False),
        pystray.MenuItem("Encerrar servidor", encerrar),
    )
    icon = pystray.Icon("voxel_lab_admin", load_icon(), APP_NAME, menu)
    icon.run()
    os._exit(0)


if __name__ == "__main__":
    main()
