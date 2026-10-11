"""Versión de consola. Uso: python main.py [--demo]"""
import sys
from datetime import date, timedelta
from getpass import getpass

from servicios import ErrorAutenticacion, ErrorAutorizacion, Sistema
from seguridad import enmascarar
from validaciones import ErrorValidacion
from modelos import Cliente

SEP = "-" * 70

def pedir(texto: str) -> str:
    return input(f"{texto}: ").strip()


def pedir_ids(texto: str) -> list[int]:
    crudo = pedir(texto + " (ids separados por coma)")
    try:
        return [int(x) for x in crudo.split(",") if x.strip()]
    except ValueError:
        raise ErrorValidacion("Debe ingresar números separados por coma.") from None


def menu_admin(s: Sistema, u):
    opciones = {
        "1": ("Listar destinos", lambda: [print(d.resumen(), "" if d.activo else "(inactivo)")
                                          for d in s.catalogo.listar_destinos(u)]),
        "2": ("Registrar destino", lambda: print("Creado:", s.catalogo.crear_destino(
            u, pedir("Nombre"), pedir("País"), pedir("Descripción"), pedir("Costo base (CLP)")).resumen())),
        "3": ("Modificar destino", lambda: print("Actualizado:", s.catalogo.modificar_destino(
            u, pedir("Id destino"), nombre=pedir("Nuevo nombre (Enter = igual)"),
            pais=pedir("Nuevo país (Enter = igual)"), descripcion=pedir("Nueva descripción (Enter = igual)"),
            costo_base=pedir("Nuevo costo (Enter = igual)")).resumen())),
        "4": ("Eliminar destino", lambda: print("Destino", s.catalogo.eliminar_destino(u, pedir("Id destino")))),
        "5": ("Listar paquetes", lambda: [print(p.resumen()) for p in s.catalogo.listar_paquetes(u)]),
        "6": ("Crear paquete", lambda: print("Creado:", s.catalogo.crear_paquete(
            u, pedir("Nombre"), pedir("Fecha inicio AAAA-MM-DD"), pedir("Fecha fin AAAA-MM-DD"),
            pedir("Cupos"), pedir_ids("Destinos")).resumen())),
        "7": ("Modificar paquete", lambda: print("Actualizado:", s.catalogo.modificar_paquete(
            u, pedir("Id paquete"), nombre=pedir("Nuevo nombre (Enter = igual)") or None,
            fecha_inicio=pedir("Nueva fecha inicio (Enter = igual)") or None,
            fecha_fin=pedir("Nueva fecha fin (Enter = igual)") or None,
            cupos=pedir("Nuevos cupos (Enter = igual)") or None,
            destino_ids=pedir_ids("Nuevos destinos (Enter = igual)") or None).resumen())),
        "8": ("Eliminar paquete", lambda: (s.catalogo.eliminar_paquete(u, pedir("Id paquete")),
                                           print("Paquete eliminado."))),
        "9": ("Disponibilidad de paquete", lambda: mostrar_disponibilidad(s, u)),
        "10": ("Ver todas las reservas", lambda: [print(r.resumen(), f"| cliente #{r.cliente_id}")
                                                 for r in s.reservas.todas(u)]),
        "11": ("Ver auditoría", lambda: [print(f"{a['fecha']} | usr {a['usuario_id']} | {a['accion']} {a['detalle']}")
                                        for a in s.auditoria.ultimos()]),
    }
    ciclo_menu(f"ADMINISTRADOR: {u.nombre}", opciones)


def menu_cliente(s: Sistema, u: Cliente):
    opciones = {
        "1": ("Ver paquetes disponibles", lambda: [print(p.resumen()) for p in s.catalogo.listar_paquetes(u)]),
        "2": ("Ver destinos", lambda: [print(d.resumen()) for d in s.catalogo.listar_destinos(u)]),
        "3": ("Cotizar combinación de destinos", lambda: print(
            f"Costo por persona: ${s.catalogo.cotizar_destinos(u, pedir_ids('Destinos')):,.0f}")),
        "4": ("Consultar disponibilidad", lambda: mostrar_disponibilidad(s, u)),
        "5": ("Reservar paquete", lambda: print("Reserva confirmada:", s.reservas.reservar(
            u, pedir("Id paquete"), pedir("Cantidad de personas")).resumen())),
        "6": ("Mi historial de reservas", lambda: [print(r.resumen()) for r in s.reservas.historial(u)]
              or print("(sin reservas)")),
        "7": ("Cancelar una reserva", lambda: print("Cancelada:", s.reservas.cancelar(
            u, pedir("Id reserva")).resumen())),
        "8": ("Mis datos", lambda: print(f"{u.nombre} | {u.email} | RUT {enmascarar(u.rut)} | "
                                         f"Tel {enmascarar(u.telefono, 4)}")),
    }
    ciclo_menu(f"CLIENTE: {u.nombre}", opciones)


