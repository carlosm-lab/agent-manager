"""
Google Antigravity Manager - Blueprint de Autenticación
Modo Usuario Único: No requiere autenticación, acceso automático.
"""

from flask import Blueprint, redirect, url_for

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Redirigir al dashboard - no se requiere login en Modo Usuario Único."""
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Redirigir al dashboard - no se requiere registro en Modo Usuario Único."""
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Redirigir al dashboard - no se requiere logout en Modo Usuario Único."""
    return redirect(url_for('dashboard.index'))


@auth_bp.route('/me', methods=['GET'])
def get_current_user_info():
    """Retornar información del usuario único para Modo Usuario Único."""
    from flask import jsonify
    from ..models import SINGLE_USER_ID
    
    return jsonify({
        'id': SINGLE_USER_ID,
        'email': 'admin@local',
        'single_user_mode': True
    })
