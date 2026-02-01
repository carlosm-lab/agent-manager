// Gestor de Tiempo
// Maneja cálculos de tiempo, temporizadores y persistencia en LocalStorage

const TimeManager = {
    intervals: {},

    // Formatear milisegundos a HH:MM:SS
    formatDuration(ms) {
        if (ms < 0) ms = 0;

        const seconds = Math.floor(ms / 1000);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;

        return [
            hours.toString().padStart(2, '0'),
            minutes.toString().padStart(2, '0'),
            secs.toString().padStart(2, '0')
        ].join(':');
    },

    // Formatear milisegundos a string legible (ej: "2h 30m")
    formatDurationHuman(ms) {
        const seconds = Math.floor(ms / 1000);
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);

        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else if (minutes > 0) {
            return `${minutes}m`;
        } else {
            return `${seconds}s`;
        }
    },

    // Iniciar temporizador que cuenta hacia arriba desde un tiempo de inicio
    startTimer(elementId, startTime, offsetMs = 0) {
        const element = document.getElementById(elementId);
        if (!element) return;

        // Limpiar intervalo existente si hay uno
        if (this.intervals[elementId]) {
            clearInterval(this.intervals[elementId]);
        }

        const startMs = startTime instanceof Date ? startTime.getTime() : new Date(startTime).getTime();

        const updateTimer = () => {
            // Verificar si el timer está pausado (función expuesta desde index.html)
            if (typeof window.isTimerPaused === 'function' && window.isTimerPaused()) {
                return; // No actualizar si está pausado
            }
            const currentSessionElapsed = Date.now() - startMs;
            const totalElapsed = currentSessionElapsed + offsetMs;
            element.textContent = this.formatDuration(totalElapsed);
        };

        updateTimer();
        this.intervals[elementId] = setInterval(updateTimer, 1000);
    },

    // Iniciar cuenta regresiva hacia un tiempo objetivo
    startCountdown(elementId, targetTime, onComplete = null) {
        const element = document.getElementById(elementId);
        if (!element) return;

        // Limpiar intervalo existente si hay uno
        if (this.intervals[elementId]) {
            clearInterval(this.intervals[elementId]);
        }

        const targetMs = targetTime instanceof Date ? targetTime.getTime() : new Date(targetTime).getTime();

        const updateCountdown = () => {
            const remaining = targetMs - Date.now();

            if (remaining <= 0) {
                element.textContent = '00:00:00';
                clearInterval(this.intervals[elementId]);
                delete this.intervals[elementId];

                // Ejecutar callback si se proporcionó
                if (onComplete) {
                    onComplete();
                }
                return;
            }

            element.textContent = this.formatDuration(remaining);
        };

        updateCountdown();
        this.intervals[elementId] = setInterval(updateCountdown, 1000);
    },

    // Detener un temporizador o cuenta regresiva específica
    stopTimer(elementId) {
        if (this.intervals[elementId]) {
            clearInterval(this.intervals[elementId]);
            delete this.intervals[elementId];
        }
    },

    // Detener todos los temporizadores
    stopAllTimers() {
        Object.keys(this.intervals).forEach(id => {
            clearInterval(this.intervals[id]);
        });
        this.intervals = {};
    },

    // Guardar datos de sesión en LocalStorage
    saveSession(sessionData) {
        localStorage.setItem('antigravity_session', JSON.stringify({
            ...sessionData,
            savedAt: new Date().toISOString()
        }));
    },

    // Obtener sesión guardada desde LocalStorage
    getSavedSession() {
        const saved = localStorage.getItem('antigravity_session');
        if (!saved) return null;

        try {
            return JSON.parse(saved);
        } catch {
            return null;
        }
    },

    // Limpiar sesión guardada
    clearSession() {
        localStorage.removeItem('antigravity_session');
    },

    // Verificar si existe una sesión activa guardada
    hasActiveSession() {
        const session = this.getSavedSession();
        return session !== null;
    },

    // Calcular tiempo transcurrido desde inicio de sesión
    getSessionElapsed() {
        const session = this.getSavedSession();
        if (!session || !session.inicio) return 0;

        const startMs = new Date(session.inicio).getTime();
        return Date.now() - startMs;
    },

    // Obtener tiempo hasta un reinicio
    getTimeUntilReset(resetTime) {
        const resetMs = new Date(resetTime).getTime();
        return Math.max(0, resetMs - Date.now());
    },

    // Verificar si un tiempo de reinicio ya pasó
    isResetPassed(resetTime) {
        return new Date(resetTime).getTime() <= Date.now();
    },

    // Restaurar temporizador de sesión al cargar página
    restoreSession(timerElementId) {
        const session = this.getSavedSession();
        if (session && session.inicio) {
            const offsetMs = session.tiempo_acumulado_ms || 0;
            this.startTimer(timerElementId, session.inicio, offsetMs);
            return true;
        }
        return false;
    }
};

// Limpiar temporizadores al cerrar página
window.addEventListener('beforeunload', () => {
    TimeManager.stopAllTimers();
});

// Exportar para uso en otros scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TimeManager;
}
