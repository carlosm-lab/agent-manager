# Pytest Configuration - Flask Deploy Template
# Asegura que el directorio raíz esté en PYTHONPATH para los tests

import sys
from pathlib import Path

# Agregar el directorio raíz al path de Python
root_dir = Path(__file__).parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
