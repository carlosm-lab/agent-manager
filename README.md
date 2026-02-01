# Google Antigravity Manager

Aplicación web para gestionar múltiples cuentas de Google Antigravity con control manual de cuotas (Gemini/Anthropic), contadores automáticos, rotación inteligente y métricas de uso.

## Stack Tecnológico

- **Frontend**: HTML + Tailwind CSS + JavaScript Vanilla
- **Backend**: Python Flask + Jinja2
- **Base de Datos**: Supabase (PostgreSQL)
- **Despliegue**: Vercel (Serverless Functions)

## Requisitos del Sistema

- **Python**: 3.9 o superior
- **Node.js**: 16+ (solo para Vercel CLI)
- **Base de datos**: PostgreSQL (Supabase)

## Características Principales

- **Gestión de cuentas**: Alta, baja y modificación de cuentas Google Antigravity
- **Control de cuotas**: Seguimiento de cuotas por proveedor (Anthropic/Gemini)
- **Rotación inteligente**: Selección automática de la mejor cuenta disponible
- **Seguimiento de sesiones**: Cronómetro de tiempo de uso y estadísticas
- **Seguridad**: Bloqueo por PIN y encriptación de datos sensibles
- **Modo usuario único**: Optimizado para uso personal

## Seguridad

### Bloqueo por PIN
La aplicación está protegida por un PIN de acceso. Al iniciar, se muestra una pantalla de bloqueo que requiere el PIN correcto para acceder.

- Rate limiting: 5 intentos por minuto para prevenir fuerza bruta
- Comparación timing-safe para prevenir ataques de temporización
- Sesión persistente una vez desbloqueado

### Generación del PIN
Para generar el hash de tu PIN:

```bash
python generate_pin.py
```

Copia el resultado `ACCESS_PIN_HASH=...` a tu archivo `.env` o a las variables de entorno de Vercel.

### Encriptación de Datos
Los datos sensibles se encriptan usando Fernet (AES-128-CBC) antes de almacenarse.

## Estructura del Proyecto

```
app/
├── api/
│   └── index.py              # Entry point para Vercel
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── config.py             # Configuración
│   ├── models.py             # SQLAlchemy models
│   ├── auth/                 # Autenticación (reservado)
│   ├── accounts/             # Gestión de cuentas
│   ├── quotas/               # Gestión de cuotas
│   ├── sessions/             # Tracking de sesiones
│   ├── dashboard/            # Dashboard principal
│   └── utils/                # Utilidades
│       ├── decorators.py     # Decoradores (login_required, rate_limit)
│       ├── encryption.py     # Encriptación y hashing de PIN
│       └── rotation.py       # Lógica de rotación inteligente
├── templates/                # Templates Jinja2
├── static/                   # Assets estáticos
│   ├── css/                 # Estilos CSS
│   └── js/                  # JavaScript (dashboard, time-manager, rotation)
├── migrations/               # SQL migrations
├── requirements.txt
├── vercel.json
├── generate_pin.py           # Generador de hash para PIN
├── reset_db.py               # Script para reiniciar base de datos
└── .env.example
```

## Configuración

### 1. Clonar y Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env

# Editar con tus credenciales
```

### Variables de Entorno

> [!CAUTION]
> **Nunca subas el archivo `.env` real a Git.** Contiene credenciales sensibles. Las variables deben configurarse directamente en Vercel.

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `SUPABASE_URL` | URL de tu proyecto Supabase | Sí |
| `SUPABASE_DB_URL` | URL de conexión PostgreSQL | Sí |
| `SECRET_KEY` | Clave secreta para Flask y encriptación (mín. 32 caracteres) | Sí |
| `JWT_SECRET` | Clave secreta para tokens JWT | Sí |
| `JWT_EXPIRATION_HOURS` | Horas de validez del token JWT (default: 24) | No |
| `ACCESS_PIN_HASH` | Hash SHA-256 del PIN de acceso | Sí (producción) |
| `ALLOWED_ORIGINS` | Orígenes CORS permitidos (separados por coma) | Sí (producción) |
| `FLASK_ENV` | Entorno: development o production | No |
| `DEBUG_MODE` | Habilitar modo debug (solo dev local) | No |

### 2. Configurar Base de Datos en Supabase

1. Ir a [Supabase](https://supabase.com) y crear un nuevo proyecto
2. Las tablas se crean automáticamente al iniciar la aplicación (`db.create_all()`)
3. SQLAlchemy maneja el schema basado en los modelos definidos en `app/models.py`

### 3. Generar PIN de Acceso

```bash
python generate_pin.py
```

Copia el hash generado a tu `.env` como `ACCESS_PIN_HASH`.

### 4. Desarrollo Local

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno (Windows)
.\venv\Scripts\activate

# Activar entorno (Linux/Mac)
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar servidor de desarrollo
python api/index.py
```

La aplicación estará disponible en `http://localhost:5000`

> **Nota**: En desarrollo local, si no se configura `ACCESS_PIN_HASH`, el PIN por defecto es `admin`.

## Despliegue en Vercel

### Opción 1: CLI de Vercel

```bash
# Instalar Vercel CLI
npm i -g vercel

# Login
vercel login

# Desplegar
vercel

# Configurar variables de entorno
vercel env add SUPABASE_URL
vercel env add SUPABASE_DB_URL
vercel env add SECRET_KEY
vercel env add ACCESS_PIN_HASH
vercel env add ALLOWED_ORIGINS

# Desplegar a producción
vercel --prod
```

