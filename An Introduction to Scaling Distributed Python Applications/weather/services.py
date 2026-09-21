"""
Funciones asíncronas para consultar la API pública Open-Meteo.

No requiere API key. Se usa httpx.AsyncClient para poder resolver
varias ciudades de forma concurrente con asyncio.gather.
"""
import time

import httpx
from django.conf import settings

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# https://open-meteo.com/en/docs#weathervariables (weather_code)
WEATHER_CODES = {
    0: "Cielo despejado",
    1: "Mayormente despejado",
    2: "Parcialmente nublado",
    3: "Nublado",
    45: "Niebla",
    48: "Niebla con escarcha",
    51: "Llovizna ligera",
    53: "Llovizna moderada",
    55: "Llovizna densa",
    61: "Lluvia ligera",
    63: "Lluvia moderada",
    65: "Lluvia intensa",
    71: "Nieve ligera",
    73: "Nieve moderada",
    75: "Nieve intensa",
    80: "Chubascos ligeros",
    81: "Chubascos moderados",
    82: "Chubascos violentos",
    95: "Tormenta eléctrica",
    96: "Tormenta con granizo ligero",
    99: "Tormenta con granizo intenso",
}

# Caché simple en memoria del proceso: evita golpear la API en cada refresh.
_cache: dict[str, dict] = {}


def _from_cache(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["fetched_at"]) < settings.WEATHER_CACHE_TTL_SECONDS:
        return entry["data"]
    return None


async def fetch_city_weather(client: httpx.AsyncClient, city_name: str) -> dict:
    """Geolocaliza una ciudad y obtiene su clima actual, de forma asíncrona."""
    cache_key = city_name.strip().lower()
    cached = _from_cache(cache_key)
    if cached is not None:
        return cached

    try:
        geo_resp = await client.get(
            GEOCODE_URL, params={"name": city_name, "count": 1, "language": "es"}
        )
        geo_resp.raise_for_status()
        geo_results = geo_resp.json().get("results")
        if not geo_results:
            return {"city": city_name, "error": "Ciudad no encontrada"}

        place = geo_results[0]
        lat, lon = place["latitude"], place["longitude"]

        weather_resp = await client.get(
            WEATHER_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
                "timezone": "auto",
            },
        )
        weather_resp.raise_for_status()
        current = weather_resp.json().get("current_weather", {})

        data = {
            "city": place.get("name", city_name),
            "country": place.get("country", ""),
            "temperature": current.get("temperature"),
            "windspeed": current.get("windspeed"),
            "description": WEATHER_CODES.get(current.get("weathercode"), "Desconocido"),
            "time": current.get("time"),
            "error": None,
        }
        _cache[cache_key] = {"data": data, "fetched_at": time.time()}
        return data
    except httpx.HTTPError:
        return {"city": city_name, "error": "Error al consultar el servicio de clima"}
