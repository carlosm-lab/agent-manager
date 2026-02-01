/* Animación Lottie del robot - Carga diferida */
(function () {
    'use strict';

    function initRobotAnimation() {
        var robotContainer = document.getElementById('lottie-robot');
        if (robotContainer && typeof lottie !== 'undefined') {
            var loadAnimation = function () {
                fetch('/static/js/robot-animation.json')
                    .then(function (response) { return response.json(); })
                    .then(function (animationData) {
                        lottie.loadAnimation({
                            container: robotContainer,
                            renderer: 'svg',
                            loop: true,
                            autoplay: true,
                            animationData: animationData
                        });
                    })
                    .catch(function (err) {
                        console.error('Error cargando animación:', err);
                    });
            };

            if ('requestIdleCallback' in window) {
                requestIdleCallback(loadAnimation, { timeout: 2000 });
            } else {
                setTimeout(loadAnimation, 100);
            }
        }
    }

    if (document.readyState === 'complete') {
        initRobotAnimation();
    } else {
        window.addEventListener('load', initRobotAnimation);
    }
})();
