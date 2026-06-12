"""Agrega el directorio raíz del proyecto al path para que los tests encuentren los módulos."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
