"""Agenda de contactos con interfaz Tkinter y persistencia en SQLite."""

import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

DB_PATH = Path(__file__).resolve().parent.parent / "contactos.db"


class ContactosDB:
    """Encapsula el acceso a la base de datos SQLite de contactos."""

    def __init__(self, db_path: Path):
        self._connection = sqlite3.connect(db_path)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._crear_tabla()

    def _crear_tabla(self):
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS contactos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                telefono TEXT,
                email TEXT
            )
            """
        )
        self._connection.commit()

    def listar(self, filtro: str = ""):
        cursor = self._connection.execute(
            "SELECT id, nombre, telefono, email FROM contactos "
            "WHERE nombre LIKE ? ORDER BY nombre COLLATE NOCASE",
            (f"%{filtro}%",),
        )
        return cursor.fetchall()

    def agregar(self, nombre: str, telefono: str, email: str):
        cursor = self._connection.execute(
            "INSERT INTO contactos (nombre, telefono, email) VALUES (?, ?, ?)",
            (nombre, telefono, email),
        )
        self._connection.commit()
        return cursor.lastrowid

    def actualizar(self, contacto_id: int, nombre: str, telefono: str, email: str):
        self._connection.execute(
            "UPDATE contactos SET nombre = ?, telefono = ?, email = ? WHERE id = ?",
            (nombre, telefono, email, contacto_id),
        )
        self._connection.commit()

    def eliminar(self, contacto_id: int):
        self._connection.execute("DELETE FROM contactos WHERE id = ?", (contacto_id,))
        self._connection.commit()

    def cerrar(self):
        self._connection.close()


class AgendaApp(tk.Tk):
    """Ventana principal de la agenda de contactos."""

    def __init__(self, db: ContactosDB):
        super().__init__()
        self.db = db
        self.contacto_seleccionado_id = None

        self.title("Agenda de Contactos")
        self.geometry("640x420")
        self.minsize(560, 380)

        self._construir_formulario()
        self._construir_busqueda()
        self._construir_tabla()
        self._construir_botones()

        self._refrescar_tabla()

    def _construir_formulario(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x")

        ttk.Label(frame, text="Nombre:").grid(row=0, column=0, sticky="w")
        self.nombre_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.nombre_var, width=30).grid(row=0, column=1, padx=5, pady=2)

        ttk.Label(frame, text="Teléfono:").grid(row=1, column=0, sticky="w")
        self.telefono_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.telefono_var, width=30).grid(row=1, column=1, padx=5, pady=2)

        ttk.Label(frame, text="Email:").grid(row=2, column=0, sticky="w")
        self.email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.email_var, width=30).grid(row=2, column=1, padx=5, pady=2)

    def _construir_busqueda(self):
        frame = ttk.Frame(self, padding=(10, 0))
        frame.pack(fill="x")

        ttk.Label(frame, text="Buscar:").pack(side="left")
        self.busqueda_var = tk.StringVar()
        self.busqueda_var.trace_add("write", lambda *_: self._refrescar_tabla())
        ttk.Entry(frame, textvariable=self.busqueda_var, width=30).pack(side="left", padx=5)

    def _construir_tabla(self):
        columnas = ("id", "nombre", "telefono", "email")
        self.tabla = ttk.Treeview(self, columns=columnas, show="headings", selectmode="browse")
        for col, texto, ancho in (
            ("id", "ID", 40),
            ("nombre", "Nombre", 180),
            ("telefono", "Teléfono", 140),
            ("email", "Email", 200),
        ):
            self.tabla.heading(col, text=texto)
            self.tabla.column(col, width=ancho, anchor="w")
        self.tabla.column("id", anchor="center")

        self.tabla.pack(fill="both", expand=True, padx=10, pady=5)
        self.tabla.bind("<<TreeviewSelect>>", self._al_seleccionar_fila)

    def _construir_botones(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x")

        ttk.Button(frame, text="Agregar", command=self._agregar_contacto).pack(side="left", padx=5)
        ttk.Button(frame, text="Actualizar", command=self._actualizar_contacto).pack(side="left", padx=5)
        ttk.Button(frame, text="Eliminar", command=self._eliminar_contacto).pack(side="left", padx=5)
        ttk.Button(frame, text="Limpiar", command=self._limpiar_formulario).pack(side="left", padx=5)

    def _refrescar_tabla(self):
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)
        for contacto in self.db.listar(self.busqueda_var.get()):
            self.tabla.insert("", "end", values=contacto)

    def _al_seleccionar_fila(self, _event):
        seleccion = self.tabla.selection()
        if not seleccion:
            return
        contacto_id, nombre, telefono, email = self.tabla.item(seleccion[0], "values")
        self.contacto_seleccionado_id = int(contacto_id)
        self.nombre_var.set(nombre)
        self.telefono_var.set(telefono)
        self.email_var.set(email)

    def _leer_formulario(self):
        nombre = self.nombre_var.get().strip()
        telefono = self.telefono_var.get().strip()
        email = self.email_var.get().strip()
        return nombre, telefono, email

    def _agregar_contacto(self):
        nombre, telefono, email = self._leer_formulario()
        if not nombre:
            messagebox.showwarning("Dato requerido", "El nombre es obligatorio.")
            return
        self.db.agregar(nombre, telefono, email)
        self._limpiar_formulario()
        self._refrescar_tabla()

    def _actualizar_contacto(self):
        if self.contacto_seleccionado_id is None:
            messagebox.showwarning("Sin selección", "Selecciona un contacto de la tabla para actualizar.")
            return
        nombre, telefono, email = self._leer_formulario()
        if not nombre:
            messagebox.showwarning("Dato requerido", "El nombre es obligatorio.")
            return
        self.db.actualizar(self.contacto_seleccionado_id, nombre, telefono, email)
        self._limpiar_formulario()
        self._refrescar_tabla()

    def _eliminar_contacto(self):
        if self.contacto_seleccionado_id is None:
            messagebox.showwarning("Sin selección", "Selecciona un contacto de la tabla para eliminar.")
            return
        if messagebox.askyesno("Confirmar", "¿Eliminar el contacto seleccionado?"):
            self.db.eliminar(self.contacto_seleccionado_id)
            self._limpiar_formulario()
            self._refrescar_tabla()

    def _limpiar_formulario(self):
        self.contacto_seleccionado_id = None
        self.nombre_var.set("")
        self.telefono_var.set("")
        self.email_var.set("")
        for fila in self.tabla.selection():
            self.tabla.selection_remove(fila)


def main():
    db = ContactosDB(DB_PATH)
    app = AgendaApp(db)
    try:
        app.mainloop()
    finally:
        db.cerrar()


if __name__ == "__main__":
    main()
