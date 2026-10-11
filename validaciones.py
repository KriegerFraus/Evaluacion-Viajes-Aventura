"""Validación de datos ingresados por el usuario."""
import re
from datetime import date, datetime


class ErrorValidacion(ValueError):
    pass


_RE_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_RE_TEXTO = re.compile(r"^[\wÁÉÍÓÚÜÑáéíóúüñ .,'()\-/]+$")
_RE_TELEFONO = re.compile(r"^\+?\d{8,12}$")


def validar_texto(valor: str, campo: str, minimo: int = 2, maximo: int = 100) -> str:
    valor = (valor or "").strip()
    if not minimo <= len(valor) <= maximo:
        raise ErrorValidacion(f"{campo} debe tener entre {minimo} y {maximo} caracteres.")
    if not _RE_TEXTO.match(valor):
        raise ErrorValidacion(f"{campo} contiene caracteres no permitidos.")
    return valor


def validar_email(valor: str) -> str:
    valor = (valor or "").strip().lower()
    if len(valor) > 120 or not _RE_EMAIL.match(valor):
        raise ErrorValidacion("El correo electrónico no tiene un formato válido.")
    return valor


def validar_rut(valor: str) -> str:
    limpio = (valor or "").replace(".", "").replace("-", "").strip().upper()
    if len(limpio) < 8 or len(limpio) > 9 or not limpio[:-1].isdigit():
        raise ErrorValidacion("RUT inválido.")
    cuerpo, dv = limpio[:-1], limpio[-1]
    suma, factor = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    esperado = {11: "0", 10: "K"}.get(resto, str(resto))
    if dv != esperado:
        raise ErrorValidacion("RUT inválido: dígito verificador incorrecto.")
    return f"{cuerpo}-{dv}"


def validar_telefono(valor: str) -> str:
    valor = (valor or "").replace(" ", "").strip()
    if not _RE_TELEFONO.match(valor):
        raise ErrorValidacion("Teléfono inválido (8 a 12 dígitos, '+' opcional).")
    return valor


def validar_monto(valor, campo: str = "Monto") -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErrorValidacion(f"{campo} debe ser numérico.") from None
    if numero <= 0 or numero > 100_000_000:
        raise ErrorValidacion(f"{campo} debe ser mayor que 0 y razonable.")
    return round(numero, 2)


def validar_entero(valor, campo: str, minimo: int = 1, maximo: int = 1000) -> int:
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        raise ErrorValidacion(f"{campo} debe ser un número entero.") from None
    if not minimo <= numero <= maximo:
        raise ErrorValidacion(f"{campo} debe estar entre {minimo} y {maximo}.")
    return numero


def validar_fecha(valor, campo: str = "Fecha") -> date:
    if isinstance(valor, date):
        return valor
    try:
        return datetime.strptime((valor or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ErrorValidacion(f"{campo} debe tener formato AAAA-MM-DD.") from None


def validar_rango_fechas(inicio, fin, permitir_pasado: bool = False) -> tuple[date, date]:
    inicio, fin = validar_fecha(inicio, "Fecha de inicio"), validar_fecha(fin, "Fecha de término")
    if fin < inicio:
        raise ErrorValidacion("La fecha de término no puede ser anterior a la de inicio.")
    if not permitir_pasado and inicio < date.today():
        raise ErrorValidacion("La fecha de inicio no puede estar en el pasado.")
    return inicio, fin