### Opción 2: Desde GitHub

1. Conectar repositorio en [Vercel Dashboard](https://vercel.com/dashboard)
2. Configurar variables de entorno en Settings > Environment Variables
3. Desplegar

## Lógica de Rotación Inteligente

El sistema implementa rotación automática de cuentas siguiendo estas reglas:

1. **Prioridad Anthropic**: Siempre se intenta usar Anthropic primero
2. **Fallback a Gemini**: Si no hay Anthropic, se ofrece usar Gemini
3. **Esperar opción**: El usuario puede elegir esperar a que Anthropic se reinicie
4. **Rotación automática**: Al agotar una cuota, se selecciona automáticamente la mejor cuenta disponible

```
Usuario marca cuota agotada
        ↓
Ingresa fecha/hora de reinicio
        ↓
Sistema cierra sesión actual
        ↓
Busca cuenta con Anthropic disponible
        ↓
¿Encontrada? → Sí → Iniciar sesión automáticamente
        ↓ No
¿Hay Gemini? → Sí → Preguntar: ¿Usar Gemini o esperar?
        ↓ No
Mostrar contador hasta próximo reinicio
```

## Manejo de Tiempo

**Principio fundamental**: Nunca guardar contadores, solo timestamps.

### Lo que se guarda en la base de datos:
- `inicio`: Timestamp de inicio de sesión
- `fin`: Timestamp de fin de sesión
- `proximo_reset`: Timestamp de próximo reinicio de cuota
- `agotada_en`: Timestamp de cuando se agotó la cuota

### Lo que calcula el frontend:
```javascript
// Tiempo en sesión actual
const tiempoSesion = Date.now() - new Date(inicio).getTime();

// Tiempo hasta próximo reinicio
const tiempoHastaReset = new Date(proximo_reset).getTime() - Date.now();
```

### Persistencia en recargas:
- Los timestamps se guardan en `LocalStorage`
- Al recargar la página, se restaura el timer desde el timestamp guardado
- Los contadores sobreviven cierres del navegador

## Conexión a Supabase

La aplicación usa SQLAlchemy para conectarse a PostgreSQL de Supabase:

```python
# En app/config.py
SQLALCHEMY_DATABASE_URI = os.environ.get('SUPABASE_DB_URL')
```

La URL de conexión tiene el formato:
```
postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres
```

Puedes encontrar esta URL en:
Supabase Dashboard > Settings > Database > Connection String

## API Endpoints

### Dashboard
- `GET /` - Dashboard principal
- `GET /lock` - Pantalla de bloqueo
- `POST /unlock` - Desbloquear con PIN
- `GET /logout` - Bloquear aplicación

### Cuentas
- `GET /api/accounts` - Listar cuentas
- `POST /api/accounts` - Crear cuenta
- `GET /api/accounts/<id>` - Obtener cuenta
- `PUT /api/accounts/<id>` - Actualizar cuenta
- `DELETE /api/accounts/<id>` - Eliminar cuenta
- `GET /api/accounts/summary` - Resumen de cuentas

### Cuotas
- `GET /api/quotas/<account_id>` - Obtener cuotas
- `POST /api/quotas/<account_id>/<provider>/exhausted` - Marcar agotada
- `POST /api/quotas/<account_id>/<provider>/reset` - Reiniciar cuota
- `GET /api/quotas/next-reset/<provider>` - Próximo reinicio

### Sesiones
- `POST /api/sessions/start` - Iniciar sesión
- `POST /api/sessions/end` - Terminar sesión
- `GET /api/sessions/active` - Obtener sesión activa
- `POST /api/sessions/rotate` - Rotar cuenta
- `GET /api/sessions/history` - Historial
- `GET /api/sessions/stats` - Estadísticas

## CSS: 100% Responsive

La aplicación usa **exclusivamente unidades relativas**:

| Unidad | Uso |
|--------|-----|
| `rem` | Espaciado, tipografía |
| `em` | Espaciado relativo al contexto |
| `%` | Anchos relativos |
| `vh/vw` | Viewport units |
| `fr` | CSS Grid |

**PROHIBIDO**: `px` en cualquier contexto

## Checklist Pre-Producción

> [!IMPORTANT]
> Antes de desplegar a producción, verifica los siguientes puntos:

- [ ] Generar nueva `SECRET_KEY` única para producción
- [ ] Generar nueva `JWT_SECRET` única para producción
- [ ] Configurar `ALLOWED_ORIGINS` con el dominio real de Vercel
- [ ] Verificar `FLASK_ENV=production` en Vercel
- [ ] Confirmar `DEBUG_MODE=0` en Vercel
- [ ] Generar nuevo `ACCESS_PIN_HASH` para producción con `python generate_pin.py`
- [ ] Cambiar contraseña de Supabase si fue expuesta
- [ ] Revisar logs después del primer despliegue
- [ ] Probar flujo de login con PIN

## Limitaciones Conocidas

- **Rate Limiting**: Usa almacenamiento en memoria, que no persiste entre invocaciones de función serverless en Vercel.
- **Lockout Progresivo**: El bloqueo de intentos fallidos también se almacena en memoria. Para alta seguridad, considerar migrar a Redis/Upstash.

## Licencia

MIT License

## Contribuir

1. Fork el repositorio
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar nueva funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request
