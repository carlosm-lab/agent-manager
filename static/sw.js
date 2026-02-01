/* Service Worker - PWA v1.5.0 */

const CACHE_VERSION = 14;
const DEPLOY_HASH = '202601220700';
const CACHE_NAME = `deploy-template-v${CACHE_VERSION}-${DEPLOY_HASH}`;
const DEBUG_SW = false;

function log(message, ...args) {
    if (DEBUG_SW) console.log('[SW]', message, ...args);
}

// Recursos estáticos a cachear
const STATIC_ASSETS = [
    '/static/css/main.css',
    '/static/css/tailwind.css',
    '/static/css/fonts.css',
    '/static/css/offline.css',
    '/static/js/main.js',
    '/static/js/sw-register.js',
    '/static/js/offline.js',
    '/static/js/error-handlers.js',
    '/static/js/lottie.min.js',
    '/static/js/robot.js',
    '/static/js/robot-animation.json',
    '/static/favicon.svg',
    '/static/manifest.json',
    '/static/offline.html',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
];

// Instalación
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                log('Cacheando recursos');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                log('Instalación completa');
                return self.skipWaiting();
            })
            .catch((error) => {
                log('Instalación fallida:', error);
            })
    );
});

// Activación
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME)
                        .map((name) => {
                            log('Eliminando caché antiguo:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                log('Activación completa');
                return self.clients.claim();
            })
    );
});

// Fetch - Cache-First para estáticos, Network-First para dinámicos
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return;
    if (!event.request.url.startsWith('http')) return;

    const url = new URL(event.request.url);
    const isStaticAsset = url.pathname.startsWith('/static/');

    if (isStaticAsset) {
        event.respondWith(
            caches.match(event.request)
                .then((cachedResponse) => {
                    if (cachedResponse) return cachedResponse;
                    return fetch(event.request).then((response) => {
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }
                        const responseToCache = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseToCache);
                        });
                        return response;
                    });
                })
        );
    } else {
        event.respondWith(
            fetch(event.request)
                .then((response) => response)
                .catch(() => {
                    if (event.request.mode === 'navigate') {
                        return caches.match('/static/offline.html').then((cached) => {
                            return cached || new Response('Offline', { status: 503 });
                        });
                    }
                    return new Response('Error de red', { status: 503 });
                })
        );
    }
});
