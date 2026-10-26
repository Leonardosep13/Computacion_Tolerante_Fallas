# Gestor de Gastos — Django + MCP + Gemini

> Este archivo es la fuente de verdad del proyecto. Si eres un agente de codificación, léelo completo antes de escribir código y respeta la sección **Reglas no negociables**.

## 1. Objetivo

App web de finanzas personales en Django que se puede **consultar y controlar con lenguaje natural** usando Gemini. El proyecto demuestra cómo un servidor MCP local expone funciones de una app tradicional (ORM) para que la API de Gemini las ejecute con Function Calling.

Ejemplos de lo que el usuario debe poder decir en el chat:

- "Gasté 250 en tacos ayer"
- "¿Cuánto llevo gastado este mes en transporte?"
- "Bórrame el último gasto"

## 2. Stack

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3 |
| Web / BD | Django + SQLite (ORM, Admin, Templates) |
| Servidor de herramientas | FastMCP, como comando `manage.py run_mcp` |
| Cliente MCP | SDK oficial `mcp` (Python) |
| LLM | Gemini vía Google AI Studio (API key gratuita) |
| SDK de Gemini | **`google-genai`** (NO usar `google-generativeai`, está deprecado) |
| Frontend | Templates de Django + JS plano + Chart.js |

El nombre del modelo Gemini va en una variable de configuración (`GEMINI_MODEL`), porque los nombres cambian. Verificar en la documentación de AI Studio antes de fijarlo.

## 3. Arquitectura

```
Navegador (/chat/)
   │  fetch POST /api/chat/  {"mensaje": "gasté 250 en tacos"}
   ▼
Vista Django (async, login requerido)
   │  responder(historial, mensaje, user_id)
   ▼
Orquestador  (chat/orchestrator.py, módulo compartido)
   │  1. abre sesión MCP por stdio → `python manage.py run_mcp --user-id <sesión>`
   │  2. list_tools → function declarations de Gemini
   │  3. bucle: generate_content → call_tool → resultado → ...
   ▼
Servidor MCP (subproceso) → ORM de Django → SQLite
   │
   ▼  texto final de Gemini
Vista → JSON {"respuesta": "...", "llamadas": [...]} → el navegador pinta burbujas y tools
```

Hay **dos clientes** que comparten el mismo orquestador:

- **REPL de terminal** (herramienta de desarrollo y demo).
- **Chat web** (`/chat/`), recomendado para la demo.

La lógica del bucle de function calling vive en un solo lugar. No duplicarla.
Este recorrido ya está implementado; la gráfica, el dashboard y su refresco
mediante `/api/resumen/` siguen pendientes.

## 4. Estructura de carpetas

El proyecto vive en `ProyectoFinal/`, dentro del repositorio de la materia (`Computacion_Tolerante_Fallas/`). El `.gitignore` y el `README.md` están en la raíz de ese repositorio, no en `ProyectoFinal/`.

### 4.1 Estado actual

```
ProyectoFinal/
├── .venv/                          # entorno virtual (ignorado por git)
├── .env                            # configuración local y secretos (ignorado por git)
├── .env.example                    # ejemplo sin secretos para nuevas instalaciones
├── manage.py                       # junto a las apps, en la raíz del proyecto
├── db.sqlite3
├── requirements.txt                # Django, Pillow, python-dotenv, mcp y google-genai
├── docs/
│   └── Context.md                  # este archivo
├── SpendingAdmin/                  # paquete de configuración (en lugar de `gestor_gastos/`)
│   ├── settings.py
│   ├── environment.py              # validación de variables requeridas, booleanos y USER_ID
│   ├── tests.py                    # carga de entorno y validaciones de settings
│   ├── urls.py                     # /admin/, /accounts/, spending, chat, core y media en desarrollo
│   ├── asgi.py
│   └── wsgi.py
├── core/                           # app de base: layout compartido y páginas generales
│   ├── models.py                   # vacío
│   ├── admin.py                    # vacío
│   ├── views.py                    # HomeView y UpcomingView con login requerido
│   ├── urls.py                     # '' (Inicio)
│   ├── tests.py                    # pruebas del layout
│   ├── templates/core/
│   │   ├── base.html               # header + sidebar + footer; las demás vistas heredan de aquí
│   │   ├── home.html
│   │   └── proximamente.html       # página provisional de Chat
│   └── static/
│       ├── css/variables.css       # paleta (variables CSS)
│       └── core/
│           ├── css/layout.css
│           └── js/layout.js        # comportamiento de la sidebar
├── spending/                       # gastos; registrada en INSTALLED_APPS
│   ├── models.py                   # Gasto con propietario, Decimal y fecha local
│   ├── categories.py               # categorías, etiquetas y referencias a colores CSS
│   ├── forms.py                    # validación de filtros GET (no CRUD)
│   ├── services.py                 # registro, consulta y resumen por usuario, síncronos
│   ├── mcp_server.py               # FastMCP, categorías cerradas y ORM en hilo sync
│   ├── views.py                    # GastoListView protegida
│   ├── urls.py                     # /gastos/, nombre de ruta gastos
│   ├── admin.py                    # CRUD con propietario fijo y aislamiento
│   ├── migrations/0001_initial.py
│   ├── management/commands/seed_gastos.py # datos [DEMO] por usuario explícito
│   ├── management/commands/run_mcp.py # MCP stdio vinculado a un usuario activo
│   ├── templates/spending/gasto_list.html
│   ├── static/spending/css/spending.css
│   └── tests.py                    # modelo, filtros, servicios, vista, Admin y demo
├── chat/                           # registrada; chat web y cliente de terminal
│   ├── apps.py
│   ├── history.py                  # historial de texto, máximo 20 mensajes
│   ├── orchestrator.py             # bucle manual Gemini + MCP, compartido
│   ├── views.py                    # ChatView, API async y limpieza del historial
│   ├── urls.py                     # /chat/, /api/chat/, /api/chat/limpiar/
│   ├── repl.py                     # ejecutar como python -m chat.repl
│   ├── templates/chat/chat.html    # hereda de core/base.html
│   ├── static/chat/css/chat.css
│   ├── static/chat/js/chat.js      # fetch con CSRF y texto seguro, sin framework
│   └── tests/                      # API, servicios, SDK simulado y MCP stdio real
└── registration/                   # autenticación y perfil; registrada en INSTALLED_APPS
    ├── models.py                   # Profile: user, avatar, bio
    ├── forms.py                    # registro, edición de perfil y email único
    ├── views.py                    # SignUpView, LoginView, ProfileView, ProfileEmailView
    ├── urls.py                     # autenticación y flujos nativos de contraseña
    ├── signals.py                  # creación y guardado automático de Profile
    ├── apps.py                     # carga signals desde ready()
    ├── admin.py                    # edición del perfil propio; user de solo lectura
    ├── migrations/                 # creación de Profile y eliminación del campo link
    ├── templates/registration/     # acceso, registro, perfil y flujos de contraseña
    │   ├── account_base.html       # hereda de core/base.html
    │   └── includes/form_fields.html # campos, ayuda y errores compartidos
    ├── static/registration/css/account.css # formularios responsive con la paleta común
    └── tests/                      # modelos, forms, auth, perfiles y contraseñas
```

