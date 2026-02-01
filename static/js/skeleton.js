/**
 * Skeleton Loader - Manejo de transiciones
 * Oculta skeleton y muestra contenido real cuando la página está lista
 */

(function () {
    'use strict';

    // Tiempo máximo de espera para skeleton (fallback)
    const MAX_SKELETON_TIME = 4000;

    // Tiempo mínimo visible del skeleton para efecto visual
    const MIN_SKELETON_TIME = 300;

    let skeletonShowTime = Date.now();

    /**
     * Marca el contenido como cargado con transición suave
     */
    function showContent() {
        // Asegurar tiempo mínimo visible del skeleton
        const elapsed = Date.now() - skeletonShowTime;
        const remainingTime = Math.max(0, MIN_SKELETON_TIME - elapsed);

        setTimeout(function () {
            document.body.classList.add('content-loaded');
        }, remainingTime);
    }

    /**
     * Verifica si recursos críticos están listos
     */
    function checkResourcesReady() {
        // Verificar si hay animación Lottie
        const lottieContainer = document.getElementById('lottie-robot');

        if (lottieContainer) {
            // Si hay Lottie, esperar a que se cargue
            if (typeof lottie !== 'undefined') {
                // Lottie ya cargado
                showContent();
            } else {
                // Esperar un poco para Lottie
                setTimeout(showContent, 600);
            }
        } else {
            // Sin Lottie, mostrar contenido directamente
            showContent();
        }
    }

    // Ejecutar cuando el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', checkResourcesReady);
    } else {
        // DOM ya cargado
        checkResourcesReady();
    }

    // Fallback: mostrar contenido después de MAX_SKELETON_TIME
    setTimeout(function () {
        if (!document.body.classList.contains('content-loaded')) {
            console.warn('[Skeleton] Timeout alcanzado, forzando visualización de contenido');
            document.body.classList.add('content-loaded');
        }
    }, MAX_SKELETON_TIME);

    // También asegurar al cargar completamente la ventana
    window.addEventListener('load', function () {
        // Pequeño delay para transición suave con todos los recursos
        setTimeout(function () {
            if (!document.body.classList.contains('content-loaded')) {
                showContent();
            }
        }, 150);
    });
})();
