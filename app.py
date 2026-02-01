"""
Flask Application - Plantilla en Construcción
Listo para producción en Vercel
"""

import os
import json
import re
import secrets
import traceback
import uuid
import logging
import ipaddress
import hmac
from datetime import datetime, timezone, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, g, Response, redirect, url_for

load_dotenv()

# Detección de entorno
IS_PRODUCTION = bool(os.environ.get('VERCEL'))
IS_DEVELOPMENT = not IS_PRODUCTION

# Logger estructurado JSON
DEPLOYMENT_ID = os.environ.get('VERCEL_DEPLOYMENT_ID', os.environ.get('VERCEL_GIT_COMMIT_SHA', 'local')[:12])


class JSONFormatter(logging.Formatter):
    """Formateador JSON para logs estructurados."""

    def format(self, record):
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "deployment_id": DEPLOYMENT_ID,
        }
        try:
            if hasattr(g, 'request_id'):
                log_record["request_id"] = g.request_id
        except RuntimeError:
            pass
        if hasattr(record, 'extra'):
            log_record.update(record.extra)
        return json.dumps(log_record)


# Configuración de logging
LOG_LEVEL_RAW = os.environ.get('LOG_LEVEL', 'INFO').upper()
VALID_LOG_LEVELS = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
LOG_LEVEL = LOG_LEVEL_RAW if LOG_LEVEL_RAW in VALID_LOG_LEVELS else 'INFO'

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=getattr(logging, LOG_LEVEL), handlers=[handler])
logger = logging.getLogger(__name__)

if LOG_LEVEL_RAW not in VALID_LOG_LEVELS:
    logger.warning(
        f"LOG_LEVEL inválido '{LOG_LEVEL_RAW}', usando INFO",
        extra={"component": "config", "provided_value": LOG_LEVEL_RAW}
    )


# Utilidades de privacidad (GDPR)
def sanitize_log_string(value: str, max_length: int = 150) -> str:
    """Sanitiza string para logging seguro."""
    if not value:
        return ''
    import re as _re
    ansi_pattern = _re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
    sanitized = ansi_pattern.sub('', value)
    sanitized = ''.join(char for char in sanitized if char >= ' ' or char in '\n\t')
    if len(sanitized) > max_length:
        return sanitized[:max_length - 3] + '...'
    return sanitized


def anonymize_ip(ip_address: str) -> str:
    """Anonimiza IP para GDPR (IPv4: /24, IPv6: /48)."""
    if not ip_address:
        return 'unknown'
    try:
        addr = ipaddress.ip_address(ip_address)
        if isinstance(addr, ipaddress.IPv4Address):
            network = ipaddress.IPv4Network(f"{ip_address}/24", strict=False)
            return str(network.network_address)
        elif isinstance(addr, ipaddress.IPv6Address):
            network = ipaddress.IPv6Network(f"{ip_address}/48", strict=False)
            return str(network.network_address)
    except ValueError:
        return 'invalid-ip'
    return 'unknown'


# Configuración de seguridad
SECRET_KEY = os.environ.get('SECRET_KEY')

if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECRET_KEY requerida en producción. "
            "Genera una con: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    else:
        SECRET_KEY = secrets.token_hex(32)


# Aplicación Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['WTF_CSRF_ENABLED'] = True
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1 MB
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.jinja_env.auto_reload = IS_DEVELOPMENT


# Rate Limiting
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

REDIS_URL = os.environ.get('REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')

if REDIS_URL:
    if REDIS_URL.startswith('https://'):
        if 'upstash' in REDIS_URL.lower():
            raise RuntimeError(
                "REDIS_URL parece ser la REST API de Upstash (https://). "
                "Flask-Limiter requiere URL Redis nativa (redis:// o rediss://)"
            )
        else:
            raise RuntimeError("REDIS_URL inválida: URLs https:// no soportadas")
    if not (REDIS_URL.startswith('redis://') or REDIS_URL.startswith('rediss://')):
        raise RuntimeError("REDIS_URL debe empezar con 'redis://' o 'rediss://'")
    RATE_LIMIT_STORAGE = REDIS_URL
elif IS_PRODUCTION:
    raise RuntimeError(
        "REDIS_URL requerida en producción para rate limiting. "
        "Configura Upstash Redis: https://upstash.com/"
    )
else:
    RATE_LIMIT_STORAGE = "memory://"


def on_rate_limit_breach(request_limit):
    """Log de violaciones de rate limit."""
    try:
        logger.warning(
            "Rate limit excedido",
            extra={
                "limit": str(request_limit),
                "ip": anonymize_ip(request.remote_addr) if request else "unknown",
                "path": request.path if request else "unknown",
                "security": "rate_limit_breach"
            }
        )
    except Exception:
        pass


