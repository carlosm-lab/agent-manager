/* Registro del Service Worker */
(function () {
    'use strict';

    var isDevMode = window.location.hostname === 'localhost' ||
        window.location.hostname === '127.0.0.1';

    if ('serviceWorker' in navigator) {
        window.addEventListener('load', function () {
            navigator.serviceWorker.register('/static/sw.js')
                .then(function (registration) {
                    if (isDevMode) {
                        console.log('[SW] Registrado:', registration.scope);
                    }
                })
                .catch(function (error) {
                    if (isDevMode) {
                        console.warn('[SW] Registro fallido:', error);
                    }
                });
        });
    }
})();
