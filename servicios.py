"""Reglas de negocio, autenticación y control de acceso."""
from __future__ import annotations

from datetime import datetime, timedelta
from functools import wraps

import config
from database import ConexionBD
from modelos import Administrador, Cliente, Destino, PaqueteTuristico, Reserva, Usuario
from repositorios import (AuditoriaRepositorio, DestinoRepositorio, PaqueteRepositorio,
                          ReservaRepositorio, UsuarioRepositorio)
from seguridad import (CifradorDatos, hashear_password, validar_politica_password,
                       verificar_password)
from validaciones import ErrorValidacion, validar_email, validar_rut, validar_telefono

class ErrorAutenticacion(Exception):
    pass


class ErrorAutorizacion(Exception):
    pass


def requiere(permiso: str):
    def decorador(func):
        @wraps(func)
        def envoltura(self, usuario: Usuario, *args, **kwargs):
            if usuario is None or not usuario.puede(permiso):
                self._auditoria.registrar(getattr(usuario, "id", None), "ACCESO_DENEGADO", permiso)
                raise ErrorAutorizacion("No tiene permisos para realizar esta acción.")
            return func(self, usuario, *args, **kwargs)
        return envoltura
    return decorador


class AuthService:
    MENSAJE_GENERICO = "Correo o contraseña incorrectos."

    def __init__(self, usuarios: UsuarioRepositorio, auditoria: AuditoriaRepositorio):
        self._usuarios = usuarios
        self._auditoria = auditoria

    def registrar_cliente(self, nombre, email, password, confirmacion, rut, telefono) -> Cliente:
        if password != confirmacion:
            raise ErrorValidacion("Las contraseñas no coinciden.")
        validar_politica_password(password)
        cliente = Cliente(nombre, email, hashear_password(password),
                          rut=validar_rut(rut), telefono=validar_telefono(telefono))
        self._usuarios.crear(cliente)
        self._auditoria.registrar(cliente.id, "REGISTRO", "cliente")
        return cliente

    def crear_administrador(self, nombre, email, password) -> Administrador:
        validar_politica_password(password)
        admin = Administrador(nombre, email, hashear_password(password))
        self._usuarios.crear(admin)
        self._auditoria.registrar(admin.id, "REGISTRO", "admin")
        return admin

    def iniciar_sesion(self, email: str, password: str, ahora: datetime | None = None) -> Usuario:
        ahora = ahora or datetime.now()
        try:
            email = validar_email(email)
        except ErrorValidacion:
            verificar_password(password, None)
            raise ErrorAutenticacion(self.MENSAJE_GENERICO) from None

        cred = self._usuarios.obtener_credenciales(email)
        if cred is None:
            verificar_password(password, None)
            self._auditoria.registrar(None, "LOGIN_FALLIDO", "usuario inexistente")
            raise ErrorAutenticacion(self.MENSAJE_GENERICO)

        if cred["bloqueado_hasta"] and datetime.fromisoformat(cred["bloqueado_hasta"]) > ahora:
            self._auditoria.registrar(cred["id"], "LOGIN_BLOQUEADO")
            raise ErrorAutenticacion(
                f"Cuenta bloqueada temporalmente. Intente en {config.MINUTOS_BLOQUEO} minutos.")

        if not verificar_password(password, cred["password_hash"]):
            intentos = cred["intentos_fallidos"] + 1
            bloqueo = None
            if intentos >= config.MAX_INTENTOS_FALLIDOS:
                bloqueo = (ahora + timedelta(minutes=config.MINUTOS_BLOQUEO)).isoformat(timespec="seconds")
                intentos = 0
            self._usuarios.registrar_fallo(cred["id"], intentos, bloqueo)
            self._auditoria.registrar(cred["id"], "LOGIN_FALLIDO", "bloqueo" if bloqueo else "")
            raise ErrorAutenticacion(self.MENSAJE_GENERICO)

        self._usuarios.reiniciar_intentos(cred["id"])
        self._auditoria.registrar(cred["id"], "LOGIN_OK")
        return self._usuarios.obtener(cred["id"])


