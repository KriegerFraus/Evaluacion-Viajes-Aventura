"""Interfaz gráfica de Viajes Aventura.

Uso: python gui.py [--demo]
"""
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from main import cargar_demo
from seguridad import enmascarar
from servicios import ErrorAutenticacion, ErrorAutorizacion, Sistema
from validaciones import ErrorValidacion

COLOR = {
    "fondo": "#F5F3EE", "panel": "#FFFFFF", "texto": "#1F2933", "suave": "#5F6B76",
    "acento": "#0F6E6E", "acento_hover": "#0B5555", "borde": "#D9D4C7", "error": "#B42318",
}
FUENTE = ("Segoe UI", 10)
FUENTE_TITULO = ("Segoe UI Semibold", 16)
FUENTE_SUB = ("Segoe UI Semibold", 11)

def configurar_estilos(raiz: tk.Tk) -> None:
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    raiz.configure(bg=COLOR["fondo"])
    estilo.configure(".", font=FUENTE, background=COLOR["fondo"], foreground=COLOR["texto"])
    estilo.configure("Panel.TFrame", background=COLOR["panel"])
    estilo.configure("Panel.TLabel", background=COLOR["panel"])
    estilo.configure("Titulo.TLabel", font=FUENTE_TITULO, background=COLOR["fondo"])
    estilo.configure("TituloPanel.TLabel", font=FUENTE_TITULO, background=COLOR["panel"])
    estilo.configure("Sub.TLabel", font=FUENTE_SUB, background=COLOR["panel"])
    estilo.configure("Suave.TLabel", foreground=COLOR["suave"], background=COLOR["panel"])
    estilo.configure("Barra.TFrame", background=COLOR["acento"])
    estilo.configure("Barra.TLabel", background=COLOR["acento"], foreground="white", font=FUENTE_SUB)
    estilo.configure("BarraSuave.TLabel", background=COLOR["acento"], foreground="#CFE6E6")
    estilo.configure("Accent.TButton", background=COLOR["acento"], foreground="white",
                     borderwidth=0, padding=(14, 7), font=FUENTE_SUB)
    estilo.map("Accent.TButton", background=[("active", COLOR["acento_hover"])])
    estilo.configure("TButton", padding=(12, 6), background="#ECE8DE", borderwidth=1)
    estilo.map("TButton", background=[("active", "#E0DACB")])
    estilo.configure("Peligro.TButton", foreground=COLOR["error"], padding=(12, 6))
    estilo.configure("Salir.TButton", background=COLOR["acento"], foreground="white", borderwidth=1)
    estilo.map("Salir.TButton", background=[("active", COLOR["acento_hover"])])
    estilo.configure("TEntry", padding=6, fieldbackground="white")
    estilo.configure("TNotebook", background=COLOR["fondo"], borderwidth=0)
    estilo.configure("TNotebook.Tab", padding=(16, 8), font=FUENTE_SUB)
    estilo.map("TNotebook.Tab", background=[("selected", COLOR["panel"])])
    estilo.configure("Treeview", rowheight=28, fieldbackground="white", borderwidth=0)
    estilo.configure("Treeview.Heading", font=FUENTE_SUB, background="#ECE8DE", relief="flat")
    estilo.map("Treeview", background=[("selected", COLOR["acento"])])


def accion_segura(func):
    def envoltura(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ErrorValidacion, ErrorAutorizacion, ErrorAutenticacion) as e:
            messagebox.showerror("Viajes Aventura", str(e))
        except Exception:
            messagebox.showerror("Viajes Aventura", "Ocurrió un error inesperado. Intente nuevamente.")
    return envoltura


def pesos(monto: float) -> str:
    return "$" + f"{monto:,.0f}".replace(",", ".")