REDIS_STORAGE_OPTIONS = {
    "socket_connect_timeout": 2,
    "socket_timeout": 3,
    "retry_on_timeout": True,
    "retry_on_error": [ConnectionError, TimeoutError, OSError],
    "retry": None,
    "max_connections": 10,
    "health_check_interval": 30,
} if REDIS_URL else {}

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=RATE_LIMIT_STORAGE,
    storage_options=REDIS_STORAGE_OPTIONS,
    on_breach=on_rate_limit_breach,
)


def rate_limit(limit_string):
    """Aplica decorador de rate limit."""
    return limiter.limit(limit_string)


# Context Processors
SITE_NAME_RAW = os.environ.get('SITE_NAME', 'VercelDeploy')
SITE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.]+$')
if not SITE_NAME_PATTERN.match(SITE_NAME_RAW) or len(SITE_NAME_RAW) > 50:
    SITE_NAME = 'VercelDeploy'
    if IS_DEVELOPMENT:
        logger.warning(f"SITE_NAME inválido '{SITE_NAME_RAW}', usando default")
else:
    SITE_NAME = SITE_NAME_RAW


@app.context_processor
def inject_globals():
    """Inyecta variables globales en templates."""
    return {
        'current_year': datetime.now(timezone.utc).year,
        'site_name': SITE_NAME,
    }


# Middleware
REQUEST_ID_PATTERN = re.compile(r'^[a-zA-Z0-9-]{1,36}$')
_ALLOWED_HOSTS = None


def get_allowed_hosts():
    """Obtiene lista de hosts permitidos."""
    global _ALLOWED_HOSTS
    if _ALLOWED_HOSTS is not None:
        return _ALLOWED_HOSTS

    allowed_hosts_raw = os.environ.get('ALLOWED_HOSTS', '')
    if allowed_hosts_raw:
        _ALLOWED_HOSTS = [h.strip().lower() for h in allowed_hosts_raw.split(',') if h.strip()]
    else:
        from urllib.parse import urlparse
        try:
            parsed_base = urlparse(BASE_URL)
            _ALLOWED_HOSTS = [parsed_base.netloc.lower()] if parsed_base.netloc else []
        except NameError:
            _ALLOWED_HOSTS = []

        if IS_DEVELOPMENT:
            _ALLOWED_HOSTS.extend(['localhost', '127.0.0.1', 'localhost:5000', '127.0.0.1:5000'])

    return _ALLOWED_HOSTS


@app.before_request
def before_request():
    """Añade ID de request, timing y valida Host header."""
    allowed_hosts = get_allowed_hosts()
    if allowed_hosts:
        request_host = request.host.lower() if request.host else ''
        host_without_port = request_host.split(':')[0]
        if request_host not in allowed_hosts and host_without_port not in allowed_hosts:
            logger.warning("Host header inválido rechazado", extra={"host": request_host[:50]})
            return Response('Bad Request: Invalid Host', status=400)

    user_request_id = request.headers.get('X-Request-ID', '')
    if user_request_id and REQUEST_ID_PATTERN.match(user_request_id):
        g.request_id = user_request_id[:36]
    else:
        g.request_id = str(uuid.uuid4())
    g.request_start = datetime.now(timezone.utc)

    if request.method in ['POST', 'PUT', 'PATCH']:
        content_type = request.content_type or ''
        allowed_types = ['application/json', 'application/x-www-form-urlencoded', 'multipart/form-data']
        if not any(content_type.startswith(t) for t in allowed_types):
            logger.warning("Content-Type no soportado", extra={"content_type": content_type[:50]})
            return Response('Unsupported Media Type', status=415)


@app.after_request
def after_request(response):
    """Añade headers de seguridad y correlación."""
    response.headers['X-Request-ID'] = g.request_id
    response.headers.pop('Server', None)

    security_headers = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()',
        'X-DNS-Prefetch-Control': 'off',
        'X-XSS-Protection': '0',
        'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; manifest-src 'self';",
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Cache-Control': 'no-store, no-cache, must-revalidate, private',
    }
    for header, value in security_headers.items():
        if header not in response.headers:
            response.headers[header] = value

    duration_ms = (datetime.now(timezone.utc) - g.request_start).total_seconds() * 1000
    logger.info(
        f"{request.method} {request.path} {response.status_code}",
        extra={
            "method": request.method,
            "path": request.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "ip": anonymize_ip(request.remote_addr),
        }
    )
    return response


