"""Configuración persistente en %APPDATA%\\DeskControl\\config.json (dispositivos, caché, ventana, atajo)."""
import contextlib
import copy
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

CARPETA = Path(os.environ.get("APPDATA", str(Path.home()))) / "DeskControl"
RUTA_POR_DEFECTO = CARPETA / "config.json"
LARGO_MAX_NOMBRE = 40
CLAVES_CACHE = ("PowerOn", "Power", "Volume", "Brightness", "BackgroundColor",
                "CurrentSoundPackageNo", "TotalSoundPackage", "fontname")
_CAMPOS_DISPOSITIVO = ("id", "tipo", "nombre", "direccion")

POR_DEFECTO = {
    "version": 1,
    "atajo": "ctrl+shift+space",
    "autoarranque": True,
    "ventana": {"x": None, "y": None},
    "dispositivos": [],
}


def _limpiar_nombre(nombre) -> str:
    limpio = " ".join(str(nombre).split())[:LARGO_MAX_NOMBRE]
    if not limpio:
        raise ValueError("El nombre no puede estar vacío")
    return limpio


def _dispositivo_valido(d) -> bool:
    return isinstance(d, dict) and all(isinstance(d.get(k), str) and d.get(k) for k in _CAMPOS_DISPOSITIVO)


class Config:
    def __init__(self, ruta: Path, datos: dict):
        self.ruta = Path(ruta)
        self.datos = datos
        self._candado = threading.RLock()  # la usan el hilo de la ventana, el de la bandeja y el del Bluetooth

    @classmethod
    def cargar(cls, ruta: Path = RUTA_POR_DEFECTO) -> "Config":
        ruta = Path(ruta)
        datos = copy.deepcopy(POR_DEFECTO)
        if ruta.exists():
            try:
                leidos = json.loads(ruta.read_text(encoding="utf-8"))
                if not isinstance(leidos, dict) or not isinstance(leidos.get("dispositivos", []), list):
                    raise ValueError("formato inesperado")
                datos.update(leidos)
            except (ValueError, OSError) as error:
                respaldo = ruta.with_name(f"config.corrupto-{time.strftime('%Y%m%d-%H%M%S')}.json")
                log.warning("config.json inválido (%s); copia en %s", error, respaldo.name)
                with contextlib.suppress(OSError):
                    ruta.replace(respaldo)
                datos = copy.deepcopy(POR_DEFECTO)
        if not isinstance(datos.get("ventana"), dict):
            datos["ventana"] = {"x": None, "y": None}
        dispositivos = [d for d in datos["dispositivos"] if _dispositivo_valido(d)]
        for d in dispositivos:
            if not isinstance(d.get("ultimo_estado"), dict):
                d["ultimo_estado"] = {}
            if not isinstance(d.get("fuentes"), list):
                d["fuentes"] = []
        datos["dispositivos"] = dispositivos
        return cls(ruta, datos)

    def guardar(self) -> None:
        with self._candado:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal = self.ruta.with_suffix(".tmp")
            temporal.write_text(json.dumps(self.datos, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporal, self.ruta)

    @property
    def candado(self) -> threading.RLock:
        """Para leer varios datos de forma consistente mientras otro hilo los actualiza."""
        return self._candado

    @property
    def dispositivos(self) -> list[dict]:
        return self.datos["dispositivos"]

    def buscar(self, id_: str) -> dict | None:
        return next((d for d in self.dispositivos if d["id"] == id_), None)

    def agregar_dispositivo(self, tipo: str, nombre: str, direccion: str) -> dict:
        with self._candado:
            nombre = _limpiar_nombre(nombre)
            direccion = str(direccion).upper()
            if any(d["direccion"] == direccion for d in self.dispositivos):
                raise ValueError("Ese dispositivo ya está guardado")
            dispositivo = {"id": uuid.uuid4().hex[:8], "tipo": tipo, "nombre": nombre, "direccion": direccion,
                           "ultimo_estado": {}, "fuentes": []}
            self.dispositivos.append(dispositivo)
            return dispositivo

    def renombrar(self, id_: str, nombre: str) -> None:
        with self._candado:
            dispositivo = self.buscar(id_)
            if dispositivo is None:
                raise KeyError(id_)
            dispositivo["nombre"] = _limpiar_nombre(nombre)

    def quitar(self, id_: str) -> None:
        with self._candado:
            self.datos["dispositivos"] = [d for d in self.dispositivos if d["id"] != id_]

    def actualizar_cache(self, id_: str, estado: dict | None = None, fuentes: list[str] | None = None) -> None:
        with self._candado:
            dispositivo = self.buscar(id_)
            if dispositivo is None:
                return
            if estado:
                dispositivo["ultimo_estado"].update({k: v for k, v in estado.items() if k in CLAVES_CACHE})
            if fuentes is not None:
                dispositivo["fuentes"] = list(fuentes)