class CatalogoService:
    def __init__(self, destinos: DestinoRepositorio, paquetes: PaqueteRepositorio,
                 auditoria: AuditoriaRepositorio):
        self._destinos = destinos
        self._paquetes = paquetes
        self._auditoria = auditoria

    @requiere("gestionar_destinos")
    def crear_destino(self, usuario, nombre, pais, descripcion, costo) -> Destino:
        destino = self._destinos.crear(Destino(nombre, pais, descripcion, costo))
        self._auditoria.registrar(usuario.id, "DESTINO_CREADO", destino.nombre)
        return destino

    @requiere("ver_catalogo")
    def listar_destinos(self, usuario) -> list[Destino]:
        return self._destinos.listar(solo_activos=not usuario.puede("gestionar_destinos"))

    @requiere("gestionar_destinos")
    def modificar_destino(self, usuario, destino_id, **cambios) -> Destino:
        destino = self._obtener_destino(destino_id)
        for campo in ("nombre", "pais", "descripcion", "costo_base"):
            if cambios.get(campo) not in (None, ""):
                setattr(destino, campo, cambios[campo])
        if "activo" in cambios and cambios["activo"] is not None:
            destino.activo = bool(cambios["activo"])
        self._destinos.actualizar(destino)
        self._auditoria.registrar(usuario.id, "DESTINO_MODIFICADO", str(destino_id))
        return destino

    @requiere("gestionar_destinos")
    def eliminar_destino(self, usuario, destino_id) -> str:
        self._obtener_destino(destino_id)
        resultado = self._destinos.eliminar(destino_id)
        self._auditoria.registrar(usuario.id, "DESTINO_" + resultado.upper(), str(destino_id))
        return resultado

    def _obtener_destino(self, destino_id) -> Destino:
        destino = self._destinos.obtener(int(destino_id))
        if destino is None:
            raise ErrorValidacion("Destino no encontrado.")
        return destino

    @requiere("gestionar_paquetes")
    def crear_paquete(self, usuario, nombre, fecha_inicio, fecha_fin, cupos, destino_ids) -> PaqueteTuristico:
        destinos = [self._destino_activo(i) for i in destino_ids]
        paquete = self._paquetes.crear(PaqueteTuristico(nombre, fecha_inicio, fecha_fin, cupos, destinos))
        self._auditoria.registrar(usuario.id, "PAQUETE_CREADO", paquete.nombre)
        return paquete

    @requiere("ver_catalogo")
    def listar_paquetes(self, usuario) -> list[PaqueteTuristico]:
        return self._paquetes.listar(solo_vigentes=not usuario.puede("gestionar_paquetes"))

    @requiere("gestionar_paquetes")
    def modificar_paquete(self, usuario, paquete_id, nombre=None, fecha_inicio=None, fecha_fin=None,
                          cupos=None, destino_ids=None) -> PaqueteTuristico:
        paquete = self._obtener_paquete(paquete_id)
        if nombre:
            paquete.nombre = nombre
        if fecha_inicio or fecha_fin:
            paquete.definir_fechas(fecha_inicio or paquete.fecha_inicio, fecha_fin or paquete.fecha_fin)
        if cupos:
            paquete.cupos_totales = cupos
        if destino_ids:
            nuevo = PaqueteTuristico(paquete.nombre, paquete.fecha_inicio, paquete.fecha_fin,
                                     paquete.cupos_totales, [self._destino_activo(i) for i in destino_ids],
                                     id_=paquete.id, permitir_pasado=True)
            paquete = nuevo
        self._paquetes.actualizar(paquete)
        self._auditoria.registrar(usuario.id, "PAQUETE_MODIFICADO", str(paquete_id))
        return paquete

    @requiere("gestionar_paquetes")
    def eliminar_paquete(self, usuario, paquete_id) -> None:
        self._obtener_paquete(paquete_id)
        self._paquetes.eliminar(int(paquete_id))
        self._auditoria.registrar(usuario.id, "PAQUETE_ELIMINADO", str(paquete_id))

    @requiere("ver_catalogo")
    def consultar_disponibilidad(self, usuario, paquete_id):
        return self._paquetes.disponibilidad(int(paquete_id))

    @requiere("ver_catalogo")
    def cotizar_destinos(self, usuario, destino_ids) -> float:
        destinos = [self._destino_activo(i) for i in destino_ids]
        subtotal = sum(d.costo_base for d in destinos)
        return round(subtotal * (1 + config.RECARGO_AGENCIA), 2)

    def _destino_activo(self, destino_id) -> Destino:
        destino = self._obtener_destino(destino_id)
        if not destino.activo:
            raise ErrorValidacion(f"El destino #{destino.id} está inactivo.")
        return destino

    def _obtener_paquete(self, paquete_id) -> PaqueteTuristico:
        paquete = self._paquetes.obtener(int(paquete_id))
        if paquete is None:
            raise ErrorValidacion("Paquete no encontrado.")
        return paquete


