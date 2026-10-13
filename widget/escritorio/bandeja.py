"""Icono de la bandeja del sistema con su menú."""
from typing import Callable

import pystray
from PIL import Image, ImageDraw


def crear_icono(tamano: int = 64) -> Image.Image:
    """Un sable en diagonal: hoja verde y mango gris."""
    img = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = tamano / 64
    d.line([(20 * s, 44 * s), (54 * s, 10 * s)], fill=(60, 255, 140, 255), width=max(2, int(6 * s)))
    d.line([(8 * s, 56 * s), (22 * s, 42 * s)], fill=(175, 175, 185, 255), width=max(3, int(9 * s)))
    return img


def crear_bandeja(*, al_alternar: Callable[[], None], al_agregar: Callable[[], None],
                  autoarranque_activo: Callable[[], bool], al_cambiar_autoarranque: Callable[[], None],
                  al_salir: Callable[[], None]) -> pystray.Icon:
    menu = pystray.Menu(
        pystray.MenuItem("Mostrar / ocultar", lambda: al_alternar(), default=True),
        pystray.MenuItem("Agregar dispositivo", lambda: al_agregar()),
        pystray.MenuItem("Iniciar con Windows", lambda: al_cambiar_autoarranque(),
                         checked=lambda _item: autoarranque_activo()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Salir", lambda: al_salir()),
    )
    return pystray.Icon("DeskControl", crear_icono(), "Desk Control", menu)
