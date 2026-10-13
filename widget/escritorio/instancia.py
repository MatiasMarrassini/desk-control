"""Instancia única con un mutex con nombre: si ya hay un Desk Control abierto, el segundo se cierra."""
import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def adquirir_instancia_unica(nombre: str):
    """Devuelve el handle del mutex (mantenerlo vivo) o None si otra instancia ya lo tiene."""
    handle = _kernel32.CreateMutexW(None, False, nombre)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return None
    return handle


def liberar(handle) -> None:
    _kernel32.CloseHandle(handle)
