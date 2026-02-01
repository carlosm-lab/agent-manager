"""
Google Antigravity Manager - Blueprint del Dashboard
Vistas principales del dashboard con protección por PIN.
Incluye bloqueo progresivo exponencial por intentos fallidos.
"""

import os
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, g, request, redirect, url_for, session
from ..utils.decorators import login_required
from ..utils.rotation import RotationManager
from ..utils.encryption import hash_pin, verify_pin
from ..models import Account

# Importar limiter para rate limiting
from app import limiter

dashboard_bp = Blueprint('dashboard', __name__)

# ============================================
# PROGRESSIVE LOCKOUT SYSTEM
# ============================================
# In-memory storage for lockout tracking (resets on server restart)
# For production with multiple instances, use Redis or database
_lockout_storage = {}

# Lockout thresholds: (attempts, lockout_seconds)
LOCKOUT_THRESHOLDS = [
    (10, 30),      # 10 intentos = 30 segundos
    (20, 60),      # 20 intentos = 1 minuto
    (30, 120),     # 30 intentos = 2 minutos
    (40, 240),     # 40 intentos = 4 minutos
    (50, 480),     # 50 intentos = 8 minutos
    (60, 960),     # 60 intentos = 16 minutos
    (70, 1920),    # 70 intentos = 32 minutos
    (80, 3600),    # 80 intentos = 1 hora
    (90, 7200),    # 90 intentos = 2 horas
    (100, 14400),  # 100 intentos = 4 horas
    (110, 28800),  # 110 intentos = 8 horas
    (120, 86400),  # 120+ intentos = 24 horas (máximo)
]