# Health Check
HEALTH_CHECK_TOKEN = os.environ.get('HEALTH_CHECK_TOKEN')

if IS_PRODUCTION and not HEALTH_CHECK_TOKEN:
    raise RuntimeError(
        "HEALTH_CHECK_TOKEN requerido en producción. "
        "Genera uno con: python -c \"import secrets; print(secrets.token_hex(16))\""
    )


def require_health_token(f):
    """Protege endpoints de health con token."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if HEALTH_CHECK_TOKEN:
            provided_token = request.headers.get('X-Health-Token', '')
            if not hmac.compare_digest(provided_token, HEALTH_CHECK_TOKEN):
                return Response('Unauthorized', status=401)
        return f(*args, **kwargs)
    return decorated_function


# Rutas
@app.route('/')
def index():
    """Página principal."""
    return render_template('index.html')


@app.route('/healthz')
@rate_limit("10 per minute")
@require_health_token
def health():
    """Endpoint de health check."""
    checks = {
        'app': 'ok',
        'redis': 'configured' if REDIS_URL else 'not_configured'
    }
    response = Response(
        json.dumps({'status': 'ok', 'checks': checks}),
        status=200,
        mimetype='application/json'
    )
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@app.route('/ready')
@rate_limit("10 per minute")
@require_health_token
def ready():
    """Endpoint de readiness check."""
    checks = {'app': 'ok'}

    if REDIS_URL:
        try:
            from redis import Redis
            redis_client = Redis.from_url(REDIS_URL, socket_connect_timeout=3, socket_timeout=5)
            redis_client.ping()
            checks['redis'] = 'connected'
        except Exception as e:
            checks['redis'] = 'error'
            logger.warning("Redis check fallido", extra={"error": str(e)[:100]})
    else:
        checks['redis'] = 'not_configured'

    response = Response(
        json.dumps({'status': 'ready', 'checks': checks}),
        status=200,
        mimetype='application/json'
    )
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@app.route('/status')
@rate_limit("10 per minute")
def status():
    """Endpoint legacy - redirige a /healthz."""
    response = redirect(url_for('health'), code=301)
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


# Rutas SEO y Seguridad
BASE_URL_RAW = os.environ.get('BASE_URL', 'http://localhost:5000').rstrip('/')
BASE_URL_PATTERN = re.compile(r'^https?://[a-zA-Z0-9][a-zA-Z0-9\-_.]+[a-zA-Z0-9](:[0-9]+)?(/.*)?$')

if not BASE_URL_PATTERN.match(BASE_URL_RAW):
    if IS_PRODUCTION:
        raise RuntimeError(f"BASE_URL inválida: '{BASE_URL_RAW}'")
    BASE_URL = 'http://localhost:5000'
    logger.warning(f"BASE_URL inválida '{BASE_URL_RAW}', usando default")
elif IS_PRODUCTION and BASE_URL_RAW.startswith('http://'):
    raise RuntimeError("BASE_URL debe usar HTTPS en producción")
elif IS_PRODUCTION and BASE_URL_RAW == 'http://localhost:5000':
    raise RuntimeError("BASE_URL no configurada para producción")
else:
    BASE_URL = BASE_URL_RAW

SECURITY_CONTACT_RAW = os.environ.get('SECURITY_CONTACT')
SECURITY_CONTACT = None
SECURITY_CONTACT_MAX_LENGTH = 500

if SECURITY_CONTACT_RAW:
    if len(SECURITY_CONTACT_RAW) > SECURITY_CONTACT_MAX_LENGTH:
        logger.warning("SECURITY_CONTACT muy largo, usando placeholder")
    elif SECURITY_CONTACT_RAW.startswith('mailto:') or SECURITY_CONTACT_RAW.startswith('https://'):
        SECURITY_CONTACT = SECURITY_CONTACT_RAW
    else:
        logger.warning("SECURITY_CONTACT debe empezar con 'mailto:' o 'https://'")

if not SECURITY_CONTACT:
    if IS_PRODUCTION:
        SECURITY_CONTACT = f'{BASE_URL}/.well-known/security.txt#configure-contact'
        if not SECURITY_CONTACT_RAW:
            logger.warning("SECURITY_CONTACT no configurado, usando placeholder")
    else:
        SECURITY_CONTACT = 'https://github.com/YOUR-USERNAME/YOUR-REPO/security/advisories/new'

SECURITY_TXT_EXPIRES_RAW = os.environ.get('SECURITY_TXT_EXPIRES')
if SECURITY_TXT_EXPIRES_RAW:
    try:
        datetime.fromisoformat(SECURITY_TXT_EXPIRES_RAW.replace('Z', '+00:00'))
        SECURITY_TXT_EXPIRES = SECURITY_TXT_EXPIRES_RAW
    except ValueError:
        logger.warning("SECURITY_TXT_EXPIRES inválido, usando auto-calculado")
        expiry_date = datetime.now(timezone.utc) + timedelta(days=365)
        SECURITY_TXT_EXPIRES = expiry_date.strftime('%Y-%m-%dT00:00:00.000Z')
else:
    expiry_date = datetime.now(timezone.utc) + timedelta(days=365)
    SECURITY_TXT_EXPIRES = expiry_date.strftime('%Y-%m-%dT00:00:00.000Z')


@app.route('/robots.txt')
@rate_limit("30 per minute")
def robots():
    """Genera robots.txt dinámicamente."""
    default_disallow = ['/healthz', '/ready', '/status']
    extra_disallow_raw = os.environ.get('ROBOTS_DISALLOW', '')
    extra_disallow = [p.strip() for p in extra_disallow_raw.split(',') if p.strip()]
    all_disallow = list(dict.fromkeys(default_disallow + extra_disallow))
    disallow_lines = '\n'.join(f'Disallow: {path}' for path in all_disallow)

    content = f"""# robots.txt
