"""Ayudas de Win32 para la ventana: monitor vertical, esquinas redondeadas y primer plano."""
import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_dwmapi = ctypes.WinDLL("dwmapi")
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowW.restype = wintypes.HWND
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)


def elegir_posicion(areas: list[tuple[int, int, int, int]], margen: int = 12) -> tuple[int, int]:
    """Esquina superior izquierda del primer monitor vertical (o del primero si no hay vertical)."""
    verticales = [a for a in areas if (a[3] - a[1]) > (a[2] - a[0])]
    candidatas = verticales or areas
    if not candidatas:
        return margen, margen
    izquierda, arriba, _, _ = candidatas[0]
    return izquierda + margen, arriba + margen


def listar_areas_de_trabajo() -> list[tuple[int, int, int, int]]:
    areas = []

    def visitar(hmonitor, _hdc, _rect, _param):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if _user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            r = info.rcWork
            areas.append((r.left, r.top, r.right, r.bottom))
        return True

    _user32.EnumDisplayMonitors(None, None, _ENUM_PROC(visitar), 0)
    return areas


def posicion_por_defecto() -> tuple[int, int]:
    return elegir_posicion(listar_areas_de_trabajo())


def buscar_ventana(titulo: str) -> int:
    return _user32.FindWindowW(None, titulo) or 0


def redondear_esquinas(hwnd: int) -> None:
    valor = ctypes.c_int(DWMWCP_ROUND)
    _dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE,
                                  ctypes.byref(valor), ctypes.sizeof(valor))


def traer_al_frente(hwnd: int) -> None:
    _user32.SetForegroundWindow(hwnd)


def es_primer_plano(hwnd: int) -> bool:
    return (_user32.GetForegroundWindow() or 0) == hwnd
