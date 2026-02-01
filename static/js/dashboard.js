// Funcionalidad del Dashboard
// Maneja la actualización periódica y reinicio automático de cuotas

const Dashboard = {
    // Inicializar dashboard
    init() {
        this.checkForPendingResets();
        this.refreshStats(); // Force immediate update
        this.setupPeriodicRefresh();
    },

    // Verificar si hay cuotas que necesitan reinicio automático
    async checkForPendingResets() {
        try {
            const result = await API.post('/api/quotas/check-resets');
            if (result.reset_count > 0) {
                showToast(`${result.reset_count} cuota(s) reiniciada(s) automáticamente`, 'info');
                this.refreshStats();
            }
        } catch (error) {
            // Fallo silencioso para verificación en segundo plano
        }
    },

    // Configurar actualización periódica de estadísticas (cada 5 min)
    setupPeriodicRefresh() {
        setInterval(() => {
            this.checkForPendingResets();
        }, 5 * 60 * 1000);
    },

    // Actualizar estadísticas desde el servidor
    async refreshStats() {
        try {
            const summary = await API.get('/api/accounts/summary');
            this.updateStatsDisplay(summary);
        } catch (error) {
            // Fallo silencioso - se actualizará en el siguiente ciclo
        }
    },

    // Actualizar visualización de estadísticas en el DOM
    updateStatsDisplay(summary) {
        const elements = {
            'stat-total': summary.total,
            'stat-disponibles': summary.disponibles,
            'stat-parcial': summary.limite_parcial,
            'stat-total-limit': summary.limite_total,
            'stat-limite-anthropic': summary.limite_anthropic,
            'stat-limite-gemini': summary.limite_gemini,
            'stat-modelo': summary.modelo_mas_usado || 'N/A',
            'stat-horas-anthropic': summary.horas_por_modelo?.anthropic?.toFixed(1) + 'h' || '0h',
            'stat-horas-gemini': summary.horas_por_modelo?.gemini?.toFixed(1) + 'h' || '0h',
            'stat-horas-total': summary.horas_totales?.toFixed(1) + 'h' || '0h'
        };

        Object.entries(elements).forEach(([id, value]) => {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        });
    },

    // Manejar acción de cuota agotada
    async handleQuotaExhausted(resetDatetime) {
        try {
            const session = TimeManager.getSavedSession();
            if (!session) {
                throw new Error('No hay sesión activa');
            }

            const result = await API.post('/api/sessions/rotate', {
                motivo: 'cuota_agotada',
                proximo_reset: new Date(resetDatetime).toISOString(),
                auto_start: true
            });

            TimeManager.clearSession();

            if (result.needs_user_choice) {
                return {
                    success: true,
                    needsChoice: true,
                    nextAnthropicReset: result.next_anthropic_reset,
                    nextAccount: result.next_account
                };
            }

            if (result.rotated) {
                showToast('Cuenta rotada exitosamente', 'success');
                return { success: true, rotated: true };
            }

            showToast('No hay cuentas disponibles', 'warning');
            return { success: true, noAccounts: true };

        } catch (error) {
            showToast(error.message, 'error');
            return { success: false, error: error.message };
        }
    },

    // Controladores para cancelar peticiones anteriores
    _abortControllers: {},

    // Cargar cuentas en modal con cancelación de peticiones anteriores
    async loadModalAccounts(filterType, elementId) {
        const container = document.getElementById(elementId);
        if (!container) return;

        const requestKey = `${filterType}-${elementId}`;

        // Cancelar cualquier petición anterior para este modal
        if (this._abortControllers[requestKey]) {
            this._abortControllers[requestKey].abort();
        }

        // Crear nuevo controlador de cancelación
        const abortController = new AbortController();
        this._abortControllers[requestKey] = abortController;

        // Mostrar skeleton loader
        container.innerHTML = `
            <div class="animate-pulse space-y-3">
                <div class="flex items-center gap-4 px-3 py-3">
                    <div class="w-10 h-10 bg-slate-200 rounded-full"></div>
                    <div class="flex-1 space-y-2">
                        <div class="h-4 bg-slate-200 rounded w-3/4"></div>
                        <div class="h-3 bg-slate-100 rounded w-1/2"></div>
                    </div>
                </div>
                <div class="flex items-center gap-4 px-3 py-3">
                    <div class="w-10 h-10 bg-slate-200 rounded-full"></div>
                    <div class="flex-1 space-y-2">
                        <div class="h-4 bg-slate-200 rounded w-2/3"></div>
                        <div class="h-3 bg-slate-100 rounded w-1/3"></div>
                    </div>
                </div>
            </div>`;

        try {
            // Mapear filtros de UI a filtros de API
            const filterMap = {
                'total': '',
                'disponibles': 'disponible',
                'anthropic': 'anthropic_exhausted',
                'gemini': 'gemini_exhausted',
                'total_limit': 'exhausted_total'
            };

            const apiFilter = filterMap[filterType] || '';
            const url = apiFilter ? `/api/accounts?filter=${apiFilter}` : '/api/accounts';

            // Hacer petición con señal de cancelación
            const response = await fetch(url, {
                method: 'GET',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include',
                signal: abortController.signal
            });

            // Verificar que la respuesta es JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                throw new Error('Sesión expirada. Recarga la página.');
            }

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Error del servidor');
            }

            // Verificar que el container sigue siendo válido y no fue reemplazado
            const currentContainer = document.getElementById(elementId);
            if (!currentContainer) return;

            if (!result.accounts || result.accounts.length === 0) {
                currentContainer.innerHTML = '<p class="text-slate-500 text-center py-8">No hay cuentas en esta categoría.</p>';
                return;
            }

            currentContainer.innerHTML = result.accounts.map(account => this.renderAccountItem(account, filterType)).join('');

            // Inicializar contadores dinámicos si es necesario
            if (filterType === 'anthropic' || filterType === 'gemini') {
                result.accounts.forEach(account => {
                    const quota = account.quotas ? account.quotas[filterType] : null;
                    if (quota && !quota.disponible && quota.proximo_reset) {
                        const resetDate = new Date(quota.proximo_reset);
                        if (resetDate > new Date()) {
                            const countdownId = `countdown-${account.id}-${filterType}`;
                            TimeManager.startCountdown(countdownId, resetDate, () => {
                                this.loadModalAccounts(filterType, elementId);
                            });
                        }
                    }
                });
            }

        } catch (error) {
            // Ignorar errores de cancelación (AbortError)
            if (error.name === 'AbortError') return;

            const currentContainer = document.getElementById(elementId);
            if (currentContainer) {
                currentContainer.innerHTML = `<p class="text-red-500 text-center py-4">Error: ${error.message}</p>`;
            }
        } finally {
            // Limpiar controlador si es el actual
            if (this._abortControllers[requestKey] === abortController) {
                delete this._abortControllers[requestKey];
            }
        }
    },

    // Renderizar item de cuenta para modal
    renderAccountItem(account, filterType) {
        const initial = (account.nombre || account.email_google || '?')[0].toUpperCase();
        const colors = ['bg-red-500', 'bg-green-500', 'bg-blue-500', 'bg-purple-500', 'bg-orange-500'];
        const colorClass = colors[account.email_google.length % colors.length];

        let statusHtml = '';

        // Personalizar estado según el contexto (filtro)
        if (filterType === 'anthropic' || filterType === 'gemini') {
            const provider = filterType;
            const quota = account.quotas ? account.quotas[provider] : null;

            if (quota && !quota.disponible && quota.proximo_reset) {
                // Mostrar cuenta regresiva dinámica
                const resetDate = new Date(quota.proximo_reset);
                const now = new Date();

                if (resetDate > now) {
                    const countdownId = `countdown-${account.id}-${filterType}`;
                    statusHtml = `
                    <div class="text-right">
                        <p class="text-xs text-amber-600 font-medium">Reinicia en</p>
                        <p class="text-sm font-bold text-amber-700 tabular-nums" id="${countdownId}">--:--:--</p>
                    </div>`;
                } else {
                    statusHtml = `<span class="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700">Disponible pronto</span>`;
                }
            } else {
                statusHtml = `<span class="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600">Agotada</span>`;
            }
        } else if (filterType === 'disponibles') {
            // Mostrar claramente que está disponible
            statusHtml = `
            <div class="text-right">
                <span class="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700">
                    Disponible
                </span>
            </div>`;
        } else if (filterType === 'total') {
            // En lista total, solo mostrar si está activa, sino nada (limpio)
            if (account.activa) {
                statusHtml = `<span class="text-xs px-2 py-1 rounded-full bg-primary-100 text-primary-700">En uso</span>`;
            } else {
                statusHtml = ''; // Nada para cuentas inactivas en la lista total
            }
        } else {
            // Default (otros filtros)
            statusHtml = `
            <div class="text-right">
                <span class="text-xs px-2 py-1 rounded-full ${account.activa ? 'bg-primary-100 text-primary-700' : 'bg-slate-100 text-slate-600'}">
                    ${account.activa ? 'En uso' : 'Inactiva'}
                </span>
            </div>`;
        }

        return `
        <div class="flex items-center gap-4 px-3 py-3 rounded-xl hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0" 
             ${filterType === 'disponibles' ? `onclick="closeModal('modal-disponibles'); openModal('modal-accounts')"` : ''} 
             style="${filterType === 'disponibles' ? 'cursor: pointer;' : ''}">
            <div class="w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${colorClass} text-white font-bold text-lg">
                ${initial}
            </div>
            <div class="min-w-0 flex-1">
                <p class="font-semibold text-slate-800 text-sm truncate">
                    ${account.nombre || account.email_google.split('@')[0]}
                </p>
                <p class="text-slate-500 text-xs truncate">${account.email_google}</p>
            </div>
            ${statusHtml}
        </div>
        `;
    }
};

// Inicializar dashboard cuando cargue la página
document.addEventListener('DOMContentLoaded', () => {
    Dashboard.init();
});
