import os
from flask import Flask
from app.config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Registra Blueprints e Rotas
    from app.routes import main_bp, api_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Filtros e Helpers para Jinja
    @app.context_processor
    def inject_global_data():
        from app.services.git_service import get_repo_status
        return {
            'repo_status': get_repo_status(),
            'config': Config
        }
        
    return app