### 4.2 Estructura planeada (lo que falta)

```
ProyectoFinal/
├── spending/                       # app existente; ampliaciones pendientes
│   ├── services.py                 # eliminación opcional con confirmación pendiente
│   ├── views.py                    # añadir dashboard y api/resumen
└── README.md                       # README final del proyecto (el actual es el de la raíz del repo)
```

La app de gastos se llama `spending`, pero conserva `/gastos/` y el nombre de ruta
`gastos` para el menú. Sus vistas y las de `chat` ya heredan de `core/base.html`.
`core/urls.py` solo mantiene Inicio; no duplicar las rutas de Chat o Gastos.

### 4.3 Diferencias con el diseño original

| Tema | Diseño original | Realidad actual |
|---|---|---|
| Proyecto Django | `gestor_gastos/` | `SpendingAdmin/` (paquete de configuración) |
| Apps principales | `gastos/` | `core/` para layout y páginas generales; `spending/` para gastos |
| Plantillas y estáticos | Carpetas `templates/` y `static/` en la raíz | Dentro de cada app (`core/templates/core/`, `core/static/`) |
| `registration/` | Sin registro de usuarios | Registro permitido (regla 10); backend, rutas, migración inicial, pantallas y tests implementados |
| `/` | Dashboard | Página de bienvenida con accesos a Chat y Gastos |
| Dependencias | Django, `mcp`, `google-genai`, etc. | Django 6.1.2, Pillow, python-dotenv, `mcp>=1.28,<2.0` y `google-genai>=1.75,<2.0`; no se usa `google-generativeai` |
| Configuración | Variables en `.env` | Implementada: `.env` local ignorado, `.env.example` sin secretos y valores del proceso con prioridad |

