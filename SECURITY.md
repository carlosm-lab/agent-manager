# Política de Seguridad - VercelDeploy

## Reportar Vulnerabilidades

Si encuentra una vulnerabilidad de seguridad, por favor repórtela responsablemente:

- **GitHub**: Usar [Security Advisories](../../security/advisories/new)
- **Respuesta esperada**: 48 horas

## Content Security Policy (CSP)

Este proyecto implementa una CSP **muy restrictiva** por diseño:

### ✅ Permitido
- Scripts desde el mismo origen (`'self'`)
- Estilos desde el mismo origen (`'self'`)
- Fuentes locales
- Imágenes locales
- Conexiones al mismo origen

### ❌ Bloqueado
- Scripts inline (sin `'unsafe-inline'`)
- Estilos inline
- Google Analytics, Plausible, u otros analytics de terceros
- Widgets de chat (Crisp, Intercom, Zendesk)
- CDNs externos
- Iframes externos
- Data URIs para imágenes

### Modificar CSP

Si necesita añadir scripts/estilos externos:

1. Buscar `Content-Security-Policy` en `app.py`
2. Buscar `Content-Security-Policy` en `vercel.json`
3. Añadir el dominio específico, ejemplo:
   ```
   script-src 'self' https://www.googletagmanager.com;
   ```

## HSTS

El header HSTS está configurado con:
- `max-age=31536000` (1 año)
- `includeSubDomains`

Para añadir preload:
1. Registrar dominio en https://hstspreload.org/
2. Esperar confirmación
3. Agregar `preload` al header

## Rate Limiting

- **Desarrollo local**: Flask-Limiter con memoria
- **Producción (Vercel)**: 
  - **OBLIGATORIO**: Redis (Upstash) configurado via `REDIS_URL`
  - La aplicación **FALLARÁ al iniciar** si no está configurado

🚨 **CRÍTICO: Sin `REDIS_URL` configurado, la aplicación no iniciará en producción.**

## Variables de Entorno Requeridas

| Variable | Producción | Descripción |
|----------|------------|-------------|
| `SECRET_KEY` | ✅ **Obligatorio** | Clave criptográfica de 64 caracteres hex |
| `REDIS_URL` | ✅ **Obligatorio** | URL de Redis para rate limiting |
| `HEALTH_CHECK_TOKEN` | ✅ **Obligatorio** | Token para proteger /healthz y /ready |
| `ALLOWED_HOSTS` | ⚠️ Recomendado | Hosts permitidos (auto-detecta desde BASE_URL si no se configura) |

## Rotación de Tokens de Seguridad

### Rotación de HEALTH_CHECK_TOKEN

1. Generar nuevo token: `python -c "import secrets; print(secrets.token_hex(16))"`
2. Actualizar variable en Vercel Dashboard > Settings > Environment Variables
3. Redesplegar la aplicación
4. Actualizar monitoreo/uptime checks con el nuevo token

**Nota**: No hay downtime durante la rotación. El nuevo token toma efecto inmediatamente después del redeploy.

### Rotación de SECRET_KEY

⚠️ **PRECAUCIÓN**: Rotar SECRET_KEY invalidará todas las sesiones activas.

1. Generar nueva clave: `python -c "import secrets; print(secrets.token_hex(32))"`
2. Actualizar variable en Vercel Dashboard
3. Redesplegar la aplicación
4. Los usuarios deberán iniciar sesión nuevamente (si hay autenticación)

### Rotación de REDIS_URL

La rotación de credenciales Redis afecta el rate limiting pero no causa pérdida de datos críticos.

1. Crear nueva base de datos Redis en Upstash (o regenerar password en la existente)
2. Copiar la nueva Redis URL
3. Actualizar `REDIS_URL` en Vercel Dashboard > Settings > Environment Variables
4. Redesplegar la aplicación

**Impacto**:
- Los contadores de rate limiting se reinician (comportamiento esperado)
- Usuarios podrían experimentar límites "frescos" temporalmente
- No hay downtime durante la rotación

**Frecuencia recomendada**: Cada 6-12 meses o inmediatamente tras sospecha de compromiso.

## Host Header Validation

La aplicación valida el header `Host` para prevenir ataques de host header injection:

- En producción, solo se permiten hosts configurados en `ALLOWED_HOSTS` o derivados de `BASE_URL`
- En desarrollo, localhost y 127.0.0.1 siempre están permitidos
- Requests con Host no válido reciben HTTP 400

## Seguridad en Uploads (cuando se implementen)

> ⚠️ **IMPORTANTE:** Esta sección describe requisitos futuros.

Cuando se añadan endpoints de upload de archivos:

1. **Validar MIME type** del archivo, no confiar en extensión
2. **Limitar tipos permitidos** (whitelist, no blacklist)
3. **Escanear contenido** de archivos para detectar SVG con scripts
4. **Almacenar fuera de webroot** o en bucket S3/GCS
5. **Generar nombres aleatorios** para evitar path traversal
6. **Actualizar CSP** si se sirven imágenes de dominio externo

## Cache del Service Worker

### Invalidación Manual

Para forzar actualización en todos los usuarios:

1. Abrir `/static/sw.js`
2. Incrementar versión en `CACHE_NAME`: `deploy-template-v10` → `v11`
3. Hacer deploy

### Automática (Recomendado)

Usar variable de entorno `VERCEL_GIT_COMMIT_SHA` en el build:
- El SW incluye timestamp del deploy
- Cache se invalida automáticamente en cada deploy

## Dependencias JavaScript Estáticas

### lottie.min.js (Monitoreo Manual Requerido)

**Versión actual**: 5.12.2  
**SHA256**: `a0757321f974527bda3cc2593bf56cc7ffe4578421249ced6ae49ffb1c529f90`  
**Fuente**: https://cdnjs.cloudflare.com/ajax/libs/lottie-web/5.12.2/lottie.min.js

> ⚠️ **IMPORTANTE**: Este archivo está hosteado localmente y NO se actualiza automáticamente.

**Procedimiento de actualización trimestral**:

1. Revisar CVEs en https://security.snyk.io/package/npm/lottie-web
2. Si hay vulnerabilidades:
   - Descargar nueva versión desde CDNJS
   - Recalcular SHA256: `Get-FileHash static/js/lottie.min.js -Algorithm SHA256`
   - Actualizar hash en `.github/workflows/ci.yml`
   - Actualizar este documento
3. Si no hay vulnerabilidades: documentar revisión con fecha

**Última revisión**: 2026-01-22 ✅ Sin vulnerabilidades conocidas