class Tabla(ttk.Frame):
    def __init__(self, padre, columnas: list[tuple[str, str, int]], alto: int = 10):
        super().__init__(padre, style="Panel.TFrame")
        self.arbol = ttk.Treeview(self, columns=[c[0] for c in columnas], show="headings",
                                  height=alto, selectmode="browse")
        for clave, titulo, ancho in columnas:
            self.arbol.heading(clave, text=titulo, anchor="w")
            self.arbol.column(clave, width=ancho, anchor="w", stretch=True)
        barra = ttk.Scrollbar(self, orient="vertical", command=self.arbol.yview)
        self.arbol.configure(yscrollcommand=barra.set)
        self.arbol.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.arbol.tag_configure("par", background="#FAF8F3")
        self.arbol.tag_configure("inactivo", foreground="#9AA2A9")

    def cargar(self, filas: list[tuple], tags: list[tuple] | None = None) -> None:
        previa = self.arbol.selection()
        self.arbol.delete(*self.arbol.get_children())
        for i, fila in enumerate(filas):
            extra = tags[i] if tags else ()
            self.arbol.insert("", "end", iid=str(fila[0]), values=fila,
                              tags=(("par",) if i % 2 else ()) + extra)
        vigentes = [i for i in previa if self.arbol.exists(i)]
        if vigentes:
            self.arbol.selection_set(vigentes)

    def seleccion(self) -> int | None:
        sel = self.arbol.selection()
        return int(sel[0]) if sel else None


class Formulario(ttk.Frame):
    def __init__(self, padre, campos: list[tuple[str, str]], ocultos: tuple = ()):
        super().__init__(padre, style="Panel.TFrame")
        self.vars: dict[str, tk.StringVar] = {}
        for fila, (clave, etiqueta) in enumerate(campos):
            ttk.Label(self, text=etiqueta, style="Panel.TLabel").grid(row=fila * 2, column=0, sticky="w",
                                                                      pady=(8 if fila else 0, 2))
            var = tk.StringVar()
            entrada = ttk.Entry(self, textvariable=var, width=34, show="•" if clave in ocultos else "")
            entrada.grid(row=fila * 2 + 1, column=0, sticky="ew")
            self.vars[clave] = var
        self.columnconfigure(0, weight=1)

    def valores(self) -> dict[str, str]:
        return {k: v.get().strip() for k, v in self.vars.items()}

    def poner(self, **valores) -> None:
        for k, v in valores.items():
            self.vars[k].set("" if v is None else str(v))

    def limpiar(self) -> None:
        for v in self.vars.values():
            v.set("")


def panel(padre, titulo: str | None = None) -> ttk.Frame:
    marco = ttk.Frame(padre, style="Panel.TFrame", padding=16)
    if titulo:
        ttk.Label(marco, text=titulo, style="Sub.TLabel").pack(anchor="w", pady=(0, 10))
    return marco


class App(tk.Tk):
    def __init__(self, sistema: Sistema):
        super().__init__()
        self.s = sistema
        self.usuario = None
        self.title("Viajes Aventura – Sistema de gestión")
        self.geometry("1100x700")
        self.minsize(960, 600)
        configurar_estilos(self)
        self.protocol("WM_DELETE_WINDOW", self.salir)
        self.contenedor = ttk.Frame(self)
        self.contenedor.pack(fill="both", expand=True)
        if not self.s.usuarios.existe_admin():
            self.mostrar(PantallaPrimerAdmin)
        else:
            self.mostrar(PantallaLogin)

    def mostrar(self, clase, **kwargs) -> None:
        self.unbind_all("<Return>")
        for hijo in self.contenedor.winfo_children():
            hijo.destroy()
        clase(self.contenedor, self, **kwargs).pack(fill="both", expand=True)

    def iniciar_sesion(self, usuario) -> None:
        self.usuario = usuario
        vista = VistaAdmin if usuario.puede("gestionar_destinos") else VistaCliente
        self.mostrar(vista)

    def cerrar_sesion(self) -> None:
        self.usuario = None
        self.mostrar(PantallaLogin)

    def salir(self) -> None:
        self.s.cerrar()
        self.destroy()


class PantallaCentrada(ttk.Frame):
    def __init__(self, padre, titulo: str, subtitulo: str):
        super().__init__(padre)
        self.tarjeta = ttk.Frame(self, style="Panel.TFrame", padding=32)
        self.tarjeta.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(self.tarjeta, text="VIAJES AVENTURA", style="Suave.TLabel",
                  font=("Segoe UI Semibold", 9)).pack(anchor="w")
        ttk.Label(self.tarjeta, text=titulo, style="TituloPanel.TLabel").pack(anchor="w")
        ttk.Label(self.tarjeta, text=subtitulo, style="Suave.TLabel").pack(anchor="w", pady=(2, 18))


