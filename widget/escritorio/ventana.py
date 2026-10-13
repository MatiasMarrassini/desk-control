"""Ayudas de Win32 para la ventana: monitor vertical, esquinas redondeadas, primer plano y memoria de WebView2."""
import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger(__name__)
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


def posicion_inicial(x, y, areas: list[tuple[int, int, int, int]], margen: int = 12) -> tuple[int, int]:
    """La posición guardada si la barra superior del widget cae en alguna pantalla; si no, la de por defecto.

    Así, si se desconecta o reacomoda el monitor vertical, el widget no queda abierto fuera de la vista.
    """
    if isinstance(x, int) and isinstance(y, int):
        px, py = x + 40, y + 20  # un punto de la barra superior, desde donde se lo puede arrastrar
        if any(a[0] <= px < a[2] and a[1] <= py < a[3] for a in areas):
            return x, y
    return elegir_posicion(areas, margen)


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


def fijar_memoria_baja(ventana, baja: bool) -> None:
    """Pide a WebView2 que recorte memoria (oculta) o vuelva a lo normal (visible).

    El control .NET solo se toca en el hilo de la interfaz: se encola con BeginInvoke y no se espera,
    así ocultar nunca queda bloqueado por esto. Sin WebView2 listo (o con otro motor), no hace nada.
    """
    formulario = getattr(ventana, "native", None)
    control = getattr(formulario, "webview", None)
    if control is None:
        return
    from Microsoft.Web.WebView2.Core import CoreWebView2MemoryUsageTargetLevel as Nivel
    from System import Action

    def fijar() -> None:
        try:
            nucleo = control.CoreWebView2
            if nucleo is not None:
                nucleo.MemoryUsageTargetLevel = Nivel.Low if baja else Nivel.Normal
        except Exception:
            log.exception("No se pudo cambiar el nivel de memoria de WebView2")

    formulario.BeginInvoke(Action(fijar))
