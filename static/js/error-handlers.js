/* Manejadores para páginas de error */
(function () {
    'use strict';

    function initReloadButtons() {
        document.addEventListener('click', function (event) {
            var target = event.target.closest('[data-action="reload"]');
            if (target) {
                event.preventDefault();
                location.reload();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initReloadButtons);
    } else {
        initReloadButtons();
    }
})();
