"""Protocolo BLE de las placas Xeno3 (ver PROTOCOLO.md).

Los mensajes son JSON en UTF-8 con la forma [tipo, {clave: valor}]:
2 = comando (app -> sable), 3 = respuesta/estado (sable -> app), 4 = error (sable -> app).
"""
import json
import re

SERVICIOS_XENO = frozenset({
    "0000dae0-0000-1000-8000-00805f9b34fb",
    "00003ab0-0000-1000-8000-00805f9b34fb",
})
CAR_HANDSHAKE = "0000dae1-0000-1000-8000-00805f9b34fb"
CAR_DATOS = "00003ab1-0000-1000-8000-00805f9b34fb"

MENSAJE_HANDSHAKE = b'[2,{"HandShake":"HelloDamien"}]'
MENSAJE_AUTORIZAR = b'[2,{"Authorize":"SaberOfDamien"}]'

TIPO_COMANDO = 2
TIPO_RESPUESTA = 3
TIPO_ERROR = 4

_MAX_BUFFER = 4096
_RUTA_FUENTE = re.compile(r"^/\d{1,3}$")


class ComandoInvalido(ValueError):
    """El comando no está permitido o su valor no es válido."""


def _entero(valor, minimo: int, maximo: int) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and minimo <= valor <= maximo


# Lista blanca: cualquier clave que no esté acá no se puede enviar (Reset, firmware, rm, etc.).
_VALIDADORES = {
    "PowerOn": lambda v: isinstance(v, bool),
    "Volume": lambda v: _entero(v, 0, 100),
    "Brightness": lambda v: _entero(v, 0, 100),
    "BackgroundColor": lambda v: isinstance(v, list) and len(v) == 3 and all(_entero(c, 0, 255) for c in v),
    "CurrentSoundPackageNo": lambda v: _entero(v, 0, 999),
    "ls": lambda v: v == "/",
    "fontname": lambda v: isinstance(v, str) and bool(_RUTA_FUENTE.match(v)),
}
CLAVES_PERMITIDAS = frozenset(_VALIDADORES)


def validar(clave: str, valor) -> None:
    """Lanza ComandoInvalido si la clave no está permitida o el valor no es válido."""
    if clave not in _VALIDADORES:
        raise ComandoInvalido(f"Comando no permitido: {clave}")
    if not _VALIDADORES[clave](valor):
        raise ComandoInvalido(f"Valor inválido para {clave}: {valor!r}")


def armar(clave: str, valor) -> bytes:
    """Arma el comando [2,{clave:valor}] listo para escribir en la característica de datos."""
    validar(clave, valor)
    return json.dumps([TIPO_COMANDO, {clave: valor}], separators=(",", ":")).encode("utf-8")


class Ensamblador:
    """Junta notificaciones BLE hasta formar un mensaje JSON completo [tipo, {...}]."""

    def __init__(self):
        self._buffer = b""

    def agregar(self, datos: bytes) -> list[tuple[int, dict]]:
        self._buffer += bytes(datos)
        try:
            mensaje = json.loads(self._buffer.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            if len(self._buffer) > _MAX_BUFFER:
                self._buffer = b""
            return []
        self._buffer = b""
        if (isinstance(mensaje, list) and len(mensaje) == 2
                and isinstance(mensaje[0], int) and isinstance(mensaje[1], dict)):
            return [(mensaje[0], mensaje[1])]
        return []
