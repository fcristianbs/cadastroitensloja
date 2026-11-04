import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Quando empacotado (PyInstaller), o .env fica ao lado do executável
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega variáveis do arquivo .env
env_file = BASE_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file)
else:
    load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'voxel-lab-admin-dev-secret-key-2026')
    
    # Caminho do repositório do catálogo
    _raw_repo_path = os.getenv('CATALOG_REPO_PATH', '')
    
    # Lista de caminhos potenciais para autodetecção caso o configurado não seja válido
    _candidate_paths = [
        Path(_raw_repo_path) if _raw_repo_path else None,
        Path('C:/git/VOXEL LAB'),
        BASE_DIR.parent / 'VOXEL LAB',
        BASE_DIR.parent / 'voxel-lab',
        Path.cwd()
    ]
    
    REPO_PATH = None
    for cand in _candidate_paths:
        if cand and cand.exists() and (cand / 'data' / 'produtos.json').exists():
            REPO_PATH = cand.resolve()
            break
            
    if not REPO_PATH:
        # Se nenhum caminho contendo data/produtos.json foi encontrado, utiliza o configurado ou padrão
        REPO_PATH = Path(_raw_repo_path).resolve() if _raw_repo_path else (Path('C:/git/VOXEL LAB')).resolve()

    # Caminhos específicos dentro do repositório alvo
    PRODUTOS_JSON_PATH = REPO_PATH / 'data' / 'produtos.json'
    CATEGORIAS_JSON_PATH = REPO_PATH / 'data' / 'categorias.json'
    STATIC_IMG_DIR = REPO_PATH / 'static' / 'img' / 'produtos'
    PUBLIC_IMG_DIR = REPO_PATH / 'public' / 'static' / 'img' / 'produtos'
    
    # Configurações do Git
    GIT_BRANCH = os.getenv('GIT_BRANCH', 'main')
    GIT_REMOTE = os.getenv('GIT_REMOTE', 'origin')
    ENABLE_AUTO_PUSH = os.getenv('ENABLE_AUTO_PUSH', 'True').lower() in ('true', '1', 'yes')
    
    # URLs de produção e repositório
    GIT_REMOTE_URL = os.getenv('GIT_REMOTE_URL', 'https://github.com/fcristianbs/voxel-lab.git')
    VERCEL_DEPLOY_URL = os.getenv('VERCEL_DEPLOY_URL', 'https://voxel-lab-black.vercel.app')
    
    # Servidor local
    FLASK_HOST = os.getenv('FLASK_HOST', '127.0.0.1')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5050))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 'yes')

    # Uploads permitidos
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max

    @classmethod
    def reload_config(cls, new_repo_path: str = None):
        """Permite recarregar caminhos dinamicamente se o usuário alterar o caminho do repositório."""
        if new_repo_path:
            cls.REPO_PATH = Path(new_repo_path).resolve()
            cls.PRODUTOS_JSON_PATH = cls.REPO_PATH / 'data' / 'produtos.json'
            cls.CATEGORIAS_JSON_PATH = cls.REPO_PATH / 'data' / 'categorias.json'
            cls.STATIC_IMG_DIR = cls.REPO_PATH / 'static' / 'img' / 'produtos'
            cls.PUBLIC_IMG_DIR = cls.REPO_PATH / 'public' / 'static' / 'img' / 'produtos'

