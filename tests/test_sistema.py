"""Pruebas automatizadas (unittest, biblioteca estándar).

Ejecutar desde la carpeta del proyecto:  python -m unittest -v
"""
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config  # noqa: E402

config.BCRYPT_ROUNDS = 4  # solo en pruebas, para que corran rápido

from cryptography.fernet import Fernet  # noqa: E402

from modelos import Administrador, Cliente, Destino, PaqueteTuristico  # noqa: E402
from seguridad import CifradorDatos, hashear_password, verificar_password  # noqa: E402
from servicios import ErrorAutenticacion, ErrorAutorizacion, Sistema  # noqa: E402
from validaciones import ErrorValidacion, validar_rut  # noqa: E402

PASS_OK = "Segura#2026"


class BaseSistema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "test.db"
        self.clave = Fernet.generate_key()
        self.s = Sistema(self.ruta, self.clave)
        self.admin = self.s.auth.crear_administrador("Admin Test", "admin@test.cl", PASS_OK)
        self.cliente = self.s.auth.registrar_cliente("Ana Pérez", "ana@test.cl", PASS_OK, PASS_OK,
                                                     "11111111-1", "+56911112222")
        self.d1 = self.s.catalogo.crear_destino(self.admin, "Valparaíso", "Chile", "Puerto y cerros", 100000)
        self.d2 = self.s.catalogo.crear_destino(self.admin, "Cusco", "Perú", "Capital inca", 200000)
        inicio = date.today() + timedelta(days=10)
        self.paq = self.s.catalogo.crear_paquete(self.admin, "Combo Andino", inicio,
                                                 inicio + timedelta(days=5), 5, [self.d1.id, self.d2.id])

    def tearDown(self):
        self.s.cerrar()
        self.tmp.cleanup()


class TestValidaciones(unittest.TestCase):
    def test_rut_valido_e_invalido(self):
        self.assertEqual(validar_rut("11.111.111-1"), "11111111-1")
        with self.assertRaises(ErrorValidacion):
            validar_rut("11111111-2")

    def test_destino_rechaza_costo_negativo_e_inyeccion(self):
        with self.assertRaises(ErrorValidacion):
            Destino("Lima", "Perú", "Ciudad", -5)
        with self.assertRaises(ErrorValidacion):
            Destino("x'; DROP TABLE destinos;--", "Perú", "Ciudad", 10)

    def test_paquete_fechas_invertidas(self):
        hoy = date.today() + timedelta(days=5)
        with self.assertRaises(ErrorValidacion):
            PaqueteTuristico("Malo", hoy, hoy - timedelta(days=1), 10, [])


class TestSeguridad(unittest.TestCase):
    def test_hash_bcrypt_no_es_texto_plano_y_tiene_sal(self):
        h1, h2 = hashear_password(PASS_OK), hashear_password(PASS_OK)
        self.assertNotIn(PASS_OK, h1)
        self.assertNotEqual(h1, h2)  # sal distinta
        self.assertTrue(verificar_password(PASS_OK, h1))
        self.assertFalse(verificar_password("Otra#2026", h1))

    def test_cifrado_detecta_manipulacion(self):
        c = CifradorDatos(Fernet.generate_key())
        token = c.cifrar("11111111-1")
        self.assertNotIn("11111111", token)
        self.assertEqual(c.descifrar(token), "11111111-1")
        alterado = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")
        self.assertEqual(c.descifrar(alterado), "[dato no disponible]")


class TestAutenticacion(BaseSistema):
    def test_login_correcto_devuelve_rol(self):
        self.assertIsInstance(self.s.auth.iniciar_sesion("ana@test.cl", PASS_OK), Cliente)
        self.assertIsInstance(self.s.auth.iniciar_sesion("ADMIN@test.cl", PASS_OK), Administrador)

    def test_mensaje_generico_para_usuario_inexistente_y_clave_mala(self):
        with self.assertRaises(ErrorAutenticacion) as a:
            self.s.auth.iniciar_sesion("nadie@test.cl", PASS_OK)
        with self.assertRaises(ErrorAutenticacion) as b:
            self.s.auth.iniciar_sesion("ana@test.cl", "Mala#2026x")
        self.assertEqual(str(a.exception), str(b.exception))

    def test_bloqueo_tras_tres_intentos(self):
        for _ in range(config.MAX_INTENTOS_FALLIDOS):
            with self.assertRaises(ErrorAutenticacion):
                self.s.auth.iniciar_sesion("ana@test.cl", "Mala#2026x")
        with self.assertRaisesRegex(ErrorAutenticacion, "bloqueada"):
            self.s.auth.iniciar_sesion("ana@test.cl", PASS_OK)  # incluso con la clave correcta
        despues = datetime.now() + timedelta(minutes=config.MINUTOS_BLOQUEO + 1)
        self.assertIsNotNone(self.s.auth.iniciar_sesion("ana@test.cl", PASS_OK, ahora=despues))

    def test_politica_password_y_email_duplicado(self):
        with self.assertRaises(ErrorValidacion):
            self.s.auth.registrar_cliente("Luis", "luis@test.cl", "debil", "debil", "11111111-1", "+56911112222")
        with self.assertRaises(ErrorValidacion):
            self.s.auth.registrar_cliente("Ana 2", "ana@test.cl", PASS_OK, PASS_OK, "11111111-1", "+56911112222")

    def test_datos_sensibles_cifrados_en_bd(self):
        # closing(): Windows no permite borrar el archivo si la conexión queda abierta.
        with closing(sqlite3.connect(self.ruta)) as conexion:
            crudo = conexion.execute(
                "SELECT password_hash, rut_cifrado, telefono_cifrado FROM usuarios WHERE email='ana@test.cl'"
            ).fetchone()
        self.assertTrue(crudo[0].startswith("$2b$"))
        self.assertNotIn("11111111", crudo[1])
        self.assertNotIn("56911112222", crudo[2])
        self.assertEqual(self.s.usuarios.obtener(self.cliente.id).rut, "11111111-1")


