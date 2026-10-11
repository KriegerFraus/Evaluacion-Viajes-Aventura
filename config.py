"""Configuración del sistema."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(os.environ.get("VA_DB_PATH", BASE_DIR / "viajes_aventura.db"))

# La clave se toma de VA_FERNET_KEY o, si no existe, de secret.key
FERNET_KEY_ENV = "VA_FERNET_KEY"
FERNET_KEY_FILE = Path(os.environ.get("VA_KEY_PATH", BASE_DIR / "secret.key"))

BCRYPT_ROUNDS = 12              # costo de bcrypt (2^12 iteraciones)
MAX_INTENTOS_FALLIDOS = 3       # intentos antes de bloquear la cuenta
MINUTOS_BLOQUEO = 5             # duración del bloqueo temporal
LARGO_MIN_PASSWORD = 8
LARGO_MAX_PASSWORD = 64         # bcrypt solo procesa 72 bytes; se limita antes
RECARGO_AGENCIA = 0.15          # 15 %
