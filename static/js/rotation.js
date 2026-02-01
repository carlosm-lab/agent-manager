// Lógica de Rotación
// Maneja la selección de cuentas y rotación automática entre proveedores

const Rotation = {
    // Obtener la mejor cuenta disponible según prioridad
    async getBestAccount() {
        try {
            const accounts = await API.get('/api/accounts?filter=disponibles');

            if (!accounts.accounts || accounts.accounts.length === 0) {
                return { account: null, provider: null, reason: 'sin_cuentas' };
            }

            // Prioridad: Anthropic primero
            for (const account of accounts.accounts) {
                if (account.quotas?.anthropic?.disponible) {
                    return { account, provider: 'anthropic', reason: 'anthropic_disponible' };
                }
            }

            // Respaldo: Gemini
            for (const account of accounts.accounts) {
                if (account.quotas?.gemini?.disponible) {
                    return { account, provider: 'gemini', reason: 'solo_gemini' };
                }
            }

            return { account: null, provider: null, reason: 'todas_agotadas' };

        } catch (error) {
            return { account: null, provider: null, reason: 'error', error: error.message };
        }
    },

    // Iniciar sesión con la mejor cuenta disponible
    async startBestSession() {
        const { account, provider, reason } = await this.getBestAccount();

        if (!account) {
            return { success: false, reason };
        }

        if (reason === 'solo_gemini') {
            return {
                success: false,
                needsChoice: true,
                account,
                provider
            };
        }

        try {
            const result = await API.post('/api/sessions/start', {
                account_id: account.id,
                provider
            });

            return { success: true, session: result.session, account, provider };
        } catch (error) {
            return { success: false, reason: 'inicio_fallido', error };
        }
    },

    // Obtener próximo tiempo de reinicio de Anthropic
    async getNextAnthropicReset() {
        try {
            const result = await API.get('/api/quotas/next-reset/anthropic');
            return result.proximo_reset ? new Date(result.proximo_reset) : null;
        } catch (error) {
            return null;
        }
    },

    // Forzar uso de Gemini cuando Anthropic no está disponible
    async useGemini() {
        const { account, provider, reason } = await this.getBestAccount();

        if (!account) {
            return { success: false, reason };
        }

        if (account.quotas?.gemini?.disponible) {
            try {
                const result = await API.post('/api/sessions/start', {
                    account_id: account.id,
                    provider: 'gemini'
                });

                return { success: true, session: result.session, account, provider: 'gemini' };
            } catch (error) {
                return { success: false, reason: 'inicio_fallido', error };
            }
        }

        return { success: false, reason: 'sin_gemini' };
    }
};

// Exportar para uso en otros scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Rotation;
}