class PantallaLogin(PantallaCentrada):
    def __init__(self, padre, app: App):
        super().__init__(padre, "Iniciar sesión", "Ingrese con su correo y contraseña.")
        self.app = app
        self.form = Formulario(self.tarjeta, [("email", "Correo electrónico"), ("password", "Contraseña")],
                               ocultos=("password",))
        self.form.pack(fill="x")
        ttk.Button(self.tarjeta, text="Ingresar", style="Accent.TButton",
                   command=self.ingresar).pack(fill="x", pady=(20, 8))
        ttk.Button(self.tarjeta, text="¿No tiene cuenta? Crear cuenta de cliente",
                   command=lambda: app.mostrar(PantallaRegistro)).pack(fill="x")
        self.bind_all("<Return>", lambda _e: self.ingresar())

    @accion_segura
    def ingresar(self) -> None:
        datos = self.form.valores()
        try:
            usuario = self.app.s.auth.iniciar_sesion(datos["email"], datos["password"])
        finally:
            self.form.vars["password"].set("")  # no dejar la clave en memoria de la GUI
        self.app.iniciar_sesion(usuario)


class PantallaRegistro(PantallaCentrada):
    def __init__(self, padre, app: App):
        super().__init__(padre, "Crear cuenta", "Su RUT y teléfono se guardan cifrados.")
        self.app = app
        self.form = Formulario(self.tarjeta, [
            ("nombre", "Nombre completo"), ("email", "Correo electrónico"),
            ("rut", "RUT (12345678-9)"), ("telefono", "Teléfono (+569…)"),
            ("password", "Contraseña"), ("confirmacion", "Repita la contraseña"),
        ], ocultos=("password", "confirmacion"))
        self.form.pack(fill="x")
        ttk.Label(self.tarjeta, text="Mínimo 8 caracteres con mayúscula, minúscula, número y símbolo.",
                  style="Suave.TLabel", font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))
        botones = ttk.Frame(self.tarjeta, style="Panel.TFrame")
        botones.pack(fill="x", pady=(18, 0))
        ttk.Button(botones, text="Registrarme", style="Accent.TButton",
                   command=self.registrar).pack(side="left")
        ttk.Button(botones, text="Volver", command=lambda: app.mostrar(PantallaLogin)).pack(side="right")

    @accion_segura
    def registrar(self) -> None:
        d = self.form.valores()
        cliente = self.app.s.auth.registrar_cliente(d["nombre"], d["email"], d["password"],
                                                    d["confirmacion"], d["rut"], d["telefono"])
        messagebox.showinfo("Cuenta creada", f"Bienvenido/a, {cliente.nombre}. Ya puede iniciar sesión.")
        self.app.mostrar(PantallaLogin)


class PantallaPrimerAdmin(PantallaCentrada):
    def __init__(self, padre, app: App):
        super().__init__(padre, "Configuración inicial", "Cree la cuenta del administrador de la agencia.")
        self.app = app
        self.form = Formulario(self.tarjeta, [("nombre", "Nombre"), ("email", "Correo electrónico"),
                                              ("password", "Contraseña")], ocultos=("password",))
        self.form.pack(fill="x")
        ttk.Button(self.tarjeta, text="Crear administrador", style="Accent.TButton",
                   command=self.crear).pack(anchor="w", pady=(18, 0))

    @accion_segura
    def crear(self) -> None:
        d = self.form.valores()
        self.app.s.auth.crear_administrador(d["nombre"], d["email"], d["password"])
        messagebox.showinfo("Listo", "Administrador creado. Inicie sesión.")
        self.app.mostrar(PantallaLogin)


class VistaBase(ttk.Frame):
    def __init__(self, padre, app: App, rol: str):
        super().__init__(padre)
        self.app, self.s, self.u = app, app.s, app.usuario
        barra = ttk.Frame(self, style="Barra.TFrame", padding=(20, 12))
        barra.pack(fill="x")
        ttk.Label(barra, text="Viajes Aventura", style="Barra.TLabel").pack(side="left")
        ttk.Label(barra, text=f"   {rol}", style="BarraSuave.TLabel").pack(side="left")
        ttk.Button(barra, text="Cerrar sesión", style="Salir.TButton",
                   command=app.cerrar_sesion).pack(side="right")
        ttk.Label(barra, text=f"{self.u.nombre}  ", style="Barra.TLabel").pack(side="right")
        self.pestanas = ttk.Notebook(self)
        self.pestanas.pack(fill="both", expand=True, padx=16, pady=16)
        self.pestanas.bind("<<NotebookTabChanged>>", lambda _e: self.refrescar())

    def refrescar(self) -> None:
        pass


