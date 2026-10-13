"""Atajo de teclado global con RegisterHotKey: Windows avisa solo esa combinación (no espía el teclado)."""
import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable

log = logging.getLogger(__name__)

MODIFICADORES = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
TECLAS = {"space": 0x20, "espacio": 0x20, "enter": 0x0D, "tab": 0x09,
          **{f"f{n}": 0x6F + n for n in range(1, 13)}}
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
_ID_ATAJO = 1


class AtajoInvalido(ValueError):
    """El texto del atajo no se entiende (ej.: 'ctrl+shift+space')."""


def interpretar(texto: str) -> tuple[int, int]:
    partes = [p.strip().lower() for p in str(texto).split("+")]
    if len(partes) < 2 or any(not p for p in partes):
        raise AtajoInvalido(f"Atajo inválido: {texto!r}")
    *mods, tecla = partes
    if any(m not in MODIFICADORES for m in mods) or len(set(mods)) != len(mods):
        raise AtajoInvalido(f"Modificadores inválidos en {texto!r}")
    if tecla in TECLAS:
        vk = TECLAS[tecla]
    elif len(tecla) == 1 and tecla.isascii() and tecla.isalnum():
        vk = ord(tecla.upper())
    else:
        raise AtajoInvalido(f"Tecla inválida en {texto!r}")
    banderas = MOD_NOREPEAT
    for m in mods:
        banderas |= MODIFICADORES[m]
    return banderas, vk


class AtajoGlobal:
    def __init__(self, texto: str, al_pulsar: Callable[[], None]):
        self.modificadores, self.tecla = interpretar(texto)
        self.registrado = False
        self._al_pulsar = al_pulsar
        self._listo = threading.Event()
        self._id_hilo: int | None = None
        self._hilo = threading.Thread(target=self._correr, name="atajo", daemon=True)

    def iniciar(self) -> bool:
        self._hilo.start()
        self._listo.wait(2)
        return self.registrado

    def _correr(self) -> None:
        user32 = ctypes.windll.user32
        self._id_hilo = ctypes.windll.kernel32.GetCurrentThreadId()
        self.registrado = bool(user32.RegisterHotKey(None, _ID_ATAJO, self.modificadores, self.tecla))
        self._listo.set()
        if not self.registrado:
            return
        mensaje = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(mensaje), None, 0, 0) > 0:
            if mensaje.message == WM_HOTKEY:
                try:
                    self._al_pulsar()
                except Exception:
                    log.exception("Error al manejar el atajo")
        user32.UnregisterHotKey(None, _ID_ATAJO)

    def detener(self) -> None:
        if self._id_hilo is not None and self._hilo.is_alive():
            ctypes.windll.user32.PostThreadMessageW(self._id_hilo, WM_QUIT, 0, 0)
            self._hilo.join(2)
