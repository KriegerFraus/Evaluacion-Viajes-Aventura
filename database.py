"""Conexión y esquema de la base de datos SQLite."""
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import config
ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT    NOT NULL,
    email             TEXT    NOT NULL UNIQUE,
    password_hash     TEXT    NOT NULL,
    rol               TEXT    NOT NULL CHECK (rol IN ('cliente','admin')),
    rut_cifrado       TEXT,
    telefono_cifrado  TEXT,
    intentos_fallidos INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta   TEXT,
    creado_en         TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS destinos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT    NOT NULL,
    pais        TEXT    NOT NULL,
    descripcion TEXT    NOT NULL,
    costo_base  REAL    NOT NULL CHECK (costo_base > 0),
    activo      INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0,1)),
    UNIQUE (nombre, pais)
);
CREATE TABLE IF NOT EXISTS paquetes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT    NOT NULL UNIQUE,
    fecha_inicio  TEXT    NOT NULL,
    fecha_fin     TEXT    NOT NULL,
    cupos_totales INTEGER NOT NULL CHECK (cupos_totales > 0),
    CHECK (fecha_fin >= fecha_inicio)
);
CREATE TABLE IF NOT EXISTS paquete_destino (
    paquete_id INTEGER NOT NULL REFERENCES paquetes(id) ON DELETE CASCADE,
    destino_id INTEGER NOT NULL REFERENCES destinos(id) ON DELETE RESTRICT,
    orden      INTEGER NOT NULL,
    PRIMARY KEY (paquete_id, destino_id)
);
CREATE TABLE IF NOT EXISTS reservas (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id        INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    paquete_id        INTEGER NOT NULL REFERENCES paquetes(id) ON DELETE RESTRICT,
    cantidad_personas INTEGER NOT NULL CHECK (cantidad_personas BETWEEN 1 AND 20),
    monto_total       REAL    NOT NULL CHECK (monto_total > 0),
    estado            TEXT    NOT NULL CHECK (estado IN ('confirmada','cancelada')),
    fecha_reserva     TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS auditoria (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER,
    accion     TEXT NOT NULL,
    detalle    TEXT,
    fecha      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_reservas_cliente ON reservas(cliente_id);
CREATE INDEX IF NOT EXISTS idx_reservas_paquete ON reservas(paquete_id);
"""


class ConexionBD:
    def __init__(self, ruta: Path | str | None = None):
        self.ruta = str(ruta or config.DB_PATH)
        nueva = self.ruta != ":memory:" and not Path(self.ruta).exists()
        self._conn = sqlite3.connect(self.ruta, isolation_level=None,
                                     detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(ESQUEMA)
        if nueva:
            try:
                os.chmod(self.ruta, 0o600)  # solo el dueño lee la base de datos
            except OSError:
                pass

    def ejecutar(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        return self._conn.execute(sql, params)

    def uno(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        return self._conn.execute(sql, params).fetchone()

    def todos(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchall()

    @contextmanager
    def transaccion(self):
        """BEGIN IMMEDIATE bloquea otras escrituras mientras dura (evita sobreventa)."""
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise

    def cerrar(self) -> None:
        self._conn.close()
