import os
import sys
import threading
import time
import webbrowser
from app import create_app
from app.config import Config

app = create_app()

def open_browser(url: str):
    """Abre o navegador padrão automaticamente após 1.2 segundos."""
    time.sleep(1.2)
    try:
        webbrowser.open_new_tab(url)
    except Exception:
        pass

if __name__ == '__main__':
    host = Config.FLASK_HOST
    port = Config.FLASK_PORT
    debug = Config.FLASK_DEBUG
    url = f"http://{host}:{port}"
    
    print("=" * 70)
    print("   VOXEL LAB · Painel Administrativo de Cadastro de Produtos")
    print("=" * 70)
    print(f" * Repositório Alvo : {Config.REPO_PATH}")
    print(f" * Branch Git       : {Config.GIT_BRANCH}")
    print(f" * Deploy Produção  : {Config.VERCEL_DEPLOY_URL}")
    print(f" * Servidor Ativo   : {url}")
    print("=" * 70)
    print(" Pressione Ctrl+C para encerrar o servidor.")
    print("-" * 70)
    
    # Abre o navegador apenas se não estiver em processo de reload do Flask debug
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
        
    app.run(host=host, port=port, debug=debug)

