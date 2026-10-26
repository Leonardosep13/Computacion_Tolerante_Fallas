import os

from django.core.exceptions import ImproperlyConfigured


def required_env(name):
    value = os.environ.get(name, "")
    if not value.strip():
        raise ImproperlyConfigured(
            f"Define {name} en ProyectoFinal/.env o en el entorno del proceso."
        )
    return value


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ImproperlyConfigured(
        f"{name} debe ser un booleano: True/False, 1/0, yes/no u on/off."
    )


def optional_positive_int(name):
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        number = int(value)
    except ValueError:
        raise ImproperlyConfigured(
            f"{name} debe ser un entero positivo o quedar vacío."
        ) from None
    if number <= 0:
        raise ImproperlyConfigured(
            f"{name} debe ser un entero positivo o quedar vacío."
        )
    return number
