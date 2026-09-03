# Agenda de Contactos (Tkinter + SQLite)

Aplicación de escritorio para gestionar una agenda de contactos, construida con la interfaz gráfica **Tkinter** y persistencia de datos mediante **SQLite**.

## Contenido

- `src/main.py`: contiene toda la aplicación:
  - `ContactosDB`: clase que encapsula la conexión y las operaciones CRUD sobre la base de datos SQLite (`contactos.db`).
  - `AgendaApp`: ventana principal de Tkinter con formulario, buscador y tabla de contactos.
- `contactos.db`: archivo de base de datos generado automáticamente en la primera ejecución (no se versiona vacío, se crea al correr el programa).

## Funcionalidades

- Agregar un contacto (nombre, teléfono, email).
- Actualizar un contacto existente seleccionándolo en la tabla.
- Eliminar un contacto seleccionado (con confirmación).
- Buscar contactos por nombre en tiempo real.
- Los datos persisten entre ejecuciones gracias a SQLite: al cerrar y volver a abrir la aplicación, la agenda conserva su estado.

## Requisitos

- Python 3.10 o superior.
- `tkinter` y `sqlite3`, ambos incluidos en la biblioteca estándar de Python (en algunas distribuciones de Linux es necesario instalar el paquete del sistema `python3-tk`).

No se requieren dependencias externas ni `requirements.txt`.

## Ejecución

Desde este directorio:

```bash
python src/main.py
```

Al ejecutarse por primera vez se crea el archivo `contactos.db` en este directorio, donde se guardan todos los contactos de forma persistente.

## Uso

1. Completa los campos **Nombre**, **Teléfono** y **Email** en el formulario superior.
2. Presiona **Agregar** para guardar un nuevo contacto.
3. Selecciona una fila en la tabla para cargar sus datos en el formulario, edítalos y presiona **Actualizar** para guardar los cambios, o **Eliminar** para borrarlo.
4. Usa el campo **Buscar** para filtrar contactos por nombre mientras escribes.
5. Presiona **Limpiar** para vaciar el formulario y deseleccionar la fila actual.
