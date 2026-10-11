"""Clases del dominio."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

import config
from validaciones import (ErrorValidacion, validar_email, validar_entero, validar_monto, validar_rango_fechas, validar_texto)

class Rol(str, Enum):
    CLIENTE = "cliente"
    ADMIN = "admin"

class EstadoReserva(str, Enum):
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"

class Entidad(ABC):
    def __init__(self, id_: int | None = None):
        self._id = id_

    @property
    def id(self) -> int | None:
        return self._id

    @id.setter
    def id(self, valor: int) -> None:
        if self._id is not None:
            raise AttributeError("El identificador no puede modificarse.")
        self._id = valor

    @abstractmethod
    def resumen(self) -> str:
        ...


class Usuario(Entidad, ABC):
    def __init__(self, nombre: str, email: str, password_hash: str, id_: int | None = None):
        super().__init__(id_)
        self.nombre = nombre
        self.email = email
        self.__password_hash = password_hash

    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor: str) -> None:
        self._nombre = validar_texto(valor, "Nombre", 2, 80)

    @property
    def email(self) -> str:
        return self._email

    @email.setter
    def email(self, valor: str) -> None:
        self._email = validar_email(valor)

    @property
    def password_hash(self) -> str:
        return self.__password_hash

    @property
    @abstractmethod
    def rol(self) -> Rol: ...

    @abstractmethod
    def permisos(self) -> set[str]:
        ...

    def puede(self, accion: str) -> bool:
        return accion in self.permisos()


class Cliente(Usuario):
    def __init__(self, nombre, email, password_hash, rut: str, telefono: str, id_=None):
        super().__init__(nombre, email, password_hash, id_)
        self.rut = rut            # se cifra al guardar
        self.telefono = telefono

    @property
    def rol(self) -> Rol:
        return Rol.CLIENTE

    def permisos(self) -> set[str]:
        return {"ver_catalogo", "reservar", "ver_historial_propio", "cancelar_reserva_propia"}

    def resumen(self) -> str:
        return f"[Cliente #{self.id}] {self.nombre} <{self.email}>"


class Administrador(Usuario):
    @property
    def rol(self) -> Rol:
        return Rol.ADMIN

    def permisos(self) -> set[str]:
        return {"ver_catalogo", "gestionar_destinos", "gestionar_paquetes",
                "ver_todas_reservas", "ver_auditoria"}

    def resumen(self) -> str:
        return f"[Admin #{self.id}] {self.nombre} <{self.email}>"


class Destino(Entidad):
    def __init__(self, nombre: str, pais: str, descripcion: str, costo_base: float,
                 activo: bool = True, id_: int | None = None):
        super().__init__(id_)
        self.nombre = nombre
        self.pais = pais
        self.descripcion = descripcion
        self.costo_base = costo_base
        self.activo = activo

    @property
    def nombre(self):
        return self._nombre

    @nombre.setter
    def nombre(self, v):
        self._nombre = validar_texto(v, "Nombre del destino", 2, 80)

    @property
    def pais(self):
        return self._pais

    @pais.setter
    def pais(self, v):
        self._pais = validar_texto(v, "País", 2, 60)

    @property
    def descripcion(self):
        return self._descripcion

    @descripcion.setter
    def descripcion(self, v):
        self._descripcion = validar_texto(v, "Descripción", 3, 300)

    @property
    def costo_base(self) -> float:
        return self._costo_base

    @costo_base.setter
    def costo_base(self, v):
        self._costo_base = validar_monto(v, "Costo base")

    def resumen(self) -> str:
        return f"#{self.id} {self.nombre} ({self.pais}) - ${self.costo_base:,.0f}"


class PaqueteTuristico(Entidad):
    def __init__(self, nombre: str, fecha_inicio, fecha_fin, cupos_totales: int,
                 destinos: list[Destino] | None = None, id_: int | None = None,
                 permitir_pasado: bool = False):
        super().__init__(id_)
        self.nombre = nombre
        self.definir_fechas(fecha_inicio, fecha_fin, permitir_pasado)
        self.cupos_totales = cupos_totales
        self._destinos: list[Destino] = []
        for destino in destinos or []:
            self.agregar_destino(destino)

    @property
    def nombre(self):
        return self._nombre

    @nombre.setter
    def nombre(self, v):
        self._nombre = validar_texto(v, "Nombre del paquete", 3, 100)

    @property
    def cupos_totales(self) -> int:
        return self._cupos_totales

    @cupos_totales.setter
    def cupos_totales(self, v):
        self._cupos_totales = validar_entero(v, "Cupos", 1, 500)

    @property
    def destinos(self) -> tuple[Destino, ...]:
        return tuple(self._destinos)

    def definir_fechas(self, inicio, fin, permitir_pasado: bool = False) -> None:
        self.fecha_inicio, self.fecha_fin = validar_rango_fechas(inicio, fin, permitir_pasado)

    def agregar_destino(self, destino: Destino) -> None:
        if any(d.id == destino.id for d in self._destinos if d.id is not None):
            raise ErrorValidacion("El destino ya forma parte del paquete.")
        self._destinos.append(destino)

    def quitar_destino(self, destino_id: int) -> None:
        self._destinos = [d for d in self._destinos if d.id != destino_id]

    @property
    def duracion_dias(self) -> int:
        return (self.fecha_fin - self.fecha_inicio).days + 1

    def calcular_costo(self) -> float:
        """Costo por persona = suma de costos de destinos + recargo de agencia."""
        if not self._destinos:
            raise ErrorValidacion("El paquete debe contener al menos un destino.")
        subtotal = sum(d.costo_base for d in self._destinos)
        return round(subtotal * (1 + config.RECARGO_AGENCIA), 2)

    def esta_vigente(self, hoy: date | None = None) -> bool:
        return self.fecha_inicio >= (hoy or date.today())

    def resumen(self) -> str:
        nombres = ", ".join(d.nombre for d in self._destinos)
        return (f"#{self.id} {self.nombre} | {self.fecha_inicio} a {self.fecha_fin} "
                f"({self.duracion_dias} días) | {nombres} | ${self.calcular_costo():,.0f} p/p")


@dataclass
class Disponibilidad:
    paquete_id: int
    cupos_totales: int
    cupos_reservados: int

    @property
    def cupos_libres(self) -> int:
        return self.cupos_totales - self.cupos_reservados


class Reserva(Entidad):
    def __init__(self, cliente_id: int, paquete: PaqueteTuristico, cantidad_personas: int,
                 monto_total: float | None = None, estado: EstadoReserva = EstadoReserva.CONFIRMADA,
                 fecha_reserva: datetime | None = None, id_: int | None = None):
        super().__init__(id_)
        self.cliente_id = cliente_id
        self.paquete = paquete
        self.cantidad_personas = validar_entero(cantidad_personas, "Cantidad de personas", 1, 20)
        self.monto_total = monto_total if monto_total is not None else self.calcular_total()
        self.estado = EstadoReserva(estado)
        self.fecha_reserva = fecha_reserva or datetime.now()

    def calcular_total(self) -> float:
        return round(self.paquete.calcular_costo() * self.cantidad_personas, 2)

    def cancelar(self) -> None:
        if self.estado == EstadoReserva.CANCELADA:
            raise ErrorValidacion("La reserva ya está cancelada.")
        self.estado = EstadoReserva.CANCELADA

    def resumen(self) -> str:
        return (f"Reserva #{self.id} | {self.paquete.nombre} | {self.cantidad_personas} pers. | "
                f"${self.monto_total:,.0f} | {self.estado.value} | {self.fecha_reserva:%Y-%m-%d %H:%M}")
