"""
Vista asíncrona: dispara varias peticiones a la API de clima en paralelo
usando asyncio.gather + httpx.AsyncClient, en lugar de resolverlas una
por una de forma secuencial.
"""
import asyncio

import httpx
from django.conf import settings
from django.shortcuts import render

from .services import fetch_city_weather


async def index(request):
    extra_city = request.GET.get("city", "").strip()
    cities = list(settings.DEFAULT_CITIES)
    if extra_city and extra_city.lower() not in (c.lower() for c in cities):
        cities.append(extra_city)

    async with httpx.AsyncClient(timeout=10) as client:
        results = await asyncio.gather(
            *(fetch_city_weather(client, city) for city in cities)
        )

    context = {"results": results, "searched_city": extra_city}
    return render(request, "weather/index.html", context)