class ReservaService:
    def __init__(self, bd: ConexionBD, reservas: ReservaRepositorio, paquetes: PaqueteRepositorio,
                 auditoria: AuditoriaRepositorio):
        self._bd = bd
        self._reservas = reservas
        self._paquetes = paquetes
        self._auditoria = auditoria

    @requiere("reservar")
    def reservar(self, usuario, paquete_id, cantidad_personas) -> Reserva:
        paquete = self._paquetes.obtener(int(paquete_id))
        if paquete is None or not paquete.esta_vigente():
            raise ErrorValidacion("El paquete no existe o ya no está disponible.")
        reserva = Reserva(usuario.id, paquete, cantidad_personas)
        # cupos y guardado en la misma transacción para evitar sobreventa
        with self._bd.transaccion():
            libres = paquete.cupos_totales - self._paquetes.cupos_reservados(paquete.id)
            if reserva.cantidad_personas > libres:
                raise ErrorValidacion(f"No hay cupos suficientes (disponibles: {libres}).")
            self._reservas.crear(reserva)
        self._auditoria.registrar(usuario.id, "RESERVA_CREADA", f"#{reserva.id}")
        return reserva

    @requiere("ver_historial_propio")
    def historial(self, usuario) -> list[Reserva]:
        return self._reservas.listar_por_cliente(usuario.id)

    @requiere("cancelar_reserva_propia")
    def cancelar(self, usuario, reserva_id) -> Reserva:
        reserva = self._reservas.obtener(int(reserva_id))
        if reserva is None or reserva.cliente_id != usuario.id:
            raise ErrorValidacion("Reserva no encontrada.")
        reserva.cancelar()
        self._reservas.actualizar(reserva)
        self._auditoria.registrar(usuario.id, "RESERVA_CANCELADA", f"#{reserva.id}")
        return reserva

    @requiere("ver_todas_reservas")
    def todas(self, usuario) -> list[Reserva]:
        return self._reservas.listar()


class Sistema:
    def __init__(self, ruta_bd=None, clave_cifrado: bytes | None = None):
        self.bd = ConexionBD(ruta_bd)
        cifrador = CifradorDatos(clave_cifrado)
        self.auditoria = AuditoriaRepositorio(self.bd)
        self.usuarios = UsuarioRepositorio(self.bd, cifrador)
        destinos = DestinoRepositorio(self.bd)
        paquetes = PaqueteRepositorio(self.bd, destinos)
        reservas = ReservaRepositorio(self.bd, paquetes)
        self.auth = AuthService(self.usuarios, self.auditoria)
        self.catalogo = CatalogoService(destinos, paquetes, self.auditoria)
        self.reservas = ReservaService(self.bd, reservas, paquetes, self.auditoria)

    def cerrar(self):
        self.bd.cerrar()
