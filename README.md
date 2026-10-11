# Viajes Aventura – Sistema de gestión (TI3V21 · ES3) · versión con interfaz gráfica

Aplicación de escritorio (Tkinter) y de consola en Python 3.10+ para gestionar destinos, paquetes turísticos y reservas,
con persistencia en SQLite y acceso seguro (bcrypt + Fernet).

## Instalación

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |  Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
python gui.py --demo    # interfaz gráfica; la primera vez carga datos de ejemplo
python gui.py           # interfaz gráfica, uso normal
python main.py          # versión de consola (misma base de datos)
```
Tkinter viene incluido con Python en Windows y macOS. En Linux puede requerir `sudo apt install python3-tk`.
Cuentas de la demo:

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | admin@viajesaventura.cl | Admin#2026 |
| Cliente | camila@correo.cl | Viaje#2026 |

Sin `--demo` y con la base vacía, el sistema pide crear el administrador inicial.

## Pruebas

```bash
python -m unittest -v          # 20 pruebas automatizadas
bandit -r . -x ./tests         # análisis estático de seguridad
pip-audit -r requirements.txt  # vulnerabilidades conocidas en dependencias
```

## Estructura

| Archivo | Responsabilidad |
|---|---|
| `gui.py` | Interfaz gráfica Tkinter: login, registro, vistas de cliente y administrador |
| `main.py` | Interfaz de consola y menús por rol |
| `modelos.py` | Clases del dominio (diagrama de clases UML) |
| `servicios.py` | Reglas de negocio, autenticación y autorización |
| `repositorios.py` | Persistencia (patrón Repositorio, CRUD) |
| `database.py` | Conexión SQLite, esquema y transacciones |
| `seguridad.py` | bcrypt, cifrado Fernet, política de contraseñas |
| `validaciones.py` | Validación de entradas (RUT, correo, fechas, montos) |
| `config.py` | Parámetros del sistema |
| `tests/` | Pruebas unitarias e integración |

## Seguridad

- La clave de cifrado se lee de la variable `VA_FERNET_KEY` o del archivo `secret.key`
  (creado con permisos 600). Ese archivo y la base de datos están en `.gitignore`.
- Si se pierde `secret.key`, los RUT y teléfonos guardados no se pueden recuperar.

## Interfaz gráfica

- **Cliente:** paquetes disponibles con cupos libres y total estimado, reserva, cotizador de destinos, historial con cancelación y datos personales enmascarados.
- **Administrador:** CRUD de destinos y paquetes con formularios, listado de todas las reservas y bitácora de auditoría.
- La GUI es solo presentación: llama a los mismos servicios (`servicios.py`), así que validaciones, bcrypt, cifrado, bloqueo de cuenta y control por rol funcionan igual que en consola. Los errores se muestran sin detalles técnicos y la contraseña se borra del formulario después de cada intento.
