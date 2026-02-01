/* Manejador de página offline */
(function () {
    'use strict';

    // Recarga automática al restaurar conexión
    function initAutoReload() {
        window.addEventListener('online', function () {
            var statusText = document.querySelector('.status-text');
            if (statusText) {
                statusText.textContent = 'Conexión restaurada, recargando...';
            }
            setTimeout(function () {
                location.reload();
            }, 500);
        });
    }

    // Botón de recarga manual
    function initReloadButton() {
        var btn = document.getElementById('retry-btn');
        if (btn) {
            btn.addEventListener('click', function () {
                location.reload();
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initAutoReload();
            initReloadButton();
        });
    } else {
        initAutoReload();
        initReloadButton();
    }
})();
