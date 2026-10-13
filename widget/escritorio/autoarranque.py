"""Arranque con Windows: valor en HKCU\\...\\Run (no requiere permisos de administrador)."""
import sys
import winreg
from pathlib import Path

CLAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE = "DeskControl"
LANZADOR = Path(__file__).resolve().parents[2] / "desk_control.pyw"


def comando() -> str:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{LANZADOR}" --oculto'


def esta_activo(clave: str = CLAVE_RUN, nombre: str = NOMBRE) -> bool:
    """True solo si el valor existe y apunta a esta copia del proyecto (si se movió la carpeta, es False)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
            valor, _ = winreg.QueryValueEx(k, nombre)
    except FileNotFoundError:
        return False
    return valor == comando()


def activar(clave: str = CLAVE_RUN, nombre: str = NOMBRE) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, clave) as k:
        winreg.SetValueEx(k, nombre, 0, winreg.REG_SZ, comando())


def desactivar(clave: str = CLAVE_RUN, nombre: str = NOMBRE) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, nombre)
    except FileNotFoundError:
        pass
