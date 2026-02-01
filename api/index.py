"""
Google Antigravity Manager - Punto de Entrada de Vercel
Configura la aplicación Flask para despliegue en Vercel.
"""

import sys
import os

# Agregar directorio padre al path para desarrollo local
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

# Crear instancia de la aplicación para Vercel
app = create_app()

# Para desarrollo local
if __name__ == '__main__':
    # SEGURIDAD: debug=False previene exposición de consola de depuración Werkzeug
    # Establecer DEBUG_MODE=1 en entorno solo para desarrollo local confiable
    import os
    debug_mode = os.environ.get('DEBUG_MODE', '0') == '1'
    app.run(debug=debug_mode, use_evalex=False, host='0.0.0.0', port=5000)
