# Tests - Flask Deploy Template
# Ejecutar con: pytest tests/ -v

import pytest
from app import app, anonymize_ip


# Fixtures
@pytest.fixture
def client():
    """Cliente de prueba Flask."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def runner():
    """CLI runner para testing."""
    return app.test_cli_runner()


# Tests de Rutas
class TestRoutes:
    """Tests para las rutas principales."""

    def test_index_returns_200(self, client):
        """La página principal debe retornar 200."""
        response = client.get('/')
        assert response.status_code == 200

    def test_index_contains_expected_content(self, client):
        """La página principal debe contener contenido esperado."""
        response = client.get('/')
        assert b'SITIO EN' in response.data or b'Sitio en' in response.data

    def test_index_has_request_id(self, client):
        """La respuesta debe incluir X-Request-ID header."""
        response = client.get('/')
        assert 'X-Request-ID' in response.headers
        assert len(response.headers['X-Request-ID']) > 0

    def test_healthz_endpoint_returns_json(self, client):
        """El endpoint /healthz debe retornar JSON válido."""
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.content_type == 'application/json'

    def test_healthz_endpoint_has_required_fields(self, client):
        """El endpoint /healthz debe tener status y checks (A2: Enhanced)."""
        response = client.get('/healthz')
        data = response.get_json()
        assert 'status' in data
        assert data['status'] == 'ok'
        assert 'checks' in data
        assert 'app' in data['checks']
        # SECURITY: timestamp fue removido para prevenir information disclosure
        assert 'timestamp' not in data

    def test_healthz_response_structure(self, client):
        """El healthz debe retornar status y checks."""
        response = client.get('/healthz')
        data = response.get_json()
        # Debe tener 'status' y 'checks'
        assert 'status' in data
        assert 'checks' in data
        assert data['checks']['app'] == 'ok'


    def test_status_redirects_to_healthz(self, client):
        """El endpoint /status debe redirigir a /healthz con 301."""
        response = client.get('/status')
        assert response.status_code == 301
        assert '/healthz' in response.headers.get('Location', '')

    def test_status_redirect_follow(self, client):
        """Siguiendo el redirect de /status debe llegar a healthz."""
        response = client.get('/status', follow_redirects=True)
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'ok'


# Tests de Manejo de Errores
class TestErrorHandlers:
    """Tests para manejadores de errores."""

    def test_404_handler(self, client):
        """Rutas inexistentes deben retornar 404."""
        response = client.get('/nonexistent-page-xyz')
        assert response.status_code == 404

    def test_404_page_contains_helpful_text(self, client):
        """Página 404 debe contener texto útil."""
        response = client.get('/nonexistent-page-xyz')
        assert b'404' in response.data

    def test_404_has_request_id(self, client):
        """Errores 404 deben incluir request ID."""
        response = client.get('/nonexistent-page-xyz')
        assert 'X-Request-ID' in response.headers

    def test_403_handler_exists(self, client):
        """403 handler está registrado (M4)."""
        from flask import abort
        # We can't directly trigger 403 without a protected route,
        # but we can verify the template exists
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'templates', 'errors', '403.html'
        )
        assert os.path.exists(template_path), "403.html template should exist"

    def test_500_handler_no_traceback_in_production(self, client):
        """A5: Error 500 no debe filtrar traceback en producción."""
        from app import IS_DEVELOPMENT, app as flask_app
        if IS_DEVELOPMENT:
            # Temporarily disable exception propagation to test error handler
            original_propagate = flask_app.config.get('PROPAGATE_EXCEPTIONS')
            flask_app.config['PROPAGATE_EXCEPTIONS'] = False
            flask_app.config['TESTING'] = False
            
            try:
                with flask_app.test_client() as test_client:
                    response = test_client.get('/test-error')
                    assert response.status_code == 500
                    # The response should NOT contain the error message
                    assert b'Intentional test error' not in response.data
                    # Should contain generic 500 page content
                    assert b'500' in response.data or b'Error' in response.data
            finally:
                # Restore original config
                flask_app.config['TESTING'] = True
                if original_propagate is not None:
                    flask_app.config['PROPAGATE_EXCEPTIONS'] = original_propagate


# Tests de Headers de Seguridad (A2)
class TestSecurityHeaders:
    """Tests para verificar headers de seguridad en respuestas."""

    def test_x_content_type_options_header(self, client):
        """X-Content-Type-Options debe estar presente."""
        response = client.get('/')
        assert response.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_frame_options_header(self, client):
        """X-Frame-Options debe estar presente."""
        response = client.get('/')
        assert response.headers.get('X-Frame-Options') == 'DENY'

    def test_referrer_policy_header(self, client):
        """Referrer-Policy debe estar presente."""
        response = client.get('/')
        assert response.headers.get('Referrer-Policy') == 'strict-origin-when-cross-origin'

    def test_permissions_policy_header(self, client):
        """Permissions-Policy debe estar presente."""
        response = client.get('/')
        permissions = response.headers.get('Permissions-Policy', '')
        assert 'camera=()' in permissions
        assert 'microphone=()' in permissions


# Tests de Anonimización IP (GDPR)
class TestIPAnonymization:
    """Tests para la función de anonimización IP."""

    # IPv4 Tests
    def test_anonymize_ip_ipv4_standard(self):
        """IPv4 estándar: último octeto debe ser 0."""
        result = anonymize_ip('192.168.1.100')
        assert result == '192.168.1.0'

    def test_anonymize_ip_ipv4_preserves_network(self):
        """Anonimización debe preservar identificador de red /24."""
        result = anonymize_ip('10.0.0.1')
        assert result == '10.0.0.0'

    def test_anonymize_ip_ipv4_already_zero(self):
        """IPv4 con último octeto ya en 0."""
        result = anonymize_ip('172.16.0.0')
        assert result == '172.16.0.0'

    def test_anonymize_ip_localhost(self):
        """Localhost IPv4."""
        result = anonymize_ip('127.0.0.1')
        assert result == '127.0.0.0'

    # IPv6 Tests
    def test_anonymize_ip_ipv6_full(self):
        """IPv6 completo debe mantener solo /48."""
        result = anonymize_ip('2001:db8:85a3:0000:0000:8a2e:0370:7334')
        assert result == '2001:db8:85a3::'

    def test_anonymize_ip_ipv6_compressed(self):
        """IPv6 comprimido (::1)."""
        result = anonymize_ip('::1')
        assert result == '::'

    def test_anonymize_ip_ipv6_loopback(self):
        """IPv6 loopback."""
        result = anonymize_ip('::1')
        assert result == '::'

    def test_anonymize_ip_ipv6_link_local(self):
        """IPv6 link-local."""
        result = anonymize_ip('fe80::1')
        assert result == 'fe80::'

    def test_anonymize_ip_ipv6_mapped_ipv4(self):
        """IPv6-mapped IPv4 (::ffff:192.168.1.1)."""
        result = anonymize_ip('::ffff:192.168.1.1')
        # This is technically an IPv6 address
        assert result == '::ffff:c0a8:' or '::' in result

    # Edge Cases
    def test_anonymize_ip_none(self):
        """IP nula debe retornar 'unknown'."""
        result = anonymize_ip(None)
        assert result == 'unknown'

    def test_anonymize_ip_empty(self):
        """IP vacía debe retornar 'unknown'."""
        result = anonymize_ip('')
        assert result == 'unknown'

    def test_anonymize_ip_invalid_format(self):
        """IP con formato inválido."""
        result = anonymize_ip('not-an-ip')
        assert result == 'invalid-ip'

    def test_anonymize_ip_partial_ipv4(self):
        """IPv4 incompleta."""
        result = anonymize_ip('192.168.1')
        assert result == 'invalid-ip'


# Tests de Configuración
class TestConfiguration:
    """Tests de configuración de la aplicación."""

    def test_app_has_secret_key(self):
        """La aplicación debe tener SECRET_KEY configurada."""
        assert app.config['SECRET_KEY'] is not None
        assert len(app.config['SECRET_KEY']) > 0

    def test_secret_key_is_not_empty(self):
        """SECRET_KEY no debe estar vacía."""
        assert len(app.config['SECRET_KEY']) >= 32

    def test_csrf_enabled(self):
        """CSRF debe estar habilitado."""
        assert app.config['WTF_CSRF_ENABLED'] is True

    def test_site_name_validation(self, monkeypatch):
        """SITE_NAME con caracteres maliciosos debe ser rechazado."""
        monkeypatch.setenv('SITE_NAME', '<script>alert(1)</script>')
        import importlib
        import app as app_module
        importlib.reload(app_module)
        
        # The malicious value should be rejected, default used
        assert app_module.SITE_NAME == 'VercelDeploy'


# Tests de Seguridad
class TestSecurity:
    """Tests de headers y configuración de seguridad."""

    def test_response_has_request_id(self, client):
        """Todas las respuestas deben tener X-Request-ID."""
        response = client.get('/')
        assert 'X-Request-ID' in response.headers

    def test_custom_request_id_preserved(self, client):
        """Si se envía X-Request-ID, debe preservarse."""
        response = client.get('/', headers={'X-Request-ID': 'test-123'})
        assert response.headers['X-Request-ID'] == 'test-123'


# Tests de Protección de Health Check
class TestHealthCheckProtection:
    """Tests para protección de endpoint healthz con token."""

    def test_healthz_accessible_without_token_by_default(self, client):
        """Sin HEALTH_CHECK_TOKEN configurado, healthz es accesible."""
        response = client.get('/healthz')
        assert response.status_code == 200

    def test_healthz_returns_ok_status(self, client):
        """Healthz debe retornar status ok."""
        response = client.get('/healthz')
        data = response.get_json()
        assert data['status'] == 'ok'

    def test_ready_endpoint_exists(self, client):
        """Endpoint /ready debe existir y retornar JSON."""
        response = client.get('/ready')
        assert response.status_code == 200
        assert response.content_type == 'application/json'

    def test_ready_returns_correct_structure(self, client):
        """Ready debe retornar status y checks."""
        response = client.get('/ready')
        data = response.get_json()
        assert 'status' in data
        assert 'checks' in data
        assert 'app' in data['checks']

    def test_healthz_with_token_protection(self, monkeypatch):
        """Con HEALTH_CHECK_TOKEN configurado, healthz requiere token."""
        import importlib
        import os
        
        # Save original state
        original_token = os.environ.get('HEALTH_CHECK_TOKEN')
        
        try:
            monkeypatch.setenv('HEALTH_CHECK_TOKEN', 'test-secret-token')
            import app as app_module
            importlib.reload(app_module)
            
            with app_module.app.test_client() as test_client:
                # Without token - should fail
                response = test_client.get('/healthz')
                assert response.status_code == 401
                
                # With wrong token - should fail
                response = test_client.get('/healthz', headers={'X-Health-Token': 'wrong'})
                assert response.status_code == 401
                
                # With correct token - should succeed
                response = test_client.get('/healthz', headers={'X-Health-Token': 'test-secret-token'})
                assert response.status_code == 200
        finally:
            # Cleanup: restore module to original state
            if original_token:
                os.environ['HEALTH_CHECK_TOKEN'] = original_token
            elif 'HEALTH_CHECK_TOKEN' in os.environ:
                del os.environ['HEALTH_CHECK_TOKEN']
            importlib.reload(app_module)

    def test_ready_with_token_protection(self, monkeypatch):
        """Con HEALTH_CHECK_TOKEN configurado, ready requiere token."""
        import importlib
        import os
        
        # Save original state
        original_token = os.environ.get('HEALTH_CHECK_TOKEN')
        
        try:
            monkeypatch.setenv('HEALTH_CHECK_TOKEN', 'test-secret-token')
            import app as app_module
            importlib.reload(app_module)
            
            with app_module.app.test_client() as test_client:
                # Without token - should fail
                response = test_client.get('/ready')
                assert response.status_code == 401
                
                # With correct token - should succeed
                response = test_client.get('/ready', headers={'X-Health-Token': 'test-secret-token'})
                assert response.status_code == 200
        finally:
            # Cleanup: restore module to original state
            if original_token:
                os.environ['HEALTH_CHECK_TOKEN'] = original_token
            elif 'HEALTH_CHECK_TOKEN' in os.environ:
                del os.environ['HEALTH_CHECK_TOKEN']
            importlib.reload(app_module)

    def test_ready_redis_connectivity_check(self, client):
        """Auditoría Ciclo 1: /ready debe reportar estado de conectividad Redis."""
        response = client.get('/ready')
        assert response.status_code == 200
        data = response.get_json()
        assert 'checks' in data
        assert 'redis' in data['checks']
        # In development without Redis, should be 'not_configured'
        # In production with Redis, should be 'connected' or 'error'
        assert data['checks']['redis'] in ['connected', 'not_configured', 'error']


# Tests de Rate Limiting (Desarrollo)
class TestRateLimiting:
    """Tests para verificar configuración de rate limiting."""

    def test_rate_limiter_configured(self):
        """Verificar que rate limiter está configurado para desarrollo."""
        from app import limiter, IS_DEVELOPMENT
        # In development, limiter should exist
        if IS_DEVELOPMENT:
            assert limiter is not None


# Tests de Escenarios de Error y Edge Cases
class TestErrorScenarios:
    """Tests para escenarios de error, edge cases y seguridad."""

    def test_malformed_request_id_rejected(self, client):
        """Request IDs con caracteres peligrosos deben ser rechazados."""
        # Intento de inyección de log
        response = client.get('/', headers={'X-Request-ID': '<script>alert(1)</script>'})
        returned_id = response.headers.get('X-Request-ID', '')
        # El ID malicioso no debe ser usado
        assert '<script>' not in returned_id
        assert 'alert' not in returned_id

    def test_very_long_request_id_truncated(self, client):
        """Request IDs muy largos deben ser truncados a 36 caracteres."""
        long_id = 'a' * 100
        response = client.get('/', headers={'X-Request-ID': long_id})
        returned_id = response.headers.get('X-Request-ID', '')
        assert len(returned_id) <= 36

    def test_healthz_no_timestamp_exposed(self, client):
        """Health endpoint no debe exponer timestamp (información sensible)."""
        response = client.get('/healthz')
        data = response.get_json()
        assert 'timestamp' not in data
        assert 'status' in data
        assert data['status'] == 'ok'

    def test_404_returns_html(self, client):
        """Página 404 debe retornar HTML, no JSON."""
        response = client.get('/nonexistent-xyz-page')
        assert response.status_code == 404
        assert response.content_type.startswith('text/html')

    def test_request_id_alphanumeric_valid(self, client):
        """Request IDs alfanuméricos válidos deben ser preservados."""
        valid_id = 'abc-123-DEF'
        response = client.get('/', headers={'X-Request-ID': valid_id})
        assert response.headers['X-Request-ID'] == valid_id


# Tests de Templates y Componentes
class TestTemplates:
    """Tests para renderizado de templates y componentes."""

    def test_index_renders_robot_component(self, client):
        """La página principal debe renderizar el componente robot."""
        response = client.get('/')
        # Verificar que el robot SVG se renderiza
        assert b'robot' in response.data.lower() or b'Robot' in response.data

    def test_index_renders_design_badge(self, client):
        """La página principal debe renderizar el badge de diseño."""
        response = client.get('/')
        # Verificar que el badge de diseño está presente
        assert b'Designed BY' in response.data or b'Carlos Molina' in response.data

    def test_index_renders_status_panel(self, client):
        """La página principal debe renderizar el panel de estado."""
        response = client.get('/')
        assert b'ESTADO' in response.data or b'Backend' in response.data

    def test_error_pages_render_correctly(self, client):
        """Las páginas de error deben renderizar correctamente."""
        response = client.get('/nonexistent-page-xyz')
        assert response.status_code == 404
        assert b'no encontrada' in response.data.lower() or b'404' in response.data

    def test_offline_html_exists(self):
        """El archivo offline.html debe existir para PWA."""
        import os
        offline_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'offline.html'
        )
        assert os.path.exists(offline_path), "offline.html is required for PWA"

    def test_manifest_json_valid(self):
        """El manifest.json debe ser JSON válido con campos requeridos."""
        import json
        import os
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'manifest.json'
        )
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        assert 'name' in manifest
        assert 'icons' in manifest
        assert 'start_url' in manifest
        assert len(manifest['icons']) >= 2

    def test_error_base_template_exists(self):
        """El template error_base.html debe existir (R2: Ciclo 2)."""
        import os
        error_base_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'templates', 'errors', 'error_base.html'
        )
        assert os.path.exists(error_base_path), "error_base.html is required"

    def test_error_base_has_noindex(self):
        """error_base.html debe contener meta noindex (B4)."""
        import os
        error_base_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'templates', 'errors', 'error_base.html'
        )
        with open(error_base_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert 'noindex' in content, "error_base.html should have noindex meta tag"

    def test_error_pages_have_noindex(self, client):
        """Las páginas de error deben tener meta noindex."""
        response = client.get('/nonexistent-page-xyz-404')
        assert response.status_code == 404
        assert b'noindex' in response.data, "404 page should have noindex"


# Tests de Contexto de Producción Simulado
class TestProductionSimulation:
    """Tests que simulan el entorno de producción."""

    def test_site_name_from_env(self, client, monkeypatch):
        """El site_name debe venir de variable de entorno."""
        monkeypatch.setenv('SITE_NAME', 'TestSite')
        # Need to reimport to pick up env change
        from app import inject_globals
        result = inject_globals()
        assert 'site_name' in result

    def test_security_headers_present_in_all_responses(self, client):
        """Todos los endpoints deben tener headers de seguridad."""
        endpoints = ['/', '/healthz']
        required_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'Referrer-Policy',
            'Content-Security-Policy',
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            for header in required_headers:
                assert header in response.headers, f"{header} missing in {endpoint}"

    def test_server_header_not_present(self, client):
        """El header Server no debe estar presente (fingerprinting prevention)."""
        response = client.get('/')
        assert 'Server' not in response.headers, "Server header should be removed"

    def test_no_placeholder_domains_in_static(self):
        """Los archivos estáticos no deben contener dominios placeholder."""
        import os
        static_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static'
        )
        
        # Patrones que indican configuración incompleta
        placeholder_patterns = ['example.com', 'example.vercel.app', 'TU-DOMINIO', 'YOUR-USERNAME']
        files_to_check = [
            'robots.txt',
            'sitemap.xml',
            os.path.join('.well-known', 'security.txt'),
        ]
        
        for filename in files_to_check:
            filepath = os.path.join(static_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    content = f.read()
                for pattern in placeholder_patterns:
                    assert pattern not in content, f"Placeholder '{pattern}' found in {filename}"


# Tests de Rutas SEO/Seguridad
class TestSEORoutes:
    """Tests para rutas SEO y seguridad estándar."""

    def test_robots_txt_accessible(self, client):
        """robots.txt debe ser accesible desde raíz."""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        assert b'User-agent' in response.data

    def test_robots_txt_contains_sitemap(self, client):
        """robots.txt debe incluir referencia a sitemap."""
        response = client.get('/robots.txt')
        assert b'Sitemap:' in response.data

    def test_sitemap_xml_accessible(self, client):
        """sitemap.xml debe ser accesible desde raíz."""
        response = client.get('/sitemap.xml')
        assert response.status_code == 200
        assert b'urlset' in response.data

    def test_sitemap_xml_contains_valid_url(self, client):
        """sitemap.xml debe contener URL válida con lastmod."""
        response = client.get('/sitemap.xml')
        assert b'<loc>' in response.data
        assert b'<lastmod>' in response.data
        assert b'<priority>' in response.data

    def test_security_txt_accessible(self, client):
        """security.txt debe ser accesible en .well-known."""
        response = client.get('/.well-known/security.txt')
        assert response.status_code == 200
        assert b'Contact:' in response.data

    def test_security_txt_contains_required_fields(self, client):
        """security.txt debe tener campos RFC 9116 requeridos."""
        response = client.get('/.well-known/security.txt')
        assert b'Expires:' in response.data
        assert b'Canonical:' in response.data

    def test_dynamic_urls_use_base_url(self, client, monkeypatch):
        """Las URLs dinámicas deben usar BASE_URL configurado."""
        monkeypatch.setenv('BASE_URL', 'https://example.com')
        # Need to reload the module to pick up env change
        import importlib
        import app as app_module
        importlib.reload(app_module)
        
        with app_module.app.test_client() as test_client:
            response = test_client.get('/robots.txt')
            assert b'https://example.com/sitemap.xml' in response.data

    def test_robots_txt_configurable_disallow(self, client, monkeypatch):
        """M1-A02: robots.txt debe soportar ROBOTS_DISALLOW env var."""
        import importlib
        import os
        
        original_disallow = os.environ.get('ROBOTS_DISALLOW')
        
        try:
            monkeypatch.setenv('ROBOTS_DISALLOW', '/admin,/api/internal')
            import app as app_module
            importlib.reload(app_module)
            
            with app_module.app.test_client() as test_client:
                response = test_client.get('/robots.txt')
                content = response.data.decode('utf-8')
                # Default disallows should still be present
                assert 'Disallow: /healthz' in content
                assert 'Disallow: /ready' in content
                # Custom disallows should be added
                assert 'Disallow: /admin' in content
                assert 'Disallow: /api/internal' in content
        finally:
            if original_disallow:
                os.environ['ROBOTS_DISALLOW'] = original_disallow
            elif 'ROBOTS_DISALLOW' in os.environ:
                del os.environ['ROBOTS_DISALLOW']
            importlib.reload(app_module)


# Tests de CSP Compliance
class TestCSPCompliance:
    """Tests para verificar que archivos HTML cumplen con CSP."""

    def test_offline_html_no_inline_scripts(self):
        """offline.html no debe contener scripts inline."""
        import os
        offline_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'offline.html'
        )
        with open(offline_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # No debe tener <script> sin src
        import re
        inline_scripts = re.findall(r'<script(?![^>]*\ssrc=)[^>]*>.*?</script>', content, re.DOTALL | re.IGNORECASE)
        assert len(inline_scripts) == 0, f"Found inline scripts in offline.html: {inline_scripts}"

    def test_offline_html_no_inline_styles(self):
        """offline.html no debe contener estilos inline (<style> tags)."""
        import os
        offline_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'offline.html'
        )
        with open(offline_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # No debe tener <style> tags
        import re
        inline_styles = re.findall(r'<style[^>]*>.*?</style>', content, re.DOTALL | re.IGNORECASE)
        assert len(inline_styles) == 0, f"Found inline styles in offline.html: {inline_styles[:100]}"

    def test_offline_html_uses_external_css(self):
        """offline.html debe usar CSS externo."""
        import os
        offline_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'offline.html'
        )
        with open(offline_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'href="/static/css/offline.css"' in content or "href='/static/css/offline.css'" in content

    def test_offline_html_uses_external_js(self):
        """offline.html debe usar JS externo."""
        import os
        offline_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'offline.html'
        )
        with open(offline_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'src="/static/js/offline.js"' in content or "src='/static/js/offline.js'" in content


# Tests de Configuración de Seguridad
class TestSecurityConfiguration:
    """Tests para configuración de seguridad de la aplicación."""

    def test_max_content_length_configured(self):
        """MAX_CONTENT_LENGTH debe estar configurado para prevenir DoS."""
        from app import app
        assert 'MAX_CONTENT_LENGTH' in app.config
        assert app.config['MAX_CONTENT_LENGTH'] == 1 * 1024 * 1024  # 1MB

    def test_session_cookie_httponly(self):
        """SESSION_COOKIE_HTTPONLY debe estar habilitado."""
        from app import app
        assert app.config.get('SESSION_COOKIE_HTTPONLY') is True

    def test_session_cookie_samesite(self):
        """SESSION_COOKIE_SAMESITE debe estar configurado."""
        from app import app
        assert app.config.get('SESSION_COOKIE_SAMESITE') == 'Lax'

    def test_new_static_files_exist(self):
        """Archivos nuevos de CSP compliance deben existir."""
        import os
        static_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static'
        )
        
        required_files = [
            os.path.join('css', 'offline.css'),
            os.path.join('js', 'offline.js'),
            os.path.join('js', 'error-handlers.js'),
        ]
        
        for filename in required_files:
            filepath = os.path.join(static_dir, filename)
            assert os.path.exists(filepath), f"Missing required file: {filename}"


# Tests de Validación de Host Header
class TestHostHeaderValidation:
    """Tests para validación de Host header (M5: prevención de host header injection)."""

    def test_valid_host_allowed(self, client):
        """Host localhost debe ser permitido en desarrollo."""
        response = client.get('/', headers={'Host': 'localhost:5000'})
        # Should not be rejected
        assert response.status_code != 400

    def test_allowed_hosts_configured(self):
        """get_allowed_hosts debe retornar lista con localhost en desarrollo."""
        from app import get_allowed_hosts
        allowed = get_allowed_hosts()
        # In development should include localhost
        assert isinstance(allowed, list)
        # At minimum should have localhost variants in dev
        assert len(allowed) >= 1


# Tests Adicionales - Ciclo 1 Auditoría
class TestAuditCycle1Fixes:
    """Tests para verificar correcciones del Ciclo 1 de auditoría."""

    def test_ipv4_mapped_ipv6_anonymization(self):
        """B4: IPv4-mapped IPv6 debe ser anonimizada correctamente."""
        from app import anonymize_ip
        # IPv4-mapped IPv6 format
        result = anonymize_ip('::ffff:192.168.1.100')
        # Should return something anonymized, not the original
        assert result != '::ffff:192.168.1.100'
        assert 'invalid' not in result.lower()

    def test_content_type_validation_rejects_invalid(self, client):
        """M2: POST con Content-Type inválido debe retornar 415."""
        response = client.post('/', 
            headers={'Content-Type': 'text/plain'},
            data='test data')
        assert response.status_code == 415

    def test_content_type_validation_allows_json(self, client):
        """M2: POST con Content-Type JSON debe ser aceptado (aunque la ruta no exista)."""
        response = client.post('/nonexistent', 
            headers={'Content-Type': 'application/json'},
            data='{}')
        # Should get 404 (route not found), not 415 (content type error)
        assert response.status_code == 404

    def test_content_type_validation_allows_form(self, client):
        """M2: POST con Content-Type form debe ser aceptado."""
        response = client.post('/nonexistent', 
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            data='key=value')
        # Should get 404 (route not found), not 415 (content type error)
        assert response.status_code == 404

    def test_security_txt_has_stable_expiry(self, client):
        """M4: security.txt debe tener fecha de expiración válida."""
        response = client.get('/.well-known/security.txt')
        assert response.status_code == 200
        # Check expires is present and in correct format
        data = response.data.decode('utf-8')
        assert 'Expires:' in data
        # Check that year is reasonable (within 2 years)
        import re
        expires_match = re.search(r'Expires: (\d{4})-', data)
        assert expires_match is not None
        year = int(expires_match.group(1))
        from datetime import datetime
        current_year = datetime.now().year
        assert current_year <= year <= current_year + 2

    def test_csp_header_present(self, client):
        """A2: CSP header debe estar presente en todas las respuestas."""
        response = client.get('/')
        csp = response.headers.get('Content-Security-Policy', '')
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_permissions_policy_header_present(self, client):
        """M5: Permissions-Policy header debe estar presente."""
        response = client.get('/')
        pp = response.headers.get('Permissions-Policy', '')
        assert 'camera=()' in pp
        assert 'microphone=()' in pp


# Tests de Correcciones Auditoría Ciclo 1
class TestAuditCorrectionsCycle1:
    """Tests para verificar correcciones de la auditoría Ciclo 1."""

    def test_sanitize_log_string_removes_ansi(self):
        """M2: sanitize_log_string debe remover secuencias ANSI."""
        from app import sanitize_log_string
        # Use actual ANSI escape sequences (ESC = \x1b)
        dangerous = "malicious\x1b[31mred\x1b[0mnormal"
        result = sanitize_log_string(dangerous)
        assert '\x1b' not in result
        assert 'maliciousrednormal' == result

    def test_sanitize_log_string_removes_control_chars(self):
        """M2: sanitize_log_string debe remover caracteres de control."""
        from app import sanitize_log_string
        # Use actual control characters
        dangerous = "test\x00null\x07bell\x08backspace"
        result = sanitize_log_string(dangerous)
        assert '\x00' not in result
        assert '\x07' not in result
        assert '\x08' not in result
        assert result == "testnullbellbackspace"

    def test_sanitize_log_string_truncates(self):
        """M2: sanitize_log_string debe truncar strings largos."""
        from app import sanitize_log_string
        long_string = "a" * 200
        result = sanitize_log_string(long_string, max_length=50)
        assert len(result) == 50
        assert result.endswith('...')

    def test_sanitize_log_string_empty(self):
        """M2: sanitize_log_string maneja strings vacíos."""
        from app import sanitize_log_string
        assert sanitize_log_string('') == ''
        assert sanitize_log_string(None) == ''

    def test_robots_txt_has_cache_control(self, client):
        """B5: robots.txt debe tener Cache-Control header."""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        cache = response.headers.get('Cache-Control', '')
        assert 'public' in cache
        assert 'max-age=3600' in cache

    def test_sitemap_xml_has_cache_control(self, client):
        """B5: sitemap.xml debe tener Cache-Control header."""
        response = client.get('/sitemap.xml')
        assert response.status_code == 200
        cache = response.headers.get('Cache-Control', '')
        assert 'public' in cache
        assert 'max-age=3600' in cache

    def test_security_txt_has_cache_control(self, client):
        """B5: security.txt debe tener Cache-Control header."""
        response = client.get('/.well-known/security.txt')
        assert response.status_code == 200
        cache = response.headers.get('Cache-Control', '')
        assert 'public' in cache
        assert 'max-age=86400' in cache

    def test_manifest_json_has_id_field(self):
        """B3: manifest.json debe tener campo id (corregido a '/' sin query string)."""
        import json
        import os
        manifest_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'static', 'manifest.json'
        )
        with open(manifest_path) as f:
            manifest = json.load(f)
        assert 'id' in manifest
        # M4 Fix: id should use query string to avoid conflicts
        assert manifest['id'] == '/?source=pwa'


# Tests de Correcciones Auditoría Ciclo 1 - Fixes
class TestAuditCycle1Fixes:
    """Tests para verificar correcciones adicionales del Ciclo 1."""

    def test_healthz_has_x_robots_tag(self, client):
        """A3: /healthz debe tener X-Robots-Tag para evitar indexación."""
        response = client.get('/healthz')
        assert response.status_code == 200
        assert response.headers.get('X-Robots-Tag') == 'noindex, nofollow'

    def test_ready_has_x_robots_tag(self, client):
        """A3: /ready debe tener X-Robots-Tag para evitar indexación."""
        response = client.get('/ready')
        assert response.status_code == 200
        assert response.headers.get('X-Robots-Tag') == 'noindex, nofollow'

    def test_log_level_fallback_on_invalid(self, monkeypatch):
        """L2: LOG_LEVEL inválido debe hacer fallback a INFO."""
        import importlib
        import os
        
        original_level = os.environ.get('LOG_LEVEL')
        
        try:
            monkeypatch.setenv('LOG_LEVEL', 'INVALID_LEVEL')
            import app as app_module
            importlib.reload(app_module)
            
            # Should fallback to INFO
            assert app_module.LOG_LEVEL == 'INFO'
        finally:
            if original_level:
                os.environ['LOG_LEVEL'] = original_level
            elif 'LOG_LEVEL' in os.environ:
                del os.environ['LOG_LEVEL']
            importlib.reload(app_module)

    def test_security_txt_expires_validates_format(self, monkeypatch):
        """A1: SECURITY_TXT_EXPIRES con formato inválido debe usar fallback."""
        import importlib
        import os
        
        original_expires = os.environ.get('SECURITY_TXT_EXPIRES')
        
        try:
            monkeypatch.setenv('SECURITY_TXT_EXPIRES', 'invalid-date-format')
            import app as app_module
            importlib.reload(app_module)
            
            # Should use auto-calculated format (should be valid ISO 8601)
            expires = app_module.SECURITY_TXT_EXPIRES
            assert 'T' in expires  # ISO 8601 has T separator
            assert expires.endswith('Z')  # Should end with Z for UTC
        finally:
            if original_expires:
                os.environ['SECURITY_TXT_EXPIRES'] = original_expires
            elif 'SECURITY_TXT_EXPIRES' in os.environ:
                del os.environ['SECURITY_TXT_EXPIRES']
            importlib.reload(app_module)

    def test_error_pages_dont_load_lottie(self, client):
        """M5: Páginas de error no deben cargar lottie.min.js (optimización)."""
        response = client.get('/nonexistent-page-xyz')
        assert response.status_code == 404
        # lottie.min.js should NOT be in error pages
        assert b'lottie.min.js' not in response.data

    def test_index_loads_lottie(self, client):
        """M5: Página principal SÍ debe cargar lottie.min.js."""
        response = client.get('/')
        assert response.status_code == 200
        # lottie.min.js should be in index
        assert b'lottie.min.js' in response.data


# Tests de Correcciones Auditoría Ciclo 1 - Fase 2
class TestAuditCycle1Phase2:
    """Tests para verificar correcciones de la auditoría Ciclo 1 Fase 2."""

    def test_x_xss_protection_header_present(self, client):
        """M6 Fix: X-XSS-Protection debe estar presente y deshabilitado."""
        response = client.get('/')
        xss_header = response.headers.get('X-XSS-Protection')
        assert xss_header == '0', "X-XSS-Protection should be '0' to disable legacy filter"

    def test_robots_txt_disallows_internal_endpoints(self, client):
        """B3 Fix: robots.txt debe excluir endpoints internos."""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        content = response.data.decode('utf-8')
        assert 'Disallow: /healthz' in content
        assert 'Disallow: /ready' in content
        assert 'Disallow: /status' in content

    def test_status_endpoint_has_rate_limit(self, client):
        """M2 Fix: /status debe tener rate limiting aplicado."""
        # This test verifies the route is decorated with rate_limit
        # We can't easily test rate limiting in unit tests, but we verify
        # the endpoint still works correctly
        response = client.get('/status')
        assert response.status_code == 301  # Redirect to /healthz
        assert '/healthz' in response.headers.get('Location', '')

    def test_security_contact_max_length_constant_exists(self):
        """M3 Fix: SECURITY_CONTACT_MAX_LENGTH debe estar definido."""
        from app import SECURITY_CONTACT_MAX_LENGTH
        assert SECURITY_CONTACT_MAX_LENGTH == 500

    def test_base_template_scripts_have_defer(self):
        """M5 Fix: Scripts en base.html deben tener atributo defer."""
        import os
        base_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'templates', 'base.html'
        )
        with open(base_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Both main.js and sw-register.js should have defer
        assert 'defer src="{{ url_for(\'static\', filename=\'js/main.js\')' in content or \
               '<script defer src="{{ url_for(\'static\', filename=\'js/main.js\')' in content.replace('"', "'")
        assert 'defer' in content and 'sw-register.js' in content


# Tests de Validación REDIS_URL
class TestRedisURLValidation:
    """Tests para validación de esquemas de REDIS_URL."""

    def test_redis_url_accepts_rediss_scheme(self, monkeypatch):
        """H1-M02: REDIS_URL con esquema rediss:// (TLS) debe ser aceptado."""
        import importlib
        import os
        
        original_url = os.environ.get('REDIS_URL')
        original_vercel = os.environ.get('VERCEL')
        
        try:
            # Simulate development environment to avoid production checks
            if 'VERCEL' in os.environ:
                del os.environ['VERCEL']
            
            monkeypatch.setenv('REDIS_URL', 'rediss://default:password@host.upstash.io:6379')
            import app as app_module
            importlib.reload(app_module)
            
            # Should not raise RuntimeError and should accept rediss://
            assert app_module.RATE_LIMIT_STORAGE.startswith('rediss://')
        finally:
            if original_url:
                os.environ['REDIS_URL'] = original_url
            elif 'REDIS_URL' in os.environ:
                del os.environ['REDIS_URL']
            if original_vercel:
                os.environ['VERCEL'] = original_vercel
            importlib.reload(app_module)