def mostrar_disponibilidad(s, u):
    d = s.catalogo.consultar_disponibilidad(u, pedir("Id paquete"))
    print(f"Cupos totales {d.cupos_totales} | reservados {d.cupos_reservados} | libres {d.cupos_libres}")


def ciclo_menu(titulo: str, opciones: dict):
    while True:
        print(f"\n{SEP}\n{titulo}\n{SEP}")
        for k, (texto, _) in opciones.items():
            print(f"{k:>3}. {texto}")
        print("  0. Cerrar sesión")
        eleccion = pedir("Opción")
        if eleccion == "0":
            return
        if eleccion not in opciones:
            print("Opción inválida.")
            continue
        ejecutar_seguro(opciones[eleccion][1])


def ejecutar_seguro(accion):
    try:
        accion()
    except (ErrorValidacion, ErrorAutorizacion, ErrorAutenticacion) as e:
        print(f"[!] {e}")
    except Exception:
        print("[!] Ocurrió un error inesperado. Intente nuevamente.")


def registrar(s: Sistema):
    c = s.auth.registrar_cliente(pedir("Nombre completo"), pedir("Correo"), getpass("Contraseña: "),
                                 getpass("Repita la contraseña: "), pedir("RUT (12345678-9)"),
                                 pedir("Teléfono (+569...)"))
    print(f"Cuenta creada para {c.nombre}. Ya puede iniciar sesión.")


def iniciar_sesion(s: Sistema):
    u = s.auth.iniciar_sesion(pedir("Correo"), getpass("Contraseña: "))
    (menu_admin if u.puede("gestionar_destinos") else menu_cliente)(s, u)


def configurar_primer_admin(s: Sistema):
    print("No existe un administrador. Cree la cuenta inicial.")
    while True:
        try:
            s.auth.crear_administrador(pedir("Nombre"), pedir("Correo"), getpass("Contraseña: "))
            print("Administrador creado.")
            return
        except ErrorValidacion as e:
            print(f"[!] {e}")


def cargar_demo(s: Sistema):
    if s.usuarios.listar():
        print("La base de datos ya tiene datos; no se cargó la demo.")
        return
    admin = s.auth.crear_administrador("Admin Agencia", "admin@viajesaventura.cl", "Admin#2026")
    ids = [s.catalogo.crear_destino(admin, *d).id for d in [
        ("Torres del Paine", "Chile", "Trekking y glaciares en la Patagonia", 450000),
        ("San Pedro de Atacama", "Chile", "Desierto, géiseres y salares", 320000),
        ("Machu Picchu", "Perú", "Ciudadela inca y Valle Sagrado", 580000),
        ("Bariloche", "Argentina", "Lagos, montaña y centro de esquí", 390000),
    ]]
    inicio = date.today() + timedelta(days=30)
    s.catalogo.crear_paquete(admin, "Ruta Patagónica", inicio, inicio + timedelta(days=7), 20, [ids[0], ids[3]])
    s.catalogo.crear_paquete(admin, "Norte y Andes", inicio + timedelta(days=15),
                             inicio + timedelta(days=24), 15, [ids[1], ids[2]])
    s.auth.registrar_cliente("Camila Rojas", "camila@correo.cl", "Viaje#2026", "Viaje#2026",
                             "11111111-1", "+56912345678")
    print("Demo cargada. Admin: admin@viajesaventura.cl / Admin#2026 | "
          "Cliente: camila@correo.cl / Viaje#2026")


def main():
    s = Sistema()
    try:
        if "--demo" in sys.argv:
            cargar_demo(s)
        if not s.usuarios.existe_admin():
            configurar_primer_admin(s)
        while True:
            print(f"\n{SEP}\nVIAJES AVENTURA - Sistema de gestión\n{SEP}")
            print("  1. Iniciar sesión\n  2. Registrarse como cliente\n  0. Salir")
            op = pedir("Opción")
            if op == "1":
                ejecutar_seguro(lambda: iniciar_sesion(s))
            elif op == "2":
                ejecutar_seguro(lambda: registrar(s))
            elif op == "0":
                print("Hasta pronto.")
                break
    except (KeyboardInterrupt, EOFError):
        print("\nSesión finalizada.")
    finally:
        s.cerrar()


if __name__ == "__main__":
    main()
