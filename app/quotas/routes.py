"""
Google Antigravity Manager - Blueprint de Cuotas
Gestión de cuotas para proveedores Gemini y Anthropic.
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime
from ..models import Account, Quota, db
from ..utils.decorators import login_required, api_require_unlock

quotas_bp = Blueprint('quotas', __name__)


# Decorador api_require_unlock importado de utils.decorators


@quotas_bp.route('/quotas/<account_id>', methods=['GET'])
@login_required
@api_require_unlock
def get_quotas(account_id):
    """
    Obtener cuotas de una cuenta específica.
    
    Args:
        account_id: ID de la cuenta
    
    Returns:
        JSON con estado de cuotas de ambos proveedores
    """
    account = Account.query.filter_by(id=account_id, user_id=g.user_id).first()
    
    if not account:
        return jsonify({'error': 'Cuenta no encontrada'}), 404
    
    return jsonify({
        'account_id': account_id,
        'quotas': {
            'anthropic': account.get_anthropic_quota().to_dict() if account.get_anthropic_quota() else {'disponible': True},
            'gemini': account.get_gemini_quota().to_dict() if account.get_gemini_quota() else {'disponible': True}
        }
    })


@quotas_bp.route('/quotas/<account_id>/<provider>/exhausted', methods=['POST'])
@login_required
@api_require_unlock
def mark_exhausted(account_id, provider):
    """
    Marcar cuota como agotada.
    
    Args:
        account_id: ID de la cuenta
        provider: Proveedor ('anthropic' o 'gemini')
    
    Body JSON:
        proximo_reset: Fecha/hora del próximo reinicio (ISO format)
    
    Returns:
        JSON con cuota actualizada
    """
    if provider not in ['anthropic', 'gemini']:
        return jsonify({'error': 'Proveedor inválido'}), 400
    
    account = Account.query.filter_by(id=account_id, user_id=g.user_id).first()
    if not account:
        return jsonify({'error': 'Cuenta no encontrada'}), 404
    
    data = request.get_json()
    if not data or not data.get('proximo_reset'):
        return jsonify({'error': 'Fecha de próximo reinicio es requerida'}), 400
    
    try:
        reset_time = datetime.fromisoformat(data['proximo_reset'].replace('Z', '+00:00'))
    except ValueError:
        return jsonify({'error': 'Formato de fecha inválido'}), 400
    
    # Obtener o crear cuota
    quota = Quota.query.filter_by(account_id=account_id, provider=provider).first()
    
    if not quota:
        quota = Quota(account_id=account_id, provider=provider)
        db.session.add(quota)
        db.session.commit()
    
    quota.mark_exhausted(reset_time)
    
    return jsonify({
        'message': f'Cuota de {provider} marcada como agotada',
        'quota': quota.to_dict()
    })


@quotas_bp.route('/quotas/<account_id>/<provider>/reset', methods=['POST'])
@login_required
@api_require_unlock
def reset_quota(account_id, provider):
    """
    Reiniciar cuota manualmente.
    
    Args:
        account_id: ID de la cuenta
        provider: Proveedor ('anthropic' o 'gemini')
    
    Returns:
        JSON con cuota reiniciada
    """
    if provider not in ['anthropic', 'gemini']:
        return jsonify({'error': 'Proveedor inválido'}), 400
    
    account = Account.query.filter_by(id=account_id, user_id=g.user_id).first()
    if not account:
        return jsonify({'error': 'Cuenta no encontrada'}), 404
    
    quota = Quota.query.filter_by(account_id=account_id, provider=provider).first()
    
    if not quota:
        return jsonify({'error': 'Cuota no encontrada'}), 404
    
    quota.reset()
    
    return jsonify({
        'message': f'Cuota de {provider} reiniciada',
        'quota': quota.to_dict()
    })


@quotas_bp.route('/quotas/next-reset/<provider>', methods=['GET'])
@login_required
@api_require_unlock
def get_next_reset(provider):
    """
    Obtener el próximo tiempo de reinicio para un proveedor.
    
    Args:
        provider: Proveedor ('anthropic' o 'gemini')
    
    Returns:
        JSON con timestamp del próximo reinicio
    """
    if provider not in ['anthropic', 'gemini']:
        return jsonify({'error': 'Proveedor inválido'}), 400
    
    from ..utils.rotation import RotationManager
    manager = RotationManager(g.user_id)
    
    if provider == 'anthropic':
        next_reset = manager.get_next_anthropic_reset()
    else:
        # Para Gemini, buscar de forma similar
        quota = Quota.query.join(Account).filter(
            Account.user_id == g.user_id,
            Quota.provider == 'gemini',
            Quota.estado == 'agotada',
            Quota.proximo_reset.isnot(None)
        ).order_by(Quota.proximo_reset.asc()).first()
        
        next_reset = quota.proximo_reset.isoformat() if quota and quota.proximo_reset else None
    
    return jsonify({
        'provider': provider,
        'proximo_reset': next_reset
    })


@quotas_bp.route('/quotas/check-resets', methods=['POST'])
@login_required
@api_require_unlock
def check_resets():
    """
    Verificar y reiniciar cuotas expiradas automáticamente.
    
    Returns:
        JSON con número de cuotas reiniciadas
    """
    from ..utils.rotation import RotationManager
    manager = RotationManager(g.user_id)
    
    reset_count = manager.check_and_reset_quotas()
    
    return jsonify({
        'message': f'{reset_count} cuota(s) reiniciada(s)',
        'reset_count': reset_count
    })