User-agent: *
Allow: /
{disallow_lines}

Sitemap: {BASE_URL}/sitemap.xml
"""
    response = Response(content, mimetype='text/plain')
    response.headers['Cache-Control'] = 'public, max-age=3600, s-maxage=60'
    return response


@app.route('/sitemap.xml')
@rate_limit("30 per minute")
def sitemap():
    """Genera sitemap.xml dinámicamente."""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{BASE_URL}/</loc>
        <lastmod>{today}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
</urlset>
"""
    response = Response(content, mimetype='application/xml')
    response.headers['Cache-Control'] = 'public, max-age=3600, s-maxage=60'
    return response


@app.route('/.well-known/security.txt')
@rate_limit("30 per minute")
def security_txt():
    """Genera security.txt (RFC 9116)."""
    content = f"""Contact: {SECURITY_CONTACT}
Expires: {SECURITY_TXT_EXPIRES}
Preferred-Languages: es, en
Canonical: {BASE_URL}/.well-known/security.txt
"""
    response = Response(content, mimetype='text/plain')
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


# Ruta de prueba (solo desarrollo)
if IS_DEVELOPMENT:
    @app.route('/test-error')
    def test_error():
        """Endpoint para probar error 500."""
        raise RuntimeError("Error de prueba")


# Manejadores de error
@app.errorhandler(403)
def forbidden_error(error):
    """Página de error 403."""
    logger.warning("Acceso prohibido", extra={"path": request.path, "ip": anonymize_ip(request.remote_addr)})
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def not_found_error(error):
    """Página de error 404."""
    logger.warning("Página no encontrada", extra={"path": request.path, "ip": anonymize_ip(request.remote_addr)})
    return render_template('errors/404.html'), 404


@app.errorhandler(429)
def ratelimit_handler(error):
    """Manejador de rate limit (429)."""
    retry_after_seconds = 60
    logger.warning(
        "Rate limit excedido",
        extra={
            "path": request.path,
            "ip": anonymize_ip(request.remote_addr),
            "user_agent": sanitize_log_string(request.headers.get('User-Agent', 'unknown'), 100),
        }
    )
    response = app.make_response(render_template('errors/429.html'))
    response.status_code = 429
    response.headers['Retry-After'] = str(retry_after_seconds)
    return response


@app.errorhandler(500)
def internal_error(error):
    """Página de error 500."""
    error_id = g.get('request_id', 'unknown')
    log_extra = {
        "error_id": error_id,
        "exception_type": type(error).__name__,
        "path": request.path,
    }
    if IS_DEVELOPMENT:
        exc_info = traceback.format_exc()
        if exc_info != 'NoneType: None\n':
            log_extra["traceback"] = exc_info
    logger.error(f"Error interno (ref: {error_id})", extra=log_extra)
    return render_template('errors/500.html', error_id=error_id), 500


# Entry point
if __name__ == '__main__':
    debug_requested = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    debug_mode = IS_DEVELOPMENT and debug_requested
    port = int(os.environ.get('PORT', 5000))

    if IS_PRODUCTION and debug_requested:
        logger.error("FLASK_DEBUG=true IGNORADO en producción")

    if debug_mode:
        logger.info("Iniciando en modo DEBUG")
        app.run(debug=True, host='127.0.0.1', port=port)
    else:
        logger.info("Iniciando en modo PRODUCCIÓN")
        app.run(debug=False, host='127.0.0.1', port=port)
