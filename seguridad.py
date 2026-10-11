"""Hash de contraseñas (bcrypt) y cifrado de datos personales (Fernet)."""
import os
import re

import bcrypt
from cryptography.fernet import Fernet, InvalidToken

import config
from validaciones import ErrorValidacion


def validar_politica_password(password: str) -> str:
    if not isinstance(password, str):
        raise ErrorValidacion("Contraseña inválida.")
    errores = []
    if not config.LARGO_MIN_PASSWORD <= len(password) <= config.LARGO_MAX_PASSWORD:
        errores.append(f"entre {config.LARGO_MIN_PASSWORD} y {config.LARGO_MAX_PASSWORD} caracteres")
    if not re.search(r"[A-Z]", password):
        errores.append("una mayúscula")
    if not re.search(r"[a-z]", password):
        errores.append("una minúscula")
    if not re.search(r"\d", password):
        errores.append("un número")
    if not re.search(r"[^A-Za-z0-9]", password):
        errores.append("un símbolo")
    if errores:
        raise ErrorValidacion("La contraseña debe tener: " + ", ".join(errores) + ".")
    return password


def hashear_password(password: str) -> str:
    sal = bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode("utf-8"), sal).decode("utf-8")


# Se compara contra este hash cuando el usuario no existe, así el tiempo
# de respuesta no revela qué correos están registrados.
_HASH_FICTICIO = bcrypt.hashpw(b"usuario-inexistente", bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS))


def verificar_password(password: str, hash_guardado: str | None) -> bool:
    if not isinstance(password, str) or len(password) > config.LARGO_MAX_PASSWORD:
        bcrypt.checkpw(b"x", _HASH_FICTICIO)
        return False
    if hash_guardado is None:
        bcrypt.checkpw(password.encode("utf-8"), _HASH_FICTICIO)
        return False
    return bcrypt.checkpw(password.encode("utf-8"), hash_guardado.encode("utf-8"))


class CifradorDatos:
    def __init__(self, clave: bytes | None = None):
        self._fernet = Fernet(clave or self._obtener_clave())

    @staticmethod
    def _obtener_clave() -> bytes:
        desde_entorno = os.environ.get(config.FERNET_KEY_ENV)
        if desde_entorno:
            return desde_entorno.encode()
        ruta = config.FERNET_KEY_FILE
        if ruta.exists():
            return ruta.read_bytes().strip()
        clave = Fernet.generate_key()
        # permisos 600: solo el dueño puede leerla
        fd = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as archivo:
            archivo.write(clave)
        return clave

    def cifrar(self, texto: str) -> str:
        return self._fernet.encrypt(texto.encode("utf-8")).decode("ascii")

    def descifrar(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode("ascii")).decode("utf-8")
        except InvalidToken:
            return "[dato no disponible]"


def enmascarar(texto: str, visibles: int = 3) -> str:
    if len(texto) <= visibles:
        return "*" * len(texto)
    return "*" * (len(texto) - visibles) + texto[-visibles:]
