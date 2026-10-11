from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

from database import ConexionBD
from modelos import (Administrador, Cliente, Destino, Disponibilidad, EstadoReserva,
                     PaqueteTuristico, Reserva, Rol, Usuario)
from seguridad import CifradorDatos
from validaciones import ErrorValidacion


class RepositorioBase(ABC):
    def __init__(self, bd: ConexionBD):
        self._bd = bd

    @abstractmethod
    def crear(self, entidad): ...

    @abstractmethod
    def obtener(self, id_: int): ...

    @abstractmethod
    def listar(self) -> list: ...

    @abstractmethod
    def actualizar(self, entidad) -> None: ...

    @abstractmethod
    def eliminar(self, id_: int): ...


class UsuarioRepositorio(RepositorioBase):
    def __init__(self, bd: ConexionBD, cifrador: CifradorDatos):
        super().__init__(bd)
        self._cifrador = cifrador

    def _a_objeto(self, fila: sqlite3.Row) -> Usuario:
        if fila["rol"] == Rol.ADMIN.value:
            return Administrador(fila["nombre"], fila["email"], fila["password_hash"], id_=fila["id"])
        return Cliente(fila["nombre"], fila["email"], fila["password_hash"],
                       rut=self._cifrador.descifrar(fila["rut_cifrado"]),
                       telefono=self._cifrador.descifrar(fila["telefono_cifrado"]),
                       id_=fila["id"])

    def crear(self, usuario: Usuario) -> Usuario:
        rut = tel = None
        if isinstance(usuario, Cliente):
            rut = self._cifrador.cifrar(usuario.rut)
            tel = self._cifrador.cifrar(usuario.telefono)
        try:
            cur = self._bd.ejecutar(
                "INSERT INTO usuarios (nombre, email, password_hash, rol, rut_cifrado, telefono_cifrado) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (usuario.nombre, usuario.email, usuario.password_hash, usuario.rol.value, rut, tel))
        except sqlite3.IntegrityError:
            raise ErrorValidacion("Ya existe una cuenta con ese correo.") from None
        usuario.id = cur.lastrowid
        return usuario

    def obtener(self, id_: int) -> Usuario | None:
        fila = self._bd.uno("SELECT * FROM usuarios WHERE id = ?", (id_,))
        return self._a_objeto(fila) if fila else None

    def obtener_credenciales(self, email: str) -> sqlite3.Row | None:
        return self._bd.uno("SELECT id, password_hash, intentos_fallidos, bloqueado_hasta "
                            "FROM usuarios WHERE email = ?", (email,))

    def listar(self) -> list[Usuario]:
        return [self._a_objeto(f) for f in self._bd.todos("SELECT * FROM usuarios ORDER BY id")]

    def actualizar(self, usuario: Usuario) -> None:
        self._bd.ejecutar("UPDATE usuarios SET nombre = ?, email = ? WHERE id = ?",
                          (usuario.nombre, usuario.email, usuario.id))

    def eliminar(self, id_: int) -> None:
        self._bd.ejecutar("DELETE FROM usuarios WHERE id = ?", (id_,))

    def registrar_fallo(self, id_: int, intentos: int, bloqueado_hasta: str | None) -> None:
        self._bd.ejecutar("UPDATE usuarios SET intentos_fallidos = ?, bloqueado_hasta = ? WHERE id = ?",
                          (intentos, bloqueado_hasta, id_))

    def reiniciar_intentos(self, id_: int) -> None:
        self._bd.ejecutar("UPDATE usuarios SET intentos_fallidos = 0, bloqueado_hasta = NULL "
                          "WHERE id = ?", (id_,))

    def existe_admin(self) -> bool:
        return self._bd.uno("SELECT 1 FROM usuarios WHERE rol = 'admin' LIMIT 1") is not None


class DestinoRepositorio(RepositorioBase):
    @staticmethod
    def _a_objeto(f: sqlite3.Row) -> Destino:
        return Destino(f["nombre"], f["pais"], f["descripcion"], f["costo_base"],
                       bool(f["activo"]), id_=f["id"])

    def crear(self, destino: Destino) -> Destino:
        try:
            cur = self._bd.ejecutar(
                "INSERT INTO destinos (nombre, pais, descripcion, costo_base, activo) VALUES (?, ?, ?, ?, ?)",
                (destino.nombre, destino.pais, destino.descripcion, destino.costo_base, int(destino.activo)))
        except sqlite3.IntegrityError:
            raise ErrorValidacion("Ya existe un destino con ese nombre en ese país.") from None
        destino.id = cur.lastrowid
        return destino

    def obtener(self, id_: int) -> Destino | None:
        f = self._bd.uno("SELECT * FROM destinos WHERE id = ?", (id_,))
        return self._a_objeto(f) if f else None

    def listar(self, solo_activos: bool = True) -> list[Destino]:
        if solo_activos:
            filas = self._bd.todos("SELECT * FROM destinos WHERE activo = 1 ORDER BY nombre")
        else:
            filas = self._bd.todos("SELECT * FROM destinos ORDER BY nombre")
        return [self._a_objeto(f) for f in filas]

    def actualizar(self, destino: Destino) -> None:
        try:
            self._bd.ejecutar(
                "UPDATE destinos SET nombre = ?, pais = ?, descripcion = ?, costo_base = ?, activo = ? "
                "WHERE id = ?",
                (destino.nombre, destino.pais, destino.descripcion, destino.costo_base,
                 int(destino.activo), destino.id))
        except sqlite3.IntegrityError:
            raise ErrorValidacion("Ya existe un destino con ese nombre en ese país.") from None

    def eliminar(self, id_: int) -> str:
        """Si el destino está en un paquete solo se desactiva."""
        en_uso = self._bd.uno("SELECT 1 FROM paquete_destino WHERE destino_id = ? LIMIT 1", (id_,))
        if en_uso:
            self._bd.ejecutar("UPDATE destinos SET activo = 0 WHERE id = ?", (id_,))
            return "desactivado"
        self._bd.ejecutar("DELETE FROM destinos WHERE id = ?", (id_,))
        return "eliminado"


class PaqueteRepositorio(RepositorioBase):
    def __init__(self, bd: ConexionBD, destinos: DestinoRepositorio):
        super().__init__(bd)
        self._destinos = destinos

    def _a_objeto(self, f: sqlite3.Row) -> PaqueteTuristico:
        filas = self._bd.todos("SELECT d.* FROM destinos d JOIN paquete_destino pd ON pd.destino_id = d.id "
                               "WHERE pd.paquete_id = ? ORDER BY pd.orden", (f["id"],))
        destinos = [DestinoRepositorio._a_objeto(x) for x in filas]
        return PaqueteTuristico(f["nombre"], f["fecha_inicio"], f["fecha_fin"], f["cupos_totales"],
                                destinos, id_=f["id"], permitir_pasado=True)

    def _guardar_destinos(self, paquete: PaqueteTuristico) -> None:
        self._bd.ejecutar("DELETE FROM paquete_destino WHERE paquete_id = ?", (paquete.id,))
        for orden, d in enumerate(paquete.destinos, start=1):
            self._bd.ejecutar("INSERT INTO paquete_destino (paquete_id, destino_id, orden) VALUES (?, ?, ?)",
                              (paquete.id, d.id, orden))

    def crear(self, paquete: PaqueteTuristico) -> PaqueteTuristico:
        paquete.calcular_costo()
        try:
            with self._bd.transaccion():
                cur = self._bd.ejecutar(
                    "INSERT INTO paquetes (nombre, fecha_inicio, fecha_fin, cupos_totales) VALUES (?, ?, ?, ?)",
                    (paquete.nombre, paquete.fecha_inicio.isoformat(), paquete.fecha_fin.isoformat(),
                     paquete.cupos_totales))
                paquete.id = cur.lastrowid
                self._guardar_destinos(paquete)
        except sqlite3.IntegrityError:
            raise ErrorValidacion("Ya existe un paquete con ese nombre.") from None
        return paquete

    def obtener(self, id_: int) -> PaqueteTuristico | None:
        f = self._bd.uno("SELECT * FROM paquetes WHERE id = ?", (id_,))
        return self._a_objeto(f) if f else None

    def listar(self, solo_vigentes: bool = False) -> list[PaqueteTuristico]:
        if solo_vigentes:
            filas = self._bd.todos("SELECT * FROM paquetes WHERE fecha_inicio >= date('now','localtime') "
                                   "ORDER BY fecha_inicio")
        else:
            filas = self._bd.todos("SELECT * FROM paquetes ORDER BY fecha_inicio")
        return [self._a_objeto(f) for f in filas]

    def actualizar(self, paquete: PaqueteTuristico) -> None:
        reservados = self.cupos_reservados(paquete.id)
        if paquete.cupos_totales < reservados:
            raise ErrorValidacion(f"No se pueden dejar menos cupos que los ya reservados ({reservados}).")
        with self._bd.transaccion():
            self._bd.ejecutar("UPDATE paquetes SET nombre = ?, fecha_inicio = ?, fecha_fin = ?, "
                              "cupos_totales = ? WHERE id = ?",
                              (paquete.nombre, paquete.fecha_inicio.isoformat(),
                               paquete.fecha_fin.isoformat(), paquete.cupos_totales, paquete.id))
            self._guardar_destinos(paquete)

    def eliminar(self, id_: int) -> None:
        if self._bd.uno("SELECT 1 FROM reservas WHERE paquete_id = ? LIMIT 1", (id_,)):
            raise ErrorValidacion("El paquete tiene reservas asociadas y no puede eliminarse.")
        self._bd.ejecutar("DELETE FROM paquetes WHERE id = ?", (id_,))

    def cupos_reservados(self, paquete_id: int) -> int:
        f = self._bd.uno("SELECT COALESCE(SUM(cantidad_personas), 0) AS n FROM reservas "
                         "WHERE paquete_id = ? AND estado = 'confirmada'", (paquete_id,))
        return int(f["n"])

    def disponibilidad(self, paquete_id: int) -> Disponibilidad:
        paquete = self.obtener(paquete_id)
        if paquete is None:
            raise ErrorValidacion("Paquete no encontrado.")
        return Disponibilidad(paquete_id, paquete.cupos_totales, self.cupos_reservados(paquete_id))


class ReservaRepositorio(RepositorioBase):
    def __init__(self, bd: ConexionBD, paquetes: PaqueteRepositorio):
        super().__init__(bd)
        self._paquetes = paquetes

    def _a_objeto(self, f: sqlite3.Row) -> Reserva:
        return Reserva(f["cliente_id"], self._paquetes.obtener(f["paquete_id"]), f["cantidad_personas"],
                       monto_total=f["monto_total"], estado=EstadoReserva(f["estado"]),
                       fecha_reserva=datetime.fromisoformat(f["fecha_reserva"]), id_=f["id"])

    def crear(self, reserva: Reserva) -> Reserva:
        cur = self._bd.ejecutar(
            "INSERT INTO reservas (cliente_id, paquete_id, cantidad_personas, monto_total, estado, fecha_reserva) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (reserva.cliente_id, reserva.paquete.id, reserva.cantidad_personas, reserva.monto_total,
             reserva.estado.value, reserva.fecha_reserva.isoformat(timespec="seconds")))
        reserva.id = cur.lastrowid
        return reserva

    def obtener(self, id_: int) -> Reserva | None:
        f = self._bd.uno("SELECT * FROM reservas WHERE id = ?", (id_,))
        return self._a_objeto(f) if f else None

    def listar(self) -> list[Reserva]:
        return [self._a_objeto(f) for f in self._bd.todos("SELECT * FROM reservas ORDER BY fecha_reserva DESC")]

    def listar_por_cliente(self, cliente_id: int) -> list[Reserva]:
        filas = self._bd.todos("SELECT * FROM reservas WHERE cliente_id = ? ORDER BY fecha_reserva DESC",
                               (cliente_id,))
        return [self._a_objeto(f) for f in filas]

    def actualizar(self, reserva: Reserva) -> None:
        self._bd.ejecutar("UPDATE reservas SET estado = ? WHERE id = ?", (reserva.estado.value, reserva.id))

    def eliminar(self, id_: int) -> None:
        raise ErrorValidacion("Las reservas no se eliminan: utilice cancelar.")


class AuditoriaRepositorio:
    def __init__(self, bd: ConexionBD):
        self._bd = bd

    def registrar(self, usuario_id: int | None, accion: str, detalle: str = "") -> None:
        self._bd.ejecutar("INSERT INTO auditoria (usuario_id, accion, detalle) VALUES (?, ?, ?)",
                          (usuario_id, accion, detalle[:200]))

    def ultimos(self, n: int = 20) -> list[sqlite3.Row]:
        return self._bd.todos("SELECT * FROM auditoria ORDER BY id DESC LIMIT ?", (n,))