class TestAutorizacion(BaseSistema):
    def test_cliente_no_gestiona_catalogo(self):
        with self.assertRaises(ErrorAutorizacion):
            self.s.catalogo.crear_destino(self.cliente, "Lima", "Perú", "Ciudad", 1000)
        with self.assertRaises(ErrorAutorizacion):
            self.s.catalogo.eliminar_paquete(self.cliente, self.paq.id)

    def test_cliente_no_cancela_reserva_ajena(self):
        otro = self.s.auth.registrar_cliente("Beto", "beto@test.cl", PASS_OK, PASS_OK, "11111111-1", "+56933334444")
        r = self.s.reservas.reservar(self.cliente, self.paq.id, 1)
        with self.assertRaises(ErrorValidacion):
            self.s.reservas.cancelar(otro, r.id)


class TestCrudYPersistencia(BaseSistema):
    def test_crud_destino(self):
        d = self.s.catalogo.crear_destino(self.admin, "Lima", "Perú", "Ciudad gastronómica", 150000)
        self.assertIn(d.id, [x.id for x in self.s.catalogo.listar_destinos(self.admin)])
        self.s.catalogo.modificar_destino(self.admin, d.id, costo_base=175000)
        self.assertEqual(self.s.catalogo._destinos.obtener(d.id).costo_base, 175000)
        self.assertEqual(self.s.catalogo.eliminar_destino(self.admin, d.id), "eliminado")
        self.assertIsNone(self.s.catalogo._destinos.obtener(d.id))

    def test_destino_en_paquete_se_desactiva(self):
        self.assertEqual(self.s.catalogo.eliminar_destino(self.admin, self.d1.id), "desactivado")
        self.assertNotIn(self.d1.id, [d.id for d in self.s.catalogo.listar_destinos(self.cliente)])

    def test_costo_paquete_y_cotizacion(self):
        esperado = round(300000 * (1 + config.RECARGO_AGENCIA), 2)
        self.assertEqual(self.paq.calcular_costo(), esperado)
        self.assertEqual(self.s.catalogo.cotizar_destinos(self.cliente, [self.d1.id, self.d2.id]), esperado)

    def test_modificar_y_eliminar_paquete(self):
        self.s.catalogo.modificar_paquete(self.admin, self.paq.id, cupos=8, destino_ids=[self.d2.id])
        p = self.s.catalogo._paquetes.obtener(self.paq.id)
        self.assertEqual((p.cupos_totales, len(p.destinos)), (8, 1))
        self.s.catalogo.eliminar_paquete(self.admin, self.paq.id)
        self.assertIsNone(self.s.catalogo._paquetes.obtener(self.paq.id))

    def test_reserva_persiste_entre_sesiones(self):
        r = self.s.reservas.reservar(self.cliente, self.paq.id, 2)
        self.assertEqual(r.monto_total, self.paq.calcular_costo() * 2)
        self.s.cerrar()
        self.s = Sistema(self.ruta, self.clave)  # "reinicio" del sistema
        hist = self.s.reservas.historial(self.cliente)
        self.assertEqual([x.id for x in hist], [r.id])

    def test_no_sobreventa_y_cancelacion_libera_cupos(self):
        r = self.s.reservas.reservar(self.cliente, self.paq.id, 5)
        with self.assertRaisesRegex(ErrorValidacion, "cupos"):
            self.s.reservas.reservar(self.cliente, self.paq.id, 1)
        self.s.reservas.cancelar(self.cliente, r.id)
        self.assertEqual(self.s.catalogo.consultar_disponibilidad(self.cliente, self.paq.id).cupos_libres, 5)

    def test_paquete_con_reservas_no_se_elimina(self):
        self.s.reservas.reservar(self.cliente, self.paq.id, 1)
        with self.assertRaises(ErrorValidacion):
            self.s.catalogo.eliminar_paquete(self.admin, self.paq.id)

    def test_auditoria_registra_eventos(self):
        acciones = [a["accion"] for a in self.s.auditoria.ultimos(50)]
        self.assertIn("PAQUETE_CREADO", acciones)
        self.assertIn("REGISTRO", acciones)


if __name__ == "__main__":
    unittest.main()
