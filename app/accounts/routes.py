"""
Google Antigravity Manager - Blueprint de Cuentas
Operaciones CRUD para cuentas de Google Antigravity.
"""

from flask import Blueprint, request, jsonify, g
from ..models import Account, Quota, db
from ..utils.decorators import login_required, api_require_unlock

accounts_bp = Blueprint('accounts', __name__)


# Decorador api_require_unlock importado de utils.decorators


@accounts_bp.route('/accounts', methods=['GET'])
@login_required
@api_require_unlock
def list_accounts():
    """
    Listar todas las cuentas del usuario.
    
    Query params:
        sort: Campo para ordenar (created_at, mas_usadas, menos_usadas, nombre)
        filter: Filtro de clasificación (disponibles, limite_parcial, limite_total)
    
    Returns:
        JSON con lista de cuentas
    """
    sort_by = request.args.get('sort', 'created_at')
    filter_by = request.args.get('filter', None)
    
    # Usar método optimizado (mismo que en rotation.py) para consistencia
    accounts = Account.get_all_with_rel(g.user_id)
    
    # Aplicar ordenamiento en Python
    if sort_by == 'mas_usadas':
        accounts.sort(key=lambda x: x.veces_usada or 0, reverse=True)
    elif sort_by == 'menos_usadas':
        accounts.sort(key=lambda x: x.veces_usada or 0)
    elif sort_by == 'nombre':
        accounts.sort(key=lambda x: (x.nombre or x.email_google).lower())
    else:
        # Default: created_at desc
        accounts.sort(key=lambda x: x.created_at, reverse=True)
    
    # Aplicar filtro de clasificación
    if filter_by:
        if filter_by == 'anthropic_exhausted':
            accounts = [a for a in accounts if not a.is_anthropic_available()]
        elif filter_by == 'gemini_exhausted':
            accounts = [a for a in accounts if not a.is_gemini_available()]
        elif filter_by == 'exhausted_total':
            accounts = [a for a in accounts if a.get_classification() == 'limite_total']
        else:
            accounts = [a for a in accounts if a.get_classification() == filter_by]
    
    return jsonify({
        'accounts': [a.to_dict() for a in accounts],
        'total': len(accounts)
    })


@accounts_bp.route('/accounts', methods=['POST'])
@login_required
@api_require_unlock
def create_account():
    """
    Crear nueva cuenta.
    
    Body JSON:
        email_google: Email de la cuenta Google (requerido)
        nombre: Nombre descriptivo de la cuenta (opcional)
    
    Returns:
        JSON con la cuenta creada
    """
    data = request.get_json()
    
    if not data or not data.get('email_google'):
        return jsonify({'error': 'Email de Google es requerido'}), 400
    
    # Verificar si ya existe
    existing = Account.query.filter_by(
        user_id=g.user_id,
        email_google=data['email_google']
    ).first()
    
    if existing:
        return jsonify({'error': 'Esta cuenta ya está registrada'}), 409
    
    # Crear cuenta
    account = Account(
        user_id=g.user_id,
        email_google=data['email_google'],
        nombre=data.get('nombre')
    )
    
    db.session.add(account)
    db.session.commit()
    
    # Crear cuotas vacías para ambos proveedores
    for provider in ['anthropic', 'gemini']:
        quota = Quota(account_id=account.id, provider=provider)
        db.session.add(quota)
    
    db.session.commit()
    
    return jsonify({
        'message': 'Cuenta creada exitosamente',
        'account': account.to_dict()
    }), 201


@accounts_bp.route('/accounts/<account_id>', methods=['GET'])
@login_required
@api_require_unlock
def get_account(account_id):
    """
    Obtener detalles de una cuenta específica.
    
    Args:
        account_id: ID de la cuenta
    
    Returns:
        JSON con detalles de la cuenta
    """
    account = Account.query.filter_by(id=account_id, user_id=g.user_id).first()
    
    if not account:
        return jsonify({'error': 'Cuenta no encontrada'}), 404
    
    return jsonify({'account': account.to_dict()})


@accounts_bp.route('/accounts/<account_id>', methods=['PUT'])
@login_required
@api_require_unlock
def update_account(account_id):
    """
    Actualizar una cuenta existente.
    
    Args:
        account_id: ID de la cuenta
    
    Body JSON:
        nombre: Nuevo nombre de la cuenta (opcional)
        email_google: Nuevo email (opcional)
    
    Returns:
        JSON con la cuenta actualizada
    """
    account = Account.query.filter_by(id=account_id, user_id=g.user_id).first()
    
    if not account:
        return jsonify({'error': 'Cuenta no encontrada'}), 404
    
    data = request.get_json()
    
    if 'nombre' in data:
        account.nombre = data['nombre']
    
    if 'email_google' in data:
        # Verificar que no exista otra cuenta con ese email
        existing = Account.query.filter(
            Account.user_id == g.user_id,
            Account.email_google == data['email_google'],
            Account.id != account_id
        ).first()
        
        if existing:
            return jsonify({'error': 'Ya existe una cuenta con ese email'}), 409
        
        account.email_google = data['email_google']
    
    db.session.commit()
    
    return jsonify({
        'message': 'Cuenta actualizada',
        'account': account.to_dict()
    })


@accounts_bp.route('/accounts/<account_id>', methods=['DELETE'])
@login_required
@api_require_unlock
def delete_account(account_id):
    """
    Eliminar una cuenta.
    
    Args:
        account_id: ID de la cuenta
    
    Returns:
        JSON con mensaje de confirmación
    
    Nota:
        No se puede eliminar una cuenta activa (en uso).
    """
    account = Account.query.filter_by(id=account_id, user_id=g.user_id).first()
    
    if not account:
        return jsonify({'error': 'Cuenta no encontrada'}), 404
    
    if account.activa:
        return jsonify({'error': 'No se puede eliminar una cuenta activa'}), 400
    
    db.session.delete(account)
    db.session.commit()
    
    return jsonify({'message': 'Cuenta eliminada exitosamente'})


@accounts_bp.route('/accounts/summary', methods=['GET'])
@login_required
@api_require_unlock
def get_summary():
    """
    Obtener resumen de todas las cuentas.
    
    Returns:
        JSON con estadísticas:
        - total: Total de cuentas
        - disponibles: Cuentas con todas las cuotas disponibles
        - limite_parcial: Cuentas con una cuota agotada
        - limite_total: Cuentas con todas las cuotas agotadas
        - horas_por_modelo: Horas usadas por cada proveedor
        - modelo_mas_usado: Proveedor más utilizado
    """
    from ..utils.rotation import RotationManager
    
    manager = RotationManager(g.user_id)
    summary = manager.get_summary()
    
    return jsonify(summary)