def get_client_ip():
    """Get client IP address, considering proxies."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'


def get_lockout_info(ip):
    """Get lockout information for an IP address."""
    if ip not in _lockout_storage:
        _lockout_storage[ip] = {
            'attempts': 0,
            'locked_until': None,
            'last_attempt': None
        }
    return _lockout_storage[ip]


def calculate_lockout_duration(attempts):
    """Calculate lockout duration based on number of failed attempts."""
    for threshold, seconds in LOCKOUT_THRESHOLDS:
        if attempts < threshold:
            return 0  # No lockout yet
    # If exceeded all thresholds, use maximum (24 hours)
    return LOCKOUT_THRESHOLDS[-1][1]


def get_lockout_seconds_for_attempt(attempts):
    """Get the lockout seconds for the current attempt count."""
    lockout_seconds = 0
    for threshold, seconds in LOCKOUT_THRESHOLDS:
        if attempts >= threshold:
            lockout_seconds = seconds
        else:
            break
    return lockout_seconds


def check_lockout(ip):
    """
    Check if IP is currently locked out.
    Returns: (is_locked, remaining_seconds, message)
    """
    info = get_lockout_info(ip)
    
    if info['locked_until']:
        now = datetime.now(timezone.utc)
        if now < info['locked_until']:
            remaining = (info['locked_until'] - now).total_seconds()
            
            # Format remaining time for user
            if remaining > 3600:
                time_str = f"{int(remaining // 3600)} hora(s) y {int((remaining % 3600) // 60)} minuto(s)"
            elif remaining > 60:
                time_str = f"{int(remaining // 60)} minuto(s) y {int(remaining % 60)} segundo(s)"
            else:
                time_str = f"{int(remaining)} segundo(s)"
            
            return True, remaining, f"🔒 Bloqueado por {time_str}. Intentos: {info['attempts']}"
        else:
            # Lockout expired, but don't reset attempts
            info['locked_until'] = None
    
    return False, 0, None


def record_failed_attempt(ip):
    """Record a failed login attempt and apply lockout if needed."""
    info = get_lockout_info(ip)
    info['attempts'] += 1
    info['last_attempt'] = datetime.now(timezone.utc)
    
    # Check if we should apply lockout
    lockout_seconds = get_lockout_seconds_for_attempt(info['attempts'])
    
    if lockout_seconds > 0:
        info['locked_until'] = datetime.now(timezone.utc) + timedelta(seconds=lockout_seconds)
        
        # Format lockout duration for message
        if lockout_seconds >= 3600:
            duration_str = f"{lockout_seconds // 3600} hora(s)"
        elif lockout_seconds >= 60:
            duration_str = f"{lockout_seconds // 60} minuto(s)"
        else:
            duration_str = f"{lockout_seconds} segundo(s)"
        
        return f"⚠️ Demasiados intentos ({info['attempts']}). Bloqueado por {duration_str}."
    
    # Show warning when approaching lockout
    next_threshold = None
    for threshold, seconds in LOCKOUT_THRESHOLDS:
        if info['attempts'] < threshold:
            next_threshold = threshold
            break
    
    if next_threshold:
        remaining_attempts = next_threshold - info['attempts']
        if remaining_attempts <= 3:
            return f"PIN incorrecto. ⚠️ {remaining_attempts} intento(s) restantes antes del bloqueo."
    
    return "PIN incorrecto"


def reset_attempts(ip):
    """Reset attempts on successful login."""
    if ip in _lockout_storage:
        _lockout_storage[ip] = {
            'attempts': 0,
            'locked_until': None,
            'last_attempt': None
        }


def is_unlocked():
    """Verificar si la sesión está desbloqueada."""
    return session.get('unlocked', False)


def require_unlock(f):
    """Decorador para requerir desbloqueo por PIN antes de acceder a la ruta."""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_unlocked():
            return redirect(url_for('dashboard.lock'))
        return f(*args, **kwargs)
    return decorated_function


@dashboard_bp.route('/lock')
def lock():
    """Mostrar pantalla de bloqueo."""
    # Si ya está desbloqueado, redirigir al dashboard
    if is_unlocked():
        return redirect(url_for('dashboard.index'))
    
    # Check for lockout status to show on lock screen
    ip = get_client_ip()
    is_locked, remaining, message = check_lockout(ip)
    
    return render_template('lock.html', 
                          error=message if is_locked else None,
                          locked=is_locked,
                          lockout_seconds=int(remaining) if is_locked else 0)


@dashboard_bp.route('/unlock', methods=['POST'])
@limiter.limit("30 per minute", error_message="Demasiados intentos. Espera 1 minuto.")
def unlock():
    """
    Manejar desbloqueo por PIN con bloqueo progresivo.
    
    Seguridad:
        - Bloqueo progresivo exponencial por intentos fallidos
        - Rate limiting adicional con flask-limiter
        - Comparación timing-safe para prevenir ataques de temporización
    """
    ip = get_client_ip()
    
    # Check if currently locked out
    is_locked, remaining, lockout_message = check_lockout(ip)
    if is_locked:
        return render_template('lock.html', 
                              error=lockout_message,
                              locked=True,
                              lockout_seconds=int(remaining))
    
    pin = request.form.get('pin', '')

    # También soportar body JSON para clientes API
    if not pin and request.is_json:
        pin = request.json.get('pin', '')
    
    # Obtener hash del PIN almacenado desde variables de entorno
    stored_pin_hash = os.environ.get('ACCESS_PIN_HASH', '')
    
    # Si no hay PIN configurado, usar PIN de desarrollo por defecto
    if not stored_pin_hash:
        # PIN por defecto para desarrollo: "admin"
        stored_pin_hash = hash_pin('admin')
    
    # Usar comparación timing-safe via verify_pin (previene ataques de temporización)
    if verify_pin(pin, stored_pin_hash):
        # SUCCESS: Reset attempts on successful login
        reset_attempts(ip)
        session['unlocked'] = True
        session.permanent = True
        return redirect(url_for('dashboard.index'))
    
    # FAIL: Record failed attempt and get appropriate error message
    error_message = record_failed_attempt(ip)
    
    # Check if now locked after this attempt
    is_locked, remaining, _ = check_lockout(ip)
    
    return render_template('lock.html', 
                          error=error_message,
                          locked=is_locked,
                          lockout_seconds=int(remaining) if is_locked else 0)


@dashboard_bp.route('/logout')
def logout():
    """Bloquear la aplicación."""
    session.pop('unlocked', None)
    return redirect(url_for('dashboard.lock'))


@dashboard_bp.route('/')
@login_required
@require_unlock
def index():
    """
    Página principal del dashboard.
    
    Muestra:
        - Cuenta activa actual (si existe)
        - Resumen de cuentas
        - Lista de cuentas disponibles
    """
    manager = RotationManager(g.user_id)
    
    # Verificar y reiniciar cuotas expiradas
    manager.check_and_reset_quotas()
    
    # Obtener sesión activa
    active_session = manager.get_active_session()
    active_account = None
    
    if active_session:
        active_account = Account.query.get(active_session.account_id)
    
    # Obtener resumen
    summary = manager.get_summary()
    
    # Obtener todas las cuentas para el modal
    accounts = Account.query.filter_by(user_id=g.user_id).order_by(Account.created_at.desc()).all()
    
    return render_template(
        'dashboard/index.html',
        active_session=active_session,
        active_account=active_account,
        summary=summary,
        accounts=accounts
    )


@dashboard_bp.route('/accounts')
@login_required
@require_unlock
def accounts_list():
    """
    Página de listado de cuentas.
    
    Query params:
        sort: Campo de ordenamiento
    """
    sort_by = request.args.get('sort', 'created_at')
    
    query = Account.query.filter_by(user_id=g.user_id)
    
    # Aplicar ordenamiento
    if sort_by == 'mas_usadas':
        query = query.order_by(Account.veces_usada.desc())
    elif sort_by == 'menos_usadas':
        query = query.order_by(Account.veces_usada.asc())
    elif sort_by == 'nombre':
        query = query.order_by(Account.nombre.asc())
    else:
        query = query.order_by(Account.created_at.desc())
    
    accounts = query.all()
    
    return render_template('accounts/list.html', accounts=accounts)
