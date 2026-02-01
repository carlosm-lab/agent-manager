"""
Google Antigravity Manager - Blueprint de Sesiones
Seguimiento y gestión de sesiones de trabajo.
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime
from ..models import Account, Session, db
from ..utils.decorators import login_required, api_require_unlock
from ..utils.rotation import RotationManager

sessions_bp = Blueprint('sessions', __name__)


# Decorador api_require_unlock importado de utils.decorators


@sessions_bp.route('/sessions/start', methods=['POST'])
@login_required
@api_require_unlock
def start_session():
    """
    Iniciar una nueva sesión de trabajo.
    
    Body JSON:
        account_id: ID de la cuenta a usar (requerido)
        provider: Proveedor a usar - 'anthropic' o 'gemini' (requerido)
    
    Returns:
        JSON con la sesión creada
    
    Errores:
        - 400: Datos faltantes o inválidos
        - 409: Ya hay una sesión activa
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Datos requeridos'}), 400
    
    account_id = data.get('account_id')
    provider = data.get('provider')
    
    if not account_id or not provider:
        return jsonify({'error': 'account_id y provider son requeridos'}), 400
    
    if provider not in ['anthropic', 'gemini']:
        return jsonify({'error': 'Proveedor inválido'}), 400
    
    manager = RotationManager(g.user_id)
    
    try:
        new_session = manager.start_session(account_id, provider)
        account = Account.query.get(account_id)
        
        return jsonify({
            'message': 'Sesión iniciada',
            'session': new_session.to_dict(),
            'account': account.to_dict() if account else None
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@sessions_bp.route('/sessions/end', methods=['POST'])
@login_required
@api_require_unlock
def end_session():
    """
    Finalizar la sesión activa.
    
    Body JSON:
        motivo: 'manual' o 'cuota_agotada' (opcional, default: 'manual')
        proximo_reset: Timestamp del próximo reinicio si cuota agotada (opcional)
    
    Returns:
        JSON con la sesión finalizada
    """
    data = request.get_json() or {}
    
    motivo = data.get('motivo', 'manual')
    proximo_reset = None
    
    if data.get('proximo_reset'):
        try:
            proximo_reset = datetime.fromisoformat(data['proximo_reset'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido'}), 400
    
    try:
        manager = RotationManager(g.user_id)
        ended_session = manager.end_session(motivo, proximo_reset)
        
        if not ended_session:
            return jsonify({'error': 'No hay sesión activa'}), 404
        
        return jsonify({
            'message': 'Sesión finalizada',
            'session': ended_session.to_dict()
        })
    except Exception as e:
        import traceback
        traceback.print_exc() # Print stack trace to console for debugging
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500


@sessions_bp.route('/sessions/active', methods=['GET'])
@login_required
@api_require_unlock
def get_active_session():
    """
    Obtener la sesión activa actual.
    
    Returns:
        JSON con la sesión activa o null si no hay ninguna
    """
    manager = RotationManager(g.user_id)
    active = manager.get_active_session()
    
    if not active:
        return jsonify({'session': None, 'account': None})
    
    account = Account.query.get(active.account_id)
    
    return jsonify({
        'session': active.to_dict(),
        'account': account.to_dict() if account else None
    })


@sessions_bp.route('/sessions/rotate', methods=['POST'])
@login_required
@api_require_unlock
def rotate_session():
    """
    Rotar a la siguiente mejor cuenta disponible.
    
    Body JSON:
        motivo: Motivo de la rotación (default: 'cuota_agotada')
        proximo_reset: Timestamp del próximo reinicio de la cuota actual
        auto_start: Si True, inicia sesión automáticamente (default: True)
    
    Returns:
        JSON con información de la rotación:
        - ended_session: Sesión que terminó
        - next_account: Siguiente cuenta sugerida
        - new_session: Nueva sesión si auto_start=True
        - needs_user_choice: True si solo hay Gemini disponible
    """
    data = request.get_json() or {}
    
    motivo = data.get('motivo', 'cuota_agotada')
    auto_start = data.get('auto_start', True)
    proximo_reset = None
    
    if data.get('proximo_reset'):
        try:
            proximo_reset = datetime.fromisoformat(data['proximo_reset'].replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'Formato de fecha inválido'}), 400
    
    manager = RotationManager(g.user_id)
    result = manager.rotate_to_next(motivo, proximo_reset, auto_start)
    
    return jsonify(result)


@sessions_bp.route('/sessions/history', methods=['GET'])
@login_required
@api_require_unlock
def get_history():
    """
    Obtener historial de sesiones.
    
    Query params:
        limit: Número máximo de sesiones (default: 50)
        account_id: Filtrar por cuenta específica (opcional)
        provider: Filtrar por proveedor (opcional)
    
    Returns:
        JSON con lista de sesiones ordenadas por fecha descendente
    """
    limit = request.args.get('limit', 50, type=int)
    account_id = request.args.get('account_id')
    provider = request.args.get('provider')
    
    query = Session.query.join(Account).filter(Account.user_id == g.user_id)
    
    if account_id:
        query = query.filter(Session.account_id == account_id)
    
    if provider:
        query = query.filter(Session.provider == provider)
    
    sessions = query.order_by(Session.inicio.desc()).limit(limit).all()
    
    return jsonify({
        'sessions': [s.to_dict() for s in sessions],
        'total': len(sessions)
    })


@sessions_bp.route('/sessions/stats', methods=['GET'])
@login_required
@api_require_unlock
def get_stats():
    """
    Obtener estadísticas de sesiones.
    
    Returns:
        JSON con estadísticas:
        - total_sesiones: Total de sesiones completadas
        - tiempo_total: Tiempo total de uso
        - por_proveedor: Desglose por proveedor
        - promedio_duracion: Duración promedio de sesiones
    """
    sessions = Session.query.join(Account).filter(
        Account.user_id == g.user_id,
        Session.fin.isnot(None)
    ).all()
    
    total_segundos = 0
    por_proveedor = {'anthropic': {'sesiones': 0, 'segundos': 0}, 'gemini': {'sesiones': 0, 'segundos': 0}}
    
    for s in sessions:
        if s.duracion:
            segundos = s.duracion.total_seconds()
            total_segundos += segundos
            por_proveedor[s.provider]['sesiones'] += 1
            por_proveedor[s.provider]['segundos'] += segundos
    
    total_sesiones = len(sessions)
    promedio = total_segundos / total_sesiones if total_sesiones > 0 else 0
    
    return jsonify({
        'total_sesiones': total_sesiones,
        'tiempo_total_segundos': total_segundos,
        'tiempo_total_horas': round(total_segundos / 3600, 2),
        'promedio_duracion_segundos': round(promedio, 2),
        'por_proveedor': {
            'anthropic': {
                'sesiones': por_proveedor['anthropic']['sesiones'],
                'horas': round(por_proveedor['anthropic']['segundos'] / 3600, 2)
            },
            'gemini': {
                'sesiones': por_proveedor['gemini']['sesiones'],
                'horas': round(por_proveedor['gemini']['segundos'] / 3600, 2)
            }
        }
    })
