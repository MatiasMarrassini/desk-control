"""Protocolo local de los focos WiZ: JSON por UDP al puerto 38899 (ver NOTAS.md y la spec de la etapa 2).

Lista blanca: solo se leen estados (getPilot, getSystemConfig) y se envían órdenes de luz (setPilot).
"""
import json

PUERTO = 38899
_LECTURAS = frozenset({"getPilot", "getSystemConfig"})

# Nombres oficiales de la app WiZ en español; IDs según la documentación de la comunidad (pywizlight).
ESCENAS_FIJAS = {
    6: "Acogedor", 11: "Blanco cálido", 12: "Luz de día", 13: "Blanco frío", 14: "Luz nocturna",
    15: "Concentración", 16: "Relax", 17: "Colores reales", 18: "Hora de la tele", 19: "Crecimiento de planta",
}
ESCENAS_ANIMADAS = {
    1: "Océano", 2: "Romance", 3: "Atardecer", 4: "Fiesta", 5: "Chimenea", 7: "Bosque", 8: "Colores pastel",
    9: "Despertar", 10: "Hora de acostarse", 20: "Primavera", 21: "Verano", 22: "Otoño", 23: "Inmersión profunda",
    24: "Jungla", 25: "Mojito", 26: "Club", 27: "Navidad", 28: "Halloween", 29: "Luz de vela", 30: "Blanco dorado",
    31: "Pulso", 32: "Steampunk", 33: "Diwali",
}
ESCENAS = {**ESCENAS_FIJAS, **ESCENAS_ANIMADAS}
FAVORITAS_POR_DEFECTO = [12, 15, 16, 14, 4, 5, 1]
MAX_FAVORITAS = 7

_PARAMS = frozenset({"state", "dimming", "r", "g", "b", "temp", "sceneId", "speed"})
_RGB = ("r", "g", "b")


class ComandoInvalido(ValueError):
    """El método o los parámetros no están permitidos."""


def _entero(valor, minimo: int, maximo: int) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and minimo <= valor <= maximo


def validar_params(params: dict) -> None:
    if not isinstance(params, dict) or not params:
        raise ComandoInvalido("Parámetros vacíos o inválidos")
    extra = set(params) - _PARAMS
    if extra:
        raise ComandoInvalido(f"Parámetro no permitido: {sorted(extra)[0]}")
    if "state" in params and not isinstance(params["state"], bool):
        raise ComandoInvalido("state debe ser true o false")
    if "dimming" in params and not _entero(params["dimming"], 10, 100):
        raise ComandoInvalido("El brillo va de 10 a 100")
    if "temp" in params and not _entero(params["temp"], 2200, 6500):
        raise ComandoInvalido("La temperatura va de 2200 a 6500 K")
    if "sceneId" in params and params["sceneId"] not in ESCENAS:
        raise ComandoInvalido("Escena desconocida")
    hay_rgb = [k in params for k in _RGB]
    if any(hay_rgb) and not all(hay_rgb):
        raise ComandoInvalido("El color necesita r, g y b")
    if all(hay_rgb) and not all(_entero(params[k], 0, 255) for k in _RGB):
        raise ComandoInvalido("Cada componente de color va de 0 a 255")
    if sum([all(hay_rgb), "temp" in params, "sceneId" in params]) > 1:
        raise ComandoInvalido("Color, temperatura y escena no se combinan")
    if "speed" in params and (params.get("sceneId") not in ESCENAS_ANIMADAS or not _entero(params["speed"], 10, 200)):
        raise ComandoInvalido("La velocidad (10–200) solo vale con una escena animada")


def armar_set(params: dict) -> bytes:
    validar_params(params)
    return json.dumps({"method": "setPilot", "params": params}, separators=(",", ":")).encode("utf-8")


def armar_lectura(metodo: str) -> bytes:
    if metodo not in _LECTURAS:
        raise ComandoInvalido(f"Método no permitido: {metodo}")
    return json.dumps({"method": metodo, "params": {}}, separators=(",", ":")).encode("utf-8")


def interpretar(datos: bytes) -> dict | None:
    """Respuesta JSON de un foco ({"method": ..., ...}) o None si no es válida."""
    try:
        mensaje = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if isinstance(mensaje, dict) and isinstance(mensaje.get("method"), str):
        return mensaje
    return None


def lista_escenas() -> list[dict]:
    fijas = [{"id": i, "nombre": n, "animada": False} for i, n in ESCENAS_FIJAS.items()]
    animadas = [{"id": i, "nombre": n, "animada": True} for i, n in ESCENAS_ANIMADAS.items()]
    return fijas + animadas
