# Clima Async con Django

Pequeña aplicación Django que demuestra el uso de **vistas asíncronas** para
consumir una API externa de clima de forma concurrente, en el contexto del
tema "Scaling Distributed Python Applications".

## ¿Qué hace?

Al entrar a la página, la vista `weather.views.index` (una `async def`)
lanza **varias peticiones HTTP en paralelo** con `httpx.AsyncClient` y
`asyncio.gather`, en lugar de resolverlas una por una:

1. Para cada ciudad, primero geolocaliza el nombre usando el endpoint de
   *geocoding* de [Open-Meteo](https://open-meteo.com/) (API pública,
   gratuita y sin necesidad de API key).
2. Con la latitud/longitud obtenida, consulta el clima actual (temperatura,
   viento, condición del cielo).
3. Todas las ciudades configuradas se resuelven **al mismo tiempo**, no en
   secuencia, gracias a `asyncio.gather`.

Además, hay un formulario de búsqueda para agregar cualquier otra ciudad al
listado sin recargar la lógica de las ciudades por defecto.

![alt text](image.png)

### Features extra

- **Caché en memoria** (`WEATHER_CACHE_TTL_SECONDS`, 5 min por defecto) para
  no golpear la API en cada refresh de la misma ciudad.
- **Manejo de errores**: si una ciudad no existe o la API falla, se muestra
  una tarjeta de error en vez de romper toda la página.
- Interfaz simple y responsiva (CSS puro, sin frameworks de frontend).

## Estructura del proyecto

```
manage.py
requirements.txt
clima_project/        # configuración del proyecto Django (settings, urls, asgi/wsgi)
weather/               # app con la lógica de clima
    views.py           # vista async, dispara las peticiones concurrentes
    services.py         # funciones async que llaman a la API de Open-Meteo
    urls.py
    templates/weather/index.html
    static/weather/style.css
```

## Instalación y ejecución

```bash
cd "An Introduction to Scaling Distributed Python Applications"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

Abre [http://127.0.0.1:8000/](http://127.0.0.1:8000/) en tu navegador.

Para buscar una ciudad adicional, usa el parámetro `city` en la URL o el
formulario de búsqueda, por ejemplo:
`http://127.0.0.1:8000/?city=Tokyo`.

> Nota: aunque el servidor de desarrollo de Django (`runserver`, basado en
> WSGI) puede ejecutar vistas `async def`, para aprovechar por completo el
> modelo asíncrono en producción se recomienda servir el proyecto con un
> servidor ASGI como `uvicorn` o `daphne` (el proyecto ya incluye
> `clima_project/asgi.py`).

## Ejecutar como servicio al iniciar Linux (systemd)

Para que la aplicación arranque automáticamente cada vez que se inicia el
sistema, se puede registrar como un servicio de **systemd**.

> ⚠️ Esto usa `runserver`, que es solo para desarrollo. Es suficiente para
> pruebas y trabajos escolares, pero no para producción (ahí se usaría
> Gunicorn/Uvicorn detrás de Nginx).

### 1. Preparar el entorno

Asegúrate de que el `.venv` tenga **todas las dependencias instaladas**
(systemd usa directamente el Python del `.venv`, sin activarlo):

```bash
cd "An Introduction to Scaling Distributed Python Applications"
source .venv/bin/activate
pip install -r requirements.txt
```

Comprueba que funciona a mano antes de crear el servicio:

```bash
python manage.py runserver 0.0.0.0:8000
```

### 2. Crear el archivo del servicio

Desde la carpeta del proyecto (donde está `manage.py`), este comando genera
el servicio con tu usuario y tus rutas reales, sin tener que editar nada a
mano:

```bash
sudo tee /etc/systemd/system/django-app.service > /dev/null <<EOF
[Unit]
Description=Django app (Clima Async)
After=network.target

[Service]
User=$USER
WorkingDirectory="$(pwd)"
ExecStart="$(pwd)/.venv/bin/python" manage.py runserver 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF
```

Puntos importantes:

- Todas las rutas deben ser **absolutas**; systemd no activa el entorno
  virtual, por eso se llama directamente a `.venv/bin/python`.
- Si la ruta tiene **espacios**, va entre comillas (el comando anterior ya
  lo hace).
- Si tu `.venv` está en otra carpeta (por ejemplo, una carpeta padre),
  ajusta la ruta en `ExecStart`.

### 3. Activar el servicio

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now django-app
systemctl status django-app
```

- `enable` hace que arranque en cada inicio del sistema.
- `--now` lo inicia inmediatamente.

Si todo va bien, el estado será `active (running)` y la app estará en
[http://localhost:8000](http://localhost:8000). Para acceder desde otros
equipos de la red, agrega su IP (o `'*'` solo para pruebas) a
`ALLOWED_HOSTS` en `clima_project/settings.py`.

### 4. Administrar el servicio

```bash
journalctl -u django-app -n 40 --no-pager   # ver logs completos
journalctl -u django-app -f                 # logs en vivo
sudo systemctl restart django-app           # reiniciar tras cambios
sudo systemctl stop django-app              # detener
sudo systemctl disable django-app           # no arrancar al iniciar
```

### Solución de problemas

| Síntoma en los logs | Causa | Solución |
|---|---|---|
| `status=217/USER` | El `User=` no existe (se dejó un valor de ejemplo) | Usar un usuario real, p. ej. `$USER` |
| `Failed at step EXEC` / `No such file or directory` | Ruta incorrecta en `ExecStart` o `WorkingDirectory` | Verificar rutas con `pwd` y `which python` |
| `ModuleNotFoundError: No module named 'django'` | Las dependencias no están instaladas en ese `.venv` | `pip install -r requirements.txt` con el venv activado |
| `Address already in use` | Ya hay un `runserver` en el puerto 8000 | Cerrarlo o cambiar el puerto |
| `Start request repeated too quickly` | systemd alcanzó el límite de reintentos | Corregir el error y ejecutar `sudo systemctl reset-failed django-app` antes de `restart` |

## Ciudades por defecto

Configurables en `clima_project/settings.py` mediante `DEFAULT_CITIES`.

## API utilizada

- [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api)
- [Open-Meteo Forecast API](https://open-meteo.com/en/docs)

No requiere registro ni API key, ideal para fines educativos/demostrativos.