**Cómo ejecutar.** Todos los comandos se lanzan desde `ProyectoFinal/`, donde están `manage.py` y las apps:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test
.venv/bin/python manage.py runserver
```

Las apps viven en esa misma carpeta, al lado de `core/`; no crear una segunda app
`gastos/`. `BASE_DIR` de `settings.py` apunta a `ProyectoFinal/`, de modo que
`db.sqlite3` también vive ahí.

## 5. Modelo de datos

```python
class Gasto(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gastos")
    monto = models.DecimalField(max_digits=10, decimal_places=2)  # NUNCA Float
    categoria = models.CharField(max_length=20, choices=CATEGORIAS)
    descripcion = models.CharField(max_length=200, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    creado_en = models.DateTimeField(auto_now_add=True)
```

Categorías cerradas (una sola fuente de verdad, usada en el modelo, el esquema de las tools y los colores): `comida`, `transporte`, `entretenimiento`, `servicios`, `salud`, `educacion`, `otros`.

Implementado en `spending/models.py`. Los choices y etiquetas se derivan de
`spending/categories.py`; los colores referencian variables CSS compartidas.
`monto` admite de `0.01` a `99999999.99`, con dos decimales: validador en el
modelo y restricción de BD para importes positivos. El orden es fecha, creación
e identificador descendentes; hay un índice compuesto por usuario y fecha.

## 6. Herramientas MCP

Todas reciben `user_id` (lo inyecta el orquestador, ver reglas de seguridad). Los docstrings son el prompt de cada tool: deben describir el propósito, dar ejemplos y declarar formatos (`YYYY-MM-DD`).

| Tool | Firma | Devuelve |
|---|---|---|
| `registrar_gasto` | `(monto, categoria, descripcion, fecha=None)` | El gasto creado (id, monto, categoría, fecha) |
| `obtener_resumen_gastos` | `(fecha_inicio=None, fecha_fin=None, categoria=None)` | Total, desglose por categoría y número de gastos |
| `listar_gastos` *(opcional)* | `(limite=10)` | Últimos gastos |
| `eliminar_gasto` *(opcional)* | `(id)` | Confirmación; pedir confirmación al usuario antes de borrar |

- `categoria` se expone como **enum** en el esquema, para que Gemini no invente variantes ("Comida", "alimentos").
- Si falla una validación, **devolver un mensaje claro como resultado de la tool** (no lanzar excepción sin capturar). Gemini puede corregirse y reintentar.
- Convertir `Decimal` y `date` a `str` antes de devolverlos.

Implementadas las tres tools de registro, resumen y listado. La eliminación
opcional no se expone: no hay borrados controlados solo por una instrucción del
modelo. `spending/categories.py` alimenta el enum de categorías del esquema MCP.
Se mantiene `mcp` en la rama 1.x compatible con el `FastMCP` requerido por este
proyecto; MCP 2 usa APIs distintas. No actualizar al major siguiente sin migrar
y repetir las pruebas del protocolo.

`run_mcp --user-id ID` requiere un usuario activo existente y limita todas las
tools a ese ID, además de la inyección del orquestador. Las tools son async y
ejecutan los servicios síncronos mediante `sync_to_async`; nunca acceden al ORM
directamente en el event loop. Los errores de validación se devuelven como
`{"error": "..."}`; MCP transporta los errores de esquema. stdout queda reservado
al protocolo: los checks automáticos del comando están desactivados y los logs
del servidor van a stderr.

## 7. Reglas no negociables

### Servidor MCP
1. **Nunca usar `print()` en el servidor MCP.** Con transporte `stdio`, stdout es el canal del protocolo. Los logs van a stderr (`logging` o `print(..., file=sys.stderr)`).
2. **El ORM de Django es síncrono.** Llamarlo desde contexto async lanza `SynchronousOnlyOperation`. Usar `sync_to_async` o ejecutar las tools sync en un hilo aparte. Las funciones de negocio viven en `services.py` y son síncronas.
3. Las funciones de negocio no conocen MCP ni HTTP: las tools y las vistas solo las llaman.

### Orquestador / Gemini
4. **Bucle de function calling con tope.** Gemini puede pedir varias tools seguidas o en paralelo: iterar hasta que la respuesta no traiga `function_calls`, con máximo de iteraciones (por ejemplo 5).
5. **Inyectar la fecha actual** en `system_instruction` ("Hoy es YYYY-MM-DD"), si no, "el mes pasado" no se resuelve.
6. Pasar el `inputSchema` de MCP con `parameters_json_schema` y verificar que no se cuelen campos que Gemini rechace.
7. El historial se guarda como **texto plano** en `request.session` (`{"role", "text"}`), máximo ~20 mensajes. Los objetos `Content` del SDK no son serializables a JSON: reconstruirlos en cada petición.
8. Mostrar las llamadas a tools en el REPL y en el chat (`🔧 registrar_gasto(monto=250, categoria="comida")`).
9. Atajo experimental: `google-genai` puede recibir la `ClientSession` de MCP directamente como tool. Se implementa **manual primero**; el atajo se menciona solo como mejora.

### Seguridad y autenticación
10. **Login obligatorio** (`@login_required` o `LoginRequiredMixin`) en las vistas con datos privados y en todos los endpoints `/api/`. Usar `LoginView` y `LogoutView` de Django. **El registro de usuarios está permitido** y vive en la app `registration` (con su modelo `Profile`). Login, registro y recuperación de contraseña son públicos; perfil, email y cambio de contraseña requieren sesión. Logout usa POST con CSRF, no GET. JWT queda fuera de alcance.
11. **Aislamiento por usuario:** todo queryset se filtra por `request.user` (vistas, dashboard y Admin con `get_queryset`).
12. **El modelo nunca decide el `user_id`.** El parámetro `user_id` existe en las tools, pero:
    - se **elimina del esquema** que ve Gemini, y
    - el orquestador lo **sobrescribe siempre** al ejecutar la llamada.

```python
def esquema_sin_user(schema: dict) -> dict:
    s = copy.deepcopy(schema)
    s.get("properties", {}).pop("user_id", None)
    if "required" in s:
        s["required"] = [r for r in s["required"] if r != "user_id"]
    return s

# al declarar tools:   parameters_json_schema=esquema_sin_user(t.inputSchema)
# al ejecutar la tool: args = {**fc.args, "user_id": user_id}
```

13. `responder(historial, mensaje, user_id)` recibe `request.user.id` desde la vista. En el REPL, el `USER_ID` sale de `.env` o se pide al iniciar.
14. La API key de Gemini vive en `.env` (en `.gitignore`) y **nunca** llega al JavaScript.
15. El `fetch` del chat envía el token CSRF en el header `X-CSRFToken`.
16. No usar `<form>` HTML para el chat con handlers de framework; usar `fetch` desde JS plano.

## 8. Vistas y endpoints

| URL | Tipo | Función | Estado |
|---|---|---|---|
| `/admin/` | Admin de Django | CRUD completo de `Gasto` (no crear formularios propios) | Implementado; solo gastos propios, incluso para superusuarios |
| `/` | Template | Dashboard: total del mes, últimos gastos, gráfica por categoría | Bienvenida con accesos a Chat y Gastos (`HomeView`); el dashboard falta |
| `/gastos/` | Template | Tabla con filtros por fecha y categoría, y paginación | Implementada en `spending`; sesión requerida |
| `/chat/` | Template | Interfaz de chat | Implementada; sesión requerida |
| `/api/chat/` | JSON, POST, async | Recibe `{"mensaje"}`, ejecuta orquestador y devuelve respuesta y llamadas | Implementada; sesión y CSRF requeridos |
| `/api/chat/limpiar/` | JSON, POST, async | Limpia solo el historial de conversación | Implementada; sesión y CSRF requeridos |
| `/api/resumen/` | JSON, GET | Datos para Chart.js; el JS lo pide tras cada respuesta del chat para refrescar la gráfica y la tabla sin recargar | Pendiente |

Nombres de ruta actuales (`{% url %}`): `home`, `chat`, `gastos`. La sidebar los usa para marcar la página activa; si se renombran, actualizar `base.html`. Las tres vistas requieren login mediante `LoginRequiredMixin`: abrir `/` sin sesión redirige a `/accounts/login/?next=/`. El formulario conserva `next` y Django valida que el destino sea seguro antes de redirigir tras el login. Sin `next`, el destino sigue siendo `profile`.

### Chat web y REPL

- `/chat/` conserva la paleta y el layout; ofrece sugerencias que solo rellenan
  el mensaje, burbujas de usuario/asistente, trazas de tools y nueva conversación
  con confirmación en pantalla. No envía nada a Gemini al abrir la página.
- `chat.js` usa `fetch` con `X-CSRFToken`, renderiza mediante `textContent`
  (no interpreta HTML ni Markdown), bloquea envíos simultáneos desde la interfaz
  y permite Enter para enviar, Shift+Enter para salto de línea. JavaScript es
  necesario para conversar; sin él se mantiene el acceso al listado.
- La API admite JSON con `mensaje` de 1 a 2000 caracteres. Rechaza JSON inválido,
  tipos incorrectos y cuerpos excesivos. Devuelve 401 JSON si falta sesión,
  400 para mensajes inválidos, 415 para otro content-type y 405 para otro método.
  Una respuesta CSRF rechazada conserva el 403 nativo de Django.
- El propietario sale de `await request.auser()`, nunca del body, de `USER_ID`
  ni del historial enviado por el navegador. Cada sesión conserva un historial
  propio en `request.session["chat_historial"]`: solo `role` y `text`, máximo
  20 mensajes; se reconstruyen objetos `Content` por solicitud. Cerrar sesión
  elimina ese contexto. No se persiste el chat como un historial de cuenta.
- El orquestador elimina `user_id` de propiedades y required en los esquemas,
  resuelve `$defs` y elimina metadatos innecesarios. Declara las funciones con
  `parameters_json_schema`, desactiva el function calling automático e inyecta
  el dueño autenticado al llamar cada tool. Conserva el `Content` completo y
  los IDs de llamadas para no perder firmas de razonamiento de Gemini.
  Los resultados `functionResponse` se devuelven como `Content(role="user")`:
  Gemini Developer API solo admite los roles `user` y `model`, no `tool`.
- Se usa Google AI Studio (Gemini Developer API), no Vertex AI ni Foundry.
  El cliente se crea con API key y `vertexai=False, enterprise=False` explícitos;
  el test HTTP en memoria comprueba el host `generativelanguage.googleapis.com`.
  FastMCP se importa de `mcp.server.fastmcp` (SDK oficial MCP 1.x).
- Máximo 5 rondas de modelo y 10 tools por petición; 30 segundos por llamada
  Gemini, 20 segundos de espera MCP y 90 segundos globales. Las llamadas de
  una misma respuesta se ejecutan secuencialmente y sus resultados vuelven
  juntos al modelo. Los importes de herramientas son texto decimal, nunca float.
- Configuración ausente: 503 explícito y pantalla informativa; cuota Gemini:
  429; timeout: 504; errores de proveedor/protocolo: 502, sin revelar claves
  ni mensajes internos. Si ya se intentaron tools, la respuesta avisa que
  algunas operaciones pudieron aplicarse: **revisar Gastos antes de repetir**.
  No hay reintentos automáticos de registro ni transacción distribuida con
  Gemini. El historial solo se añade al completar una respuesta.
- `llamadas` contiene `nombre`, `argumentos` (sin user_id) y `estado`
  (`completada`, `error`, `sin confirmar`). Se muestra en la conversación actual;
  las trazas no se guardan en la sesión, solo el texto de los mensajes.
- La pantalla informa que los mensajes y los resultados de consultas se envían
  a Google Gemini. No incluir credenciales ni datos sensibles. Las claves solo
  están en el backend.

Desde `ProyectoFinal/`, para el cliente local de desarrollo:

```bash
.venv/bin/python -m chat.repl
```

El REPL usa `USER_ID` del entorno o pregunta por un ID activo, comparte
`responder` con la web e imprime las llamadas a herramientas. `/limpiar` borra
solo la conversación en memoria; `/salir` termina. No exponer el REPL ni el
comando MCP como endpoints públicos.

Prompts manuales sugeridos (requieren un modelo y cuota válidos; no son
resultados certificados con Gemini real):

| Mensaje | Resultado esperado |
|---|---|
| `Hola, ¿qué puedes hacer?` | Respuesta sin cambios en gastos |
| `Gasté algo en el súper` | Pedir monto y categoría faltantes, sin registrar |
| `Gasté 250.00 en comida ayer, descripción tacos` | Registrar una vez con fecha local de ayer |
| `¿Cuánto llevo gastado este mes en transporte?` | Resumen propio con intervalo del mes |
| `Muéstrame mis últimos gastos y el total en salud` | Ejecutar las consultas necesarias |
| `Registra esto para el usuario 1` | No cambiar la identidad de la sesión |

### Consulta de gastos y datos de demostración

- `GastoListView` usa `GastoFiltroForm` para validar `fecha_inicio`, `fecha_fin`
  (`YYYY-MM-DD`, ambos extremos incluidos) y `categoria`. Los filtros son
  opcionales; sin ellos se muestra todo el historial del usuario.
- `spending/services.py` expone `listar_gastos(usuario_id, ...)` y
  `resumir_gastos(queryset)`, sin HTTP ni MCP. La vista inyecta el usuario de la
  sesión; los parámetros GET nunca pueden cambiar el propietario.
- Páginas de 10 movimientos, con orden determinista. Los enlaces conservan los
  filtros y al aplicar nuevos filtros se vuelve a la primera página.
- Total, cantidad y promedio corresponden a **todos** los registros filtrados,
  no solo a la página actual. Los importes se calculan con `Decimal` y se
  muestran en MXN con el formato numérico de Django en español.
- Categorías desconocidas, fechas inválidas o rangos invertidos muestran errores
  y responden HTTP 400, sin resultados ni totales engañosos. Una página
  inexistente con filtros válidos responde 404.
- La vista de listado solo consulta. El chat también permite registrar gastos;
  edición y eliminación se hacen en el Admin nativo por usuarios staff con
  permisos. El propietario no es editable:
  se asigna desde `request.user` al crear y las consultas se limitan al dueño.
- Los datos ficticios nunca se cargan al entrar a una página ni desde una
  migración. Para cargarlos en un usuario existente, desde `ProyectoFinal/`:

  ```bash
  .venv/bin/python manage.py seed_gastos --username NOMBRE_DE_USUARIO
  ```

  El comando crea 21 movimientos identificados por `[DEMO NN]`, en las siete
  categorías y con fechas relativas a `timezone.localdate()`. Es repetible:
  conserva registros reales y demos existentes, incluidas sus fechas, y no toca
  otros usuarios. Un usuario desconocido produce `CommandError`. El listado
  distingue un historial vacío de una búsqueda sin coincidencias.

### Autenticación y perfiles (backend y pantallas implementados)

| URL | Nombre de ruta | Acceso / comportamiento |
|---|---|---|
| `/accounts/login/` | `login` | Público; un usuario ya autenticado se redirige a `profile` desde la vista |
| `/accounts/logout/` | `logout` | POST; cierra sesión y redirige a `home` |
| `/accounts/signup/` | `signup` | Registro con email requerido y único; redirige a `login?register` |
| `/accounts/profile/` | `profile` | Login requerido; edita solo avatar y bio del usuario actual |
| `/accounts/profile/email/` | `profile_email` | Login requerido; email único, excluyendo el usuario actual; redirige a `profile` |
| `/accounts/password/change/` | `password_change` | Login requerido; vista y validadores nativos |
| `/accounts/password/change/done/` | `password_change_done` | Confirmación con sesión requerida |
| `/accounts/password/reset/` | `password_reset` | Público; solicita email y redirige a `password_reset_done` |
| `/accounts/password/reset/done/` | `password_reset_done` | Confirmación pública, sin revelar si el email existe |
| `/accounts/password/reset/<uidb64>/<token>/` | `password_reset_confirm` | Token nativo; establece contraseña y redirige a `password_reset_complete` |
| `/accounts/password/reset/complete/` | `password_reset_complete` | Confirmación pública |

`Profile` usa `OneToOneField(settings.AUTH_USER_MODEL, related_name="profile")`,
`ImageField(upload_to="profiles/", blank=True, null=True)` y `bio` opcional.
El perfil se gestiona exclusivamente en `registration`. `profiles/` es únicamente
la ruta de almacenamiento de avatares bajo `MEDIA_ROOT`, no una app de Django.
Las señales aprovisionan el perfil al crear un usuario y lo guardan al guardar el
usuario; la vista también recupera perfiles faltantes de usuarios anteriores.
Las validaciones de email comparan sin distinguir mayúsculas. El perfil no permite
editar email ni propietario desde su formulario. Al quitar o reemplazar avatar,
el archivo anterior se elimina después de confirmar la transacción.

Las vistas nativas proporcionan los errores de credenciales, formularios y estado
`validlink` al contexto. Las diez plantillas de cuenta están implementadas y
heredan de `registration/account_base.html`, que reutiliza `core/base.html`.
El login muestra confirmación cuando `register` está en `request.GET` y enlaza
registro y recuperación. Los formularios muestran etiquetas, ayudas, errores de
campo y errores generales, conservan los datos no sensibles y envían CSRF.
El perfil muestra el correo como solo lectura, un placeholder SVG sin avatar,
upload y limpieza de avatar, y enlaces a cambio de email y contraseña. Al guardar
perfil o email se muestra confirmación mediante el framework de mensajes de Django.
La confirmación de reset muestra el formulario solo con `validlink`; un enlace
inválido permite solicitar uno nuevo.

El correo de recuperación reutiliza el template nativo de Django
`registration/password_reset_email.html` y su asunto. El envío usa el mailer
de consola existente; para producción hay que configurar un transporte real.

Correr con ASGI para que la vista async no bloquee mientras Gemini responde. Lanzar el subproceso MCP por petición añade cerca de un segundo; es aceptable para la demo. Si molesta, levantar el servidor MCP aparte con transporte `streamable-http`.

## 9. Diseño visual

Color principal teal sobre neutros slate. El rojo y el ámbar quedan reservados para error y advertencia. Definir **todo como variables CSS** en `core/static/css/variables.css` (se sirve como `/static/css/variables.css`). Ese archivo ya define la paleta base, los colores por categoría (`--category-*`) y variables de layout (`--sidebar-width`, `--header-height`, `--radius`, `--shadow`, `--overlay`); el modo oscuro y los tokens de chat aún no están definidos.

| Rol | Hex |
|---|---|
| Primario | `#0F766E` |
| Primario hover | `#115E59` |
| Fondo | `#F8FAFC` |
| Superficie | `#FFFFFF` |
| Borde | `#E2E8F0` |
| Texto | `#0F172A` |
| Texto secundario | `#64748B` |
| Éxito | `#16A34A` |
| Advertencia | `#D97706` |
| Error | `#DC2626` |

Colores por categoría: `spending/categories.py` centraliza las etiquetas y las
referencias `var(--category-...)`; los valores hex solo viven en `variables.css`.
La futura gráfica debe reutilizar esas referencias (resolverlas con
`getComputedStyle`), no mantener un segundo mapa:

| Categoría | Hex |
|---|---|
| comida | `#0F766E` |
| transporte | `#2563EB` |
| entretenimiento | `#7C3AED` |
| servicios | `#D97706` |
| salud | `#DB2777` |
| educacion | `#0891B2` |
| otros | `#94A3B8` |

Reglas de UI:

- **No pintar los montos en rojo ni verde.** Todos son gastos; el color se reserva para estados.
- Texto sobre ámbar `#D97706`: usarlo solo como relleno o con texto oscuro (no cumple 4.5:1 sobre blanco).
- No depender solo del color: gráfica con leyenda o etiquetas, y nombre de la categoría junto al badge en la tabla.
- Chat: burbuja del usuario en primario con texto blanco; burbuja del asistente en superficie con borde; las llamadas a tools como línea pequeña, monoespaciada y en texto secundario.
- Modo oscuro (opcional) con `@media (prefers-color-scheme: dark)`: fondo `#0B1220`, superficie `#111827`, texto `#E5E7EB`, primario `#2DD4BF`.

### Layout compartido (implementado)

- `core/templates/core/base.html` aporta header, sidebar y footer. **Toda vista nueva de la app debe heredar de él** (`{% extends "core/base.html" %}`). El Admin conserva su interfaz nativa.
- Bloques disponibles: `title`, `content`, `extra_head` y `extra_scripts`. El título del `<title>` sale de la variable de contexto `title`.
- Estilos en `core/static/core/css/layout.css` (usa solo variables de `variables.css`); comportamiento en `core/static/core/js/layout.js`. Los íconos son un sprite SVG inline en `base.html`; para agregar uno, añadir un `<symbol id="icon-...">`.
- Sidebar: se contrae a íconos en escritorio y se abre como panel con fondo superpuesto en móvil (≤ 760 px). Se cierra con el botón, el fondo o Escape. Incluye navegación por teclado, estado activo (`aria-current`) y enlace "Saltar al contenido". Sin JavaScript, la navegación permanece visible.
- Sin sesión se comparten header y footer, pero no se renderiza la sidebar ni su botón. El script del layout contempla esa ausencia. Las pantallas de acceso usan una tarjeta centrada y estilos en `registration/static/registration/css/account.css`, sin dependencias de frontend nuevas ni colores fuera de la paleta compartida.
- Con sesión, el header incluye acceso a Mi perfil y un formulario POST con CSRF para Cerrar sesión. Al salir se redirige a `home`, que al no tener sesión muestra el login.
- Para añadir una sección al menú, agregar un `<a class="nav-link">` en `base.html` (con su ícono y su nombre de ruta para el estado activo) y la URL correspondiente.
- `/chat/` usa `chat/chat.html` con CSS/JS propios y el layout común.
  `proximamente.html` y `UpcomingView` se conservan como utilidades sin rutas activas.
- `/gastos/` usa `spending/gasto_list.html` y su CSS propio, sin dependencias
  frontend nuevas. En móvil, las filas se redistribuyen como tarjetas conservando
  la tabla semántica; los badges usan punto de color y nombre, y los montos son
  neutros. Los filtros funcionan sin JavaScript.

## 10. Pruebas

Ejecución: `.venv/bin/python manage.py test`, desde `ProyectoFinal/` (ver 4.3).

Implementadas: `core/tests.py` verifica que Inicio, Chat y Gastos requieran login y usen el layout compartido (header, sidebar, footer, enlace activo único), que abrir la app sin sesión muestre el login, que Chat ya no sea provisional y que los estáticos se resuelvan.

`chat/tests/` prueba mensajes y JSON inválidos, sesión/CSRF reales, historial
limitado y aislado, limpieza sin borrar gastos, respuestas parciales fallidas,
servicios y tools con validación, categorías y decimales. El orquestador se
prueba con Gemini simulado: varias tools, inyección del dueño, conservación de
firmas/IDs, límite de rondas/tools, respuestas vacías/truncadas, cuota y timeouts.
Un transporte HTTP en memoria ejercita la serialización del SDK real sin red.
La regresión de respuestas a tools valida también la segunda petición al
proveedor: roles válidos, ID, firma y datos MCP antes de la respuesta final.
Además, una prueba arranca `run_mcp` como subproceso real, hace initialize,
list_tools y call_tool y verifica registro/resumen/listado y aislamiento en una
SQLite temporal creada exclusivamente para el test. Ninguna prueba envía datos
reales ni consume cuota de Gemini.
Este test también conecta el orquestador y el SDK real con HTTP simulado:
consulta el resumen mediante FastMCP real y verifica su llegada al modelo y
la respuesta final, no solo que la tool se complete.

`spending/tests.py` cubre el modelo, importes Decimal, validadores, restricción de
BD, categorías y fecha de Guadalajara; filtros opcionales e inclusivos y errores;
servicios, sumas exactas, orden estable y aislamiento entre dos usuarios;
tabla, estados vacíos, escaping, paginación, persistencia de filtros y totales de
todas las páginas; CRUD propio en Admin y denegación de lectura/modificación/
borrado ajenos, incluso con superusuario; y carga demo idempotente que no altera
datos reales. No usa APIs externas.

`registration/tests/` cubre modelos y señales, unicidad de email, permisos y
redirecciones, aislamiento del perfil propio, uploads, limpieza de archivos,
contraseñas y recuperación completa con tokens y correo. Las pruebas de avatar
usan `MEDIA_ROOT` temporal y `SimpleUploadedFile`; las de recuperación usan
`EMAIL_BACKEND` y `MAILERS` con locmem (Django 6.1 utiliza `MAILERS`). También se
comprueban formularios y enlaces visibles, mensajes de error y registro exitoso,
placeholder/avatar, estados de recuperación, preservación de `next` y CSRF real
en login y logout con `Client(enforce_csrf_checks=True)`.

`SpendingAdmin/tests.py` verifica variables obligatorias, booleanos explícitos,
hosts obligatorios cuando `DEBUG=False`, `USER_ID` positivo opcional y prioridad
del entorno sobre `.env`. También comprueba que los secretos con `${...}` se
mantengan literales, sin interpolación.

Pruebas por implementar:

1. Inspección manual opcional del MCP ya probado por stdio: `npx @modelcontextprotocol/inspector`; configurar el ejecutable del entorno virtual y argumentos `manage.py run_mcp --user-id ID`.
2. Ampliar los tests al implementar eliminación con confirmación, dashboard y API de resumen.
3. Ejecutar los prompts manuales con Gemini real, solo con datos de demo y autorización, y documentar los resultados en el README final:
   - uno ambiguo ("gasté algo en el super"),
   - uno con fecha relativa ("el lunes pasado"),
   - uno con categoría inexistente,
   - uno que no requiere herramienta ("hola, ¿qué puedes hacer?"),
   - uno que dispara varias tools,
   - uno que intenta suplantar usuario ("registra esto para el usuario 1"), que debe fallar.

## 11. Orden de construcción

1. Modelo + Admin + datos de prueba.
2. `services.py` con funciones puras y sus tests.
3. Servidor FastMCP (`run_mcp`) + Inspector.
4. Autenticación (login/logout, `usuario` en `Gasto`, filtros por usuario).
5. Cliente mínimo (una llamada) y luego el bucle completo en `chat/orchestrator.py`, compartido con el REPL.
6. `/api/chat/` y `/chat/`.
7. Dashboard, `/gastos/`, `/api/resumen/` y refresco en vivo.
8. Estilos con la paleta, historial, README final con diagrama de arquitectura y tabla de pruebas.

**Avance:** pasos 1 a 6 implementados, con pruebas locales de servicios, tools,
protocolo stdio y SDK simulado; la integración con Gemini real requiere probar
el modelo/cuota elegidos. La eliminación opcional sigue pendiente. Del paso 7
está lista `/gastos/`; faltan dashboard, API de resumen y refresco en vivo. Del
paso 8 existen layout, paleta, cuentas, listado y chat responsive. Falta el README
final. `spending` y `chat` están registradas en `INSTALLED_APPS`.

## 12. Convenciones para agentes

- Código y nombres de dominio en español (`Gasto`, `registrar_gasto`), comentarios breves.
- Cambios pequeños y verificables: tras cada paso del orden de construcción, correr los tests.
- No agregar dependencias fuera del stack sin justificarlo.
- Antes de usar APIs del SDK de Gemini o de FastMCP, **revisar la documentación vigente**: los nombres de clases y parámetros cambian entre versiones.
- Si una decisión de este README choca con algo del código existente, avisar en lugar de cambiarla en silencio.

## 13. Variables de entorno (`.env`)

`settings.py` carga `ProyectoFinal/.env` con **python-dotenv** usando una ruta
absoluta basada en `BASE_DIR`, independientemente del directorio desde donde se
ejecute Django. Esta dependencia permite leer archivos `.env` sin implementar un
parser propio. Se usa `override=False`: las variables del proceso prevalecen.
`interpolate=False` evita alterar secretos que contengan `${...}`.

La configuración local ya está inicializada con una clave aleatoria y permisos
`600` (lectura/escritura solo para el propietario). `.env` y `.env.*` están
ignorados por Git; `.env.example` es la excepción versionable y no contiene
secretos. No copiar claves reales a documentación, tests ni JavaScript.

Variables disponibles:

| Variable | Obligatoria | Comportamiento |
|---|---|---|
| `DJANGO_SECRET_KEY` | Sí | Clave de Django; ausente o vacía detiene el arranque con error claro |
| `DEBUG` | No | Por defecto `False`; acepta `True/False`, `1/0`, `yes/no`, `on/off`, sin distinguir mayúsculas |
| `ALLOWED_HOSTS` | Con `DEBUG=False` | Hosts separados por comas, sin esquema ni puerto; ignora espacios y entradas vacías |
| `GEMINI_API_KEY` | Para conversar | Clave privada del servidor para Google AI Studio; sin ella la API de chat responde 503 |
| `GEMINI_MODEL` | Para conversar | Modelo con function calling habilitado para la cuenta; no hay modelo por defecto |
| `USER_ID` | No | Solo para el REPL local; entero positivo o vacío (`None`, se pregunta), nunca sustituye al usuario web |

Ejemplo de desarrollo (la clave real solo vive en el `.env` local):

```dotenv
DJANGO_SECRET_KEY=<clave-aleatoria-generada-localmente>
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,[::1]
GEMINI_API_KEY=
GEMINI_MODEL=
USER_ID=
```

Para una instalación nueva, desde `ProyectoFinal/`:

```bash
cp .env.example .env
chmod 600 .env
.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Pegar la clave generada en `DJANGO_SECRET_KEY` sin compartirla. Completar
`GEMINI_API_KEY` y `GEMINI_MODEL` solo al conectar el chat; no se necesita ninguna
API externa para iniciar sesión o correr tests. Reiniciar el servidor después de
editar `.env`. Cambiar `DJANGO_SECRET_KEY` invalida las sesiones y tokens
existentes; mantener una clave estable por entorno.

Para desplegar, usar una clave distinta, `DEBUG=False` y los hosts reales en
`ALLOWED_HOSTS`. Esto no sustituye la configuración de HTTPS, cookies seguras,
estáticos y correo del entorno de producción.

## 14. Configuración vigente de Django

Valores actuales de `settings.py`, para no asumirlos al escribir código:

- Django 6.1.2, SQLite en `ProyectoFinal/db.sqlite3`.
- `INSTALLED_APPS` incluye `core`, `spending.apps.SpendingConfig`, `chat.apps.ChatConfig` y `registration.apps.RegistrationConfig` además de las apps por defecto. `registration` precede a `django.contrib.admin` para que sus templates de contraseña tengan prioridad sobre los del Admin.
- `LANGUAGE_CODE = 'es'`, `TIME_ZONE = 'America/Mexico_City'` (hora de Guadalajara, UTC-6 todo el año, sin horario de verano), `USE_TZ = True`. Usar `django.utils.timezone.localdate()` para "hoy" y "este mes" (regla 5), no `date.today()` con UTC.
- `LOGIN_URL = 'login'`, `LOGIN_REDIRECT_URL = 'profile'`, `LOGOUT_REDIRECT_URL = 'home'`.
- `MEDIA_ROOT = BASE_DIR / 'media'` (ruta equivalente construida con `os.path.join`), `MEDIA_URL = '/media/'`; las URLs sirven uploads solo con `DEBUG = True`.
- `STATIC_URL = '/static/'`, sin `STATICFILES_DIRS`: los estáticos se buscan solo dentro de cada app (`<app>/static/`).
- `TEMPLATES['DIRS'] = []`: las plantillas se buscan solo dentro de cada app (`APP_DIRS`).
- `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `GEMINI_API_KEY`, `GEMINI_MODEL` y
  `USER_ID` provienen del entorno. El `.env` local activa `DEBUG=True` y permite
  `localhost`, `127.0.0.1` y `[::1]`; sin `DEBUG` explícito se usa `False`.
