"""
Google Antigravity Manager - Decoradores de Utilidad
Rate limiting y autenticación para Modo Usuario Único.
"""

from functools import wraps
from flask import g, jsonify, session
from ..models import SINGLE_USER_ID


def api_require_unlock(f):
    """Decorador para requerir desbloqueo por PIN en rutas API."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('unlocked', False):
            return jsonify({'error': 'Sesión bloqueada. Ingresa tu PIN.'}), 401
        return f(*args, **kwargs)
    return decorated_function

# Instancia del rate limiter (inicializada en app factory si es necesario)
limiter = None


def init_limiter(app):
    """Inicializar rate limiter con contexto de aplicación."""
    global limiter
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"]
        )
    except ImportError:
        pass


def login_required(f):
    """
    Decorador para rutas protegidas (Modo Usuario Único).
    Automáticamente establece g.user_id al ID de usuario único.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Modo Usuario Único: siempre autenticado
        g.user_id = SINGLE_USER_ID
        return f(*args, **kwargs)
    return decorated_function


def rate_limit(limit_string):
    """
    Decorador de rate limiting personalizable.
    
    Args:
        limit_string: String de límite (ej: "5 per minute")
        
    Uso:
        @rate_limit("5 per minute")
        def mi_funcion():
            pass
    """
    def decorator(f):
        if limiter:
            return limiter.limit(limit_string)(f)
        return f
    return decorator
