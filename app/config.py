"""
Google Antigravity Manager - Configuración
Configuración centralizada usando variables de entorno.
"""

import os
from datetime import timedelta


class Config:
    """Clase de configuración base."""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # JWT
    JWT_SECRET = os.environ.get('JWT_SECRET', 'jwt-secret-key-change-in-production')
    JWT_EXPIRATION_HOURS = int(os.environ.get('JWT_EXPIRATION_HOURS', 24))
    
    # Base de datos - Supabase PostgreSQL (sin fallback SQLite)
    SQLALCHEMY_DATABASE_URI = os.environ.get('SUPABASE_DB_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("SUPABASE_DB_URL no está configurada. Se requiere conexión a Supabase.")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
    
    # Sesión
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


class DevelopmentConfig(Config):
    """Configuración de desarrollo."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    """Configuración de producción."""
    DEBUG = False
    
    # En producción, SECRET_KEY viene de variables de entorno
    # La validación se hace al cargar la clase
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
    # Validar que SECRET_KEY esté definido (solo en producción real)
    if os.environ.get('FLASK_ENV') == 'production' and not SECRET_KEY:
        raise ValueError("SECRET_KEY debe estar definido en producción")


class TestingConfig(Config):
    """Configuración de pruebas."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Obtener configuración según el entorno."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    return config_map.get(config_name, DevelopmentConfig)
