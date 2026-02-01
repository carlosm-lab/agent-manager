"""
Google Antigravity Manager - Flask Application Factory
Listo para producción con características de seguridad.
"""

import os
import logging
from flask import Flask, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

from .models import db
from .config import get_config

# Inicializar rate limiter con tolerancia a fallos para Vercel
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "30 per minute"],
    storage_uri="memory://",
    swallow_errors=True  # No fallar si hay problemas con el storage
)


def create_app(config_name=None):
    """Crear y configurar la aplicación Flask."""
    app = Flask(__name__,
                template_folder='../templates',
                static_folder='../static')
    
    # Cargar configuración
    config = get_config(config_name)
    app.config.from_object(config)
    
    # Inicializar extensiones
    db.init_app(app)
    
    # Inicializar limiter con manejo de errores
    try:
        limiter.init_app(app)
    except Exception as e:
        logging.warning(f"Rate limiter no disponible: {e}")
    
    # Configurar CORS
    allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
    CORS(app, origins=allowed_origins, supports_credentials=True)
    
    # Configurar headers de seguridad
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response
    
    # Registrar blueprints
    from .auth import auth_bp
    from .accounts import accounts_bp
    from .quotas import quotas_bp
    from .sessions import sessions_bp
    from .dashboard import dashboard_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(accounts_bp, url_prefix='/api')
    app.register_blueprint(quotas_bp, url_prefix='/api')
    app.register_blueprint(sessions_bp, url_prefix='/api')
    app.register_blueprint(dashboard_bp)
    
    # Crear tablas si no existen (con manejo de errores para Vercel)
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            logging.warning(f"No se pudieron crear tablas (normal si ya existen): {e}")
    
    return app