class VistaCliente(VistaBase):
    def __init__(self, padre, app: App):
        super().__init__(padre, app, "Cliente")
        self._paquetes = {}
        self._crear_paquetes()
        self._crear_cotizador()
        self._crear_reservas()
        self._crear_datos()
        self.refrescar()

    # --- Paquetes y reserva
    def _crear_paquetes(self):
        tab = panel(self.pestanas)
        self.pestanas.add(tab, text="Paquetes disponibles")
        self.t_paq = Tabla(tab, [("id", "#", 36), ("nombre", "Paquete", 150), ("fechas", "Fechas", 210),
                                 ("dias", "Días", 50), ("destinos", "Destinos", 270), ("costo", "Costo p/p", 100),
                                 ("libres", "Cupos libres", 90)], alto=12)
        self.t_paq.pack(fill="both", expand=True)
        abajo = ttk.Frame(tab, style="Panel.TFrame")
        abajo.pack(fill="x", pady=(12, 0))
        ttk.Label(abajo, text="Personas:", style="Panel.TLabel").pack(side="left")
        self.personas = tk.Spinbox(abajo, from_=1, to=20, width=5, font=FUENTE)
        self.personas.pack(side="left", padx=(6, 16))
        self.total = ttk.Label(abajo, text="Seleccione un paquete", style="Suave.TLabel")
        self.total.pack(side="left")
        ttk.Button(abajo, text="Reservar", style="Accent.TButton", command=self.reservar).pack(side="right")
        self.t_paq.arbol.bind("<<TreeviewSelect>>", lambda _e: self._actualizar_total())
        self.personas.configure(command=self._actualizar_total)

    def _actualizar_total(self):
        pid = self.t_paq.seleccion()
        if pid is None:
            return
        try:
            n = int(self.personas.get())
        except ValueError:
            n = 1
        self.total.configure(text=f"Total estimado: {pesos(self._paquetes[pid].calcular_costo() * n)}")

    @accion_segura
    def reservar(self):
        pid = self.t_paq.seleccion()
        if pid is None:
            raise ErrorValidacion("Seleccione un paquete de la lista.")
        r = self.s.reservas.reservar(self.u, pid, self.personas.get())
        messagebox.showinfo("Reserva confirmada",
                            f"Reserva #{r.id}\n{r.paquete.nombre}\n{r.cantidad_personas} persona(s)\n"
                            f"Total: {pesos(r.monto_total)}")
        self.refrescar()

    # --- Cotizador
    def _crear_cotizador(self):
        tab = panel(self.pestanas, "Elija uno o más destinos para conocer el costo por persona")
        self.pestanas.add(tab, text="Cotizar")
        self.lista_dest = tk.Listbox(tab, selectmode="multiple", height=12, font=FUENTE, bd=0,
                                     highlightthickness=1, highlightcolor=COLOR["borde"],
                                     selectbackground=COLOR["acento"], selectforeground="white", activestyle="none")
        self.lista_dest.pack(fill="both", expand=True)
        abajo = ttk.Frame(tab, style="Panel.TFrame")
        abajo.pack(fill="x", pady=(12, 0))
        self.cotizacion = ttk.Label(abajo, text="", style="Sub.TLabel")
        self.cotizacion.pack(side="left")
        ttk.Button(abajo, text="Cotizar", style="Accent.TButton", command=self.cotizar).pack(side="right")

    @accion_segura
    def cotizar(self):
        ids = [self._ids_dest[i] for i in self.lista_dest.curselection()]
        if not ids:
            raise ErrorValidacion("Seleccione al menos un destino.")
        costo = self.s.catalogo.cotizar_destinos(self.u, ids)
        self.cotizacion.configure(text=f"Costo por persona: {pesos(costo)}  (incluye 15 % de la agencia)")

    # --- Reservas
    def _crear_reservas(self):
        tab = panel(self.pestanas)
        self.pestanas.add(tab, text="Mis reservas")
        self.t_res = Tabla(tab, [("id", "#", 50), ("paquete", "Paquete", 200), ("personas", "Personas", 80),
                                 ("monto", "Monto", 120), ("estado", "Estado", 110), ("fecha", "Fecha", 150)])
        self.t_res.pack(fill="both", expand=True)
        ttk.Button(tab, text="Cancelar reserva seleccionada", style="Peligro.TButton",
                   command=self.cancelar).pack(anchor="e", pady=(12, 0))

    @accion_segura
    def cancelar(self):
        rid = self.t_res.seleccion()
        if rid is None:
            raise ErrorValidacion("Seleccione una reserva.")
        if messagebox.askyesno("Confirmar", f"¿Cancelar la reserva #{rid}? Los cupos quedarán libres."):
            self.s.reservas.cancelar(self.u, rid)
            self.refrescar()

    # --- Datos
    def _crear_datos(self):
        tab = panel(self.pestanas, "Mis datos")
        self.pestanas.add(tab, text="Mis datos")
        for etiqueta, valor in [("Nombre", self.u.nombre), ("Correo", self.u.email),
                                ("RUT", enmascarar(self.u.rut)), ("Teléfono", enmascarar(self.u.telefono, 4))]:
            fila = ttk.Frame(tab, style="Panel.TFrame")
            fila.pack(fill="x", pady=4)
            ttk.Label(fila, text=etiqueta, style="Suave.TLabel", width=12).pack(side="left")
            ttk.Label(fila, text=valor, style="Panel.TLabel").pack(side="left")
        ttk.Label(tab, text="El RUT y el teléfono se almacenan cifrados y se muestran enmascarados.",
                  style="Suave.TLabel").pack(anchor="w", pady=(16, 0))

    @accion_segura
    def refrescar(self):
        paquetes = self.s.catalogo.listar_paquetes(self.u)
        self._paquetes = {p.id: p for p in paquetes}
        filas = []
        for p in paquetes:
            libres = self.s.catalogo.consultar_disponibilidad(self.u, p.id).cupos_libres
            filas.append((p.id, p.nombre, f"{p.fecha_inicio} a {p.fecha_fin}", p.duracion_dias,
                          ", ".join(d.nombre for d in p.destinos), pesos(p.calcular_costo()), libres))
        self.t_paq.cargar(filas)
        destinos = self.s.catalogo.listar_destinos(self.u)
        self._ids_dest = [d.id for d in destinos]
        self.lista_dest.delete(0, "end")
        for d in destinos:
            self.lista_dest.insert("end", f"  {d.nombre} ({d.pais}) — {pesos(d.costo_base)}")
        self.t_res.cargar([(r.id, r.paquete.nombre, r.cantidad_personas, pesos(r.monto_total),
                            r.estado.value.capitalize(), f"{r.fecha_reserva:%Y-%m-%d %H:%M}")
                           for r in self.s.reservas.historial(self.u)])


