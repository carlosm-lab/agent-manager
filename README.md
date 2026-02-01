# Deploy Template - Flask

Plantilla profesional para pre-desplegar en Vercel y reservar dominios.

![Preview](screen.png)

## Características de Seguridad

- ✅ SECRET_KEY obligatoria en producción (fallo explícito si falta)
- ✅ Headers HTTP seguros (CSP, HSTS, X-Frame-Options)
- ✅ Rate limiting en desarrollo local (Flask-Limiter)
- ✅ Logging estructurado JSON con request IDs y nivel configurable
- ✅ Anonimización IP compatible con GDPR
- ✅ Manejo de errores sin filtrar información (con ID de referencia)
- ✅ CSRF preparado para formularios futuros
- ✅ PWA con Service Worker (Network-First para contenido dinámico)
- ✅ Página offline.html para PWA
- ✅ URLs dinámicas para SEO files (robots.txt, sitemap.xml, security.txt)

## Rate Limiting en Producción

En desarrollo local, Flask-Limiter provee rate limiting en memoria. **En producción (Vercel)**, Redis es **obligatorio**:

> ⚠️ **La aplicación FALLARÁ al iniciar si `REDIS_URL` no está configurado en producción.**

### Configuración con Upstash (Gratis)
1. Crear cuenta en [upstash.com](https://upstash.com/)
2. Crear base de datos Redis
3. Copiar "Redis URL" (formato: `redis://default:xxx@xxx.upstash.io:6379`)
4. Agregar como `REDIS_URL` en Vercel Dashboard

## Estructura

```
deploy/
├── app.py                  # Aplicación Flask
├── conftest.py             # Configuración pytest
├── requirements.txt        # Dependencias producción
├── requirements-dev.txt    # Dependencias desarrollo
├── runtime.txt             # Versión Python para Vercel (3.12)
├── vercel.json             # Configuración Vercel + headers
├── pytest.ini              # Configuración pytest
├── .editorconfig           # Configuración del editor
├── README.md               # Esta documentación
├── SECURITY.md             # Documentación de seguridad
├── api/
│   └── index.py            # Entry point Vercel
├── static/
│   ├── css/
│   │   ├── main.css        # Estilos principales
│   │   ├── tailwind.css    # Utilidades Tailwind
│   │   ├── fonts.css       # Definición de fuentes
│   │   └── offline.css     # Estilos página offline
│   ├── js/
│   │   ├── main.js         # JavaScript principal
│   │   ├── lottie.min.js   # Librería animaciones
│   │   ├── robot.js        # Animación robot
│   │   ├── robot-animation.json  # Datos animación
│   │   ├── offline.js      # Lógica página offline
│   │   ├── error-handlers.js    # Manejo errores
│   │   └── sw-register.js  # Registro Service Worker
│   ├── icons/
│   │   ├── icon-192.png    # Icono PWA 192x192
│   │   └── icon-512.png    # Icono PWA 512x512
│   ├── fonts/              # Archivos de fuentes
│   ├── favicon.svg         # Favicon
│   ├── manifest.json       # PWA manifest
│   ├── sw.js               # Service Worker
│   ├── humans.txt          # Créditos humanos
│   └── offline.html        # Página offline PWA
├── templates/
│   ├── base.html           # Plantilla base
│   ├── index.html          # Página principal
│   ├── components/
│   │   ├── animated_gears.html   # Animación engranajes
│   │   ├── footer.html     # Pie de página
│   │   ├── robot.html      # Componente robot
│   │   ├── status_panel.html    # Panel de estado
│   │   └── svg_defs.html   # Definiciones SVG
│   └── errors/
│       ├── error_base.html # Base para errores
│       ├── 403.html        # Error 403 Prohibido
│       ├── 404.html        # Error 404 No encontrado
│       ├── 429.html        # Error 429 Rate limit
│       └── 500.html        # Error 500 Interno
├── tests/                   # Tests del proyecto
└── .github/
    ├── dependabot.yml      # Configuración Dependabot
    └── workflows/
        └── ci.yml          # Pipeline CI/CD
```

## Variables de Entorno

| Variable | Producción | Descripción |
|----------|------------|-------------|
| `SECRET_KEY` | ✅ **Obligatorio** | Clave para firmar sesiones |
| `REDIS_URL` | ✅ **Obligatorio** | URL de Redis para rate limiting |
| `HEALTH_CHECK_TOKEN` | ✅ **Obligatorio** | Token para proteger `/healthz` |
| `BASE_URL` | ⚠️ **Recomendado** | URL base para SEO files (robots.txt, sitemap.xml) |
| `SITE_NAME` | ❌ Opcional | Nombre del sitio (default: VercelDeploy) |
| `SECURITY_CONTACT` | ❌ Opcional | URL de contacto para security.txt |
| `FLASK_DEBUG` | ❌ Opcional | Modo debug (default: false) |
| `LOG_LEVEL` | ❌ Opcional | Nivel de logging (default: INFO) |

### Generar Tokens

```bash
# SECRET_KEY (64 caracteres hex)
python -c "import secrets; print(secrets.token_hex(32))"

# HEALTH_CHECK_TOKEN (32 caracteres hex)
python -c "import secrets; print(secrets.token_hex(16))"
```

## Desarrollo Local

```bash
# 1. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# 2. Instalar dependencias (desarrollo)
pip install -r requirements-dev.txt

# 3. Crear .env.local (ignorado por git)
echo "SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')" > .env.local

# 4. Ejecutar
python app.py
```

## Despliegue en Vercel

### 1. Configurar Variables en Vercel

Dashboard > Settings > Environment Variables:
- `SECRET_KEY` = (valor generado)

### 2. Desplegar

```bash
vercel
```

## Testing

```bash
# Ejecutar tests
pytest tests/ -v

# Con coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Auditoría de dependencias
pip-audit
```

## Endpoints

| Ruta | Descripción |
|------|-------------|
| `/` | Página principal |
| `/healthz` | **Liveness check** - Indica si la app está viva (protegido con token) |
| `/ready` | **Readiness check** - Verifica conectividad Redis real (protegido con token) |
| `/status` | Redirige a /healthz (deprecated) |

### Diferencia entre `/healthz` y `/ready`

- **`/healthz` (Liveness)**: Retorna OK si la aplicación está ejecutándose. Útil para que orquestadores reinicien pods muertos.
- **`/ready` (Readiness)**: Retorna OK solo si Redis está conectado. Útil para load balancers (no enviar tráfico hasta que la app puede procesar requests).

> 💡 **Recomendación**: Usar `/healthz` para uptime monitoring, `/ready` para load balancer health checks.

### Cache de Archivos Estáticos

Los archivos en `/static/*` tienen cache agresivo (`Cache-Control: s-maxage=31536000`). Para forzar actualización:

1. **Método recomendado**: Cambiar el contenido del archivo (Vercel detecta cambios automáticamente)
2. **Cache del Service Worker**: Incrementar `CACHE_VERSION` en `sw.js` (el CI actualiza `DEPLOY_HASH` automáticamente)

---

## ⚠️ Pre-Launch Checklist

> **Importante:** Antes de desplegar a producción con dominio real:

- [x] **robots.txt**: Configurado con `Allow: /` ✅
- [x] **meta robots**: Configurado con `index, follow` ✅
- [x] **sitemap.xml**: Configurado con entrada válida ✅
- [x] **security.txt**: Actualizado con dominio real ✅
- [x] **offline.html**: Página PWA offline creada ✅
- [x] **SECRET_KEY**: Configurar en Vercel Dashboard ✅
- [x] **REDIS_URL**: Configurar en Vercel Dashboard ✅
- [x] **HEALTH_CHECK_TOKEN**: Configurar en Vercel Dashboard ✅
- [x] **BASE_URL**: Configurar en Vercel Dashboard ✅

> **Nota:** Cada instancia de este template requiere configurar las variables de entorno propias.

---

## Seguridad

Ver [SECURITY.md](SECURITY.md) para documentación detallada sobre:
- Content Security Policy (CSP) y cómo modificarlo
- HSTS y proceso de preload
- Rate limiting en producción

---

## Licencia

MIT