class VistaAdmin(VistaBase):
    def __init__(self, padre, app: App):
        super().__init__(padre, app, "Administrador")
        self._crear_destinos()
        self._crear_paquetes()
        self._crear_reservas()
        self._crear_auditoria()
        self.refrescar()

    # --- Destinos (CRUD)
    def _crear_destinos(self):
        tab = ttk.Frame(self.pestanas, style="Panel.TFrame", padding=16)
        self.pestanas.add(tab, text="Destinos")
        izq = ttk.Frame(tab, style="Panel.TFrame")
        izq.pack(side="left", fill="both", expand=True)
        self.t_dest = Tabla(izq, [("id", "#", 40), ("nombre", "Destino", 180), ("pais", "País", 100),
                                  ("costo", "Costo base", 110), ("estado", "Estado", 90)], alto=14)
        self.t_dest.pack(fill="both", expand=True)
        self.t_dest.arbol.bind("<<TreeviewSelect>>", lambda _e: self._cargar_destino())
        der = panel(tab, "Datos del destino")
        der.pack(side="right", fill="y", padx=(16, 0))
        self.f_dest = Formulario(der, [("nombre", "Nombre"), ("pais", "País"),
                                       ("descripcion", "Descripción"), ("costo", "Costo base (CLP)")])
        self.f_dest.pack(fill="x")
        for texto, estilo, cmd in [("Nuevo destino", "Accent.TButton", self.crear_destino),
                                   ("Guardar cambios", "TButton", self.modificar_destino),
                                   ("Eliminar", "Peligro.TButton", self.eliminar_destino),
                                   ("Limpiar formulario", "TButton", self._limpiar_destino)]:
            ttk.Button(der, text=texto, style=estilo, command=cmd).pack(fill="x", pady=(10 if texto == "Nuevo destino" else 4, 0))

    def _cargar_destino(self):
        did = self.t_dest.seleccion()
        d = next((x for x in self._destinos if x.id == did), None)
        if d:
            self.f_dest.poner(nombre=d.nombre, pais=d.pais, descripcion=d.descripcion, costo=int(d.costo_base))

    def _limpiar_destino(self):
        self.t_dest.arbol.selection_remove(self.t_dest.arbol.selection())
        self.f_dest.limpiar()

    @accion_segura
    def crear_destino(self):
        v = self.f_dest.valores()
        self.s.catalogo.crear_destino(self.u, v["nombre"], v["pais"], v["descripcion"], v["costo"])
        self.f_dest.limpiar()
        self.refrescar()

    @accion_segura
    def modificar_destino(self):
        did = self.t_dest.seleccion()
        if did is None:
            raise ErrorValidacion("Seleccione el destino a modificar.")
        v = self.f_dest.valores()
        self.s.catalogo.modificar_destino(self.u, did, nombre=v["nombre"], pais=v["pais"],
                                          descripcion=v["descripcion"], costo_base=v["costo"])
        self.refrescar()

    @accion_segura
    def eliminar_destino(self):
        did = self.t_dest.seleccion()
        if did is None:
            raise ErrorValidacion("Seleccione el destino a eliminar.")
        if messagebox.askyesno("Confirmar", f"¿Eliminar el destino #{did}?"):
            resultado = self.s.catalogo.eliminar_destino(self.u, did)
            if resultado == "desactivado":
                messagebox.showinfo("Destino desactivado",
                                    "El destino forma parte de un paquete: se desactivó para conservar el historial.")
            self.f_dest.limpiar()
            self.refrescar()

    # --- Paquetes (CRUD)
    def _crear_paquetes(self):
        tab = ttk.Frame(self.pestanas, style="Panel.TFrame", padding=16)
        self.pestanas.add(tab, text="Paquetes")
        izq = ttk.Frame(tab, style="Panel.TFrame")
        izq.pack(side="left", fill="both", expand=True)
        self.t_paq = Tabla(izq, [("id", "#", 40), ("nombre", "Paquete", 130), ("fechas", "Fechas", 190),
                                 ("costo", "Costo p/p", 95), ("cupos", "Reservados / total", 130)], alto=14)
        self.t_paq.pack(fill="both", expand=True)
        self.t_paq.arbol.bind("<<TreeviewSelect>>", lambda _e: self._cargar_paquete())
        der = panel(tab, "Datos del paquete")
        der.pack(side="right", fill="y", padx=(16, 0))
        self.f_paq = Formulario(der, [("nombre", "Nombre"), ("inicio", "Fecha inicio (AAAA-MM-DD)"),
                                      ("fin", "Fecha término (AAAA-MM-DD)"), ("cupos", "Cupos totales")])
        self.f_paq.pack(fill="x")
        ttk.Label(der, text="Destinos (Ctrl + clic para varios)", style="Panel.TLabel").pack(anchor="w", pady=(8, 2))
        self.lista_paq_dest = tk.Listbox(der, selectmode="extended", height=4, exportselection=False,
                                         font=FUENTE, bd=0, highlightthickness=1,
                                         selectbackground=COLOR["acento"], selectforeground="white", activestyle="none")
        self.lista_paq_dest.pack(fill="x")
        ttk.Button(der, text="Nuevo paquete", style="Accent.TButton",
                   command=self.crear_paquete).pack(fill="x", pady=(10, 4))
        fila = ttk.Frame(der, style="Panel.TFrame")
        fila.pack(fill="x")
        ttk.Button(fila, text="Guardar cambios", command=self.modificar_paquete).pack(side="left", fill="x", expand=True)
        ttk.Button(fila, text="Eliminar", style="Peligro.TButton",
                   command=self.eliminar_paquete).pack(side="left", padx=(4, 0))

    def _destinos_elegidos(self) -> list[int]:
        return [self._ids_activos[i] for i in self.lista_paq_dest.curselection()]

    def _cargar_paquete(self):
        pid = self.t_paq.seleccion()
        p = next((x for x in self._paquetes if x.id == pid), None)
        if not p:
            return
        self.f_paq.poner(nombre=p.nombre, inicio=p.fecha_inicio, fin=p.fecha_fin, cupos=p.cupos_totales)
        self.lista_paq_dest.selection_clear(0, "end")
        for d in p.destinos:
            if d.id in self._ids_activos:
                self.lista_paq_dest.selection_set(self._ids_activos.index(d.id))

    @accion_segura
    def crear_paquete(self):
        v = self.f_paq.valores()
        self.s.catalogo.crear_paquete(self.u, v["nombre"], v["inicio"], v["fin"], v["cupos"],
                                      self._destinos_elegidos())
        self.f_paq.limpiar()
        self.refrescar()

    @accion_segura
    def modificar_paquete(self):
        pid = self.t_paq.seleccion()
        if pid is None:
            raise ErrorValidacion("Seleccione el paquete a modificar.")
        v = self.f_paq.valores()
        self.s.catalogo.modificar_paquete(self.u, pid, nombre=v["nombre"] or None,
                                          fecha_inicio=v["inicio"] or None, fecha_fin=v["fin"] or None,
                                          cupos=v["cupos"] or None, destino_ids=self._destinos_elegidos() or None)
        self.refrescar()

    @accion_segura
    def eliminar_paquete(self):
        pid = self.t_paq.seleccion()
        if pid is None:
            raise ErrorValidacion("Seleccione el paquete a eliminar.")
        if messagebox.askyesno("Confirmar", f"¿Eliminar el paquete #{pid}?"):
            self.s.catalogo.eliminar_paquete(self.u, pid)
            self.f_paq.limpiar()
            self.refrescar()

    # --- Reservas y auditoría (solo lectura)
    def _crear_reservas(self):
        tab = panel(self.pestanas)
        self.pestanas.add(tab, text="Reservas")
        self.t_res = Tabla(tab, [("id", "#", 50), ("cliente", "Cliente #", 80), ("paquete", "Paquete", 200),
                                 ("personas", "Personas", 80), ("monto", "Monto", 120),
                                 ("estado", "Estado", 110), ("fecha", "Fecha", 150)], alto=16)
        self.t_res.pack(fill="both", expand=True)

    def _crear_auditoria(self):
        tab = panel(self.pestanas)
        self.pestanas.add(tab, text="Auditoría")
        self.t_aud = Tabla(tab, [("id", "#", 50), ("fecha", "Fecha", 160), ("usuario", "Usuario #", 90),
                                 ("accion", "Acción", 200), ("detalle", "Detalle", 300)], alto=16)
        self.t_aud.pack(fill="both", expand=True)

    @accion_segura
    def refrescar(self):
        self._destinos = self.s.catalogo.listar_destinos(self.u)
        self.t_dest.cargar([(d.id, d.nombre, d.pais, pesos(d.costo_base), "Activo" if d.activo else "Inactivo")
                            for d in self._destinos],
                           [() if d.activo else ("inactivo",) for d in self._destinos])
        activos = [d for d in self._destinos if d.activo]
        self._ids_activos = [d.id for d in activos]
        self.lista_paq_dest.delete(0, "end")
        for d in activos:
            self.lista_paq_dest.insert("end", f" {d.nombre} ({d.pais})")
        self._paquetes = self.s.catalogo.listar_paquetes(self.u)
        filas = []
        for p in self._paquetes:
            disp = self.s.catalogo.consultar_disponibilidad(self.u, p.id)
            filas.append((p.id, p.nombre, f"{p.fecha_inicio} a {p.fecha_fin}", pesos(p.calcular_costo()),
                          f"{disp.cupos_reservados} / {disp.cupos_totales}"))
        self.t_paq.cargar(filas)
        self.t_res.cargar([(r.id, r.cliente_id, r.paquete.nombre, r.cantidad_personas, pesos(r.monto_total),
                            r.estado.value.capitalize(), f"{r.fecha_reserva:%Y-%m-%d %H:%M}")
                           for r in self.s.reservas.todas(self.u)])
        if self.u.puede("ver_auditoria"):
            self.t_aud.cargar([(a["id"], a["fecha"], a["usuario_id"] or "—", a["accion"], a["detalle"] or "")
                               for a in self.s.auditoria.ultimos(100)])


def main() -> None:
    sistema = Sistema()
    if "--demo" in sys.argv:
        cargar_demo(sistema)
    App(sistema).mainloop()


if __name__ == "__main__":
    main()
