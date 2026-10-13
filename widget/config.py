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

from widget.dispositivos.wiz_protocolo import ESCENAS, FAVORITAS_POR_DEFECTO, MAX_FAVORITAS  # noqa: E402

CLAVES_CACHE_WIZ = ("state", "dimming", "temp", "r", "g", "b", "sceneId")

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


def _foco_valido(f) -> bool:
    return isinstance(f, dict) and all(isinstance(f.get(k), str) and f.get(k) for k in ("mac", "ip"))


def _dispositivo_valido(d) -> bool:
    if not (isinstance(d, dict) and all(isinstance(d.get(k), str) and d.get(k) for k in _CAMPOS_DISPOSITIVO)):
        return False
    if d["tipo"] == "wiz_grupo":
        focos = d.get("focos")
        return isinstance(focos, list) and any(_foco_valido(f) for f in focos)
    return True


def _favoritas_validas(ids) -> list[int]:
    if not isinstance(ids, list):
        return list(FAVORITAS_POR_DEFECTO)
    vistas, salida = set(), []
    for i in ids:
        if isinstance(i, int) and not isinstance(i, bool) and i in ESCENAS and i not in vistas:
            vistas.add(i)
            salida.append(i)
    return salida[:MAX_FAVORITAS]


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
            if d["tipo"] == "wiz_grupo":
                d["focos"] = [{"mac": f["mac"], "ip": f["ip"], "nombre": str(f.get("nombre") or "Foco")}
                              for f in d["focos"] if _foco_valido(f)]
                d["favoritas"] = _favoritas_validas(d.get("favoritas"))
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

    def agregar_grupo_wiz(self, nombre: str, clave: str, focos: list[dict]) -> dict:
        with self._candado:
            nombre = _limpiar_nombre(nombre)
            direccion = f"WIZ:{clave}"
            if any(d["direccion"] == direccion for d in self.dispositivos):
                raise ValueError("Ese grupo de focos ya está guardado")
            validos = [f for f in focos if _foco_valido(f)]
            if not validos:
                raise ValueError("El grupo necesita al menos un foco")
            grupo = {"id": uuid.uuid4().hex[:8], "tipo": "wiz_grupo", "nombre": nombre, "direccion": direccion,
                     "focos": [{"mac": f["mac"].lower(), "ip": f["ip"], "nombre": f"Foco {i}"}
                               for i, f in enumerate(validos, start=1)],
                     "favoritas": list(FAVORITAS_POR_DEFECTO), "ultimo_estado": {}, "fuentes": []}
            self.dispositivos.append(grupo)
            return grupo

    def foco(self, id_: str, mac: str) -> dict:
        grupo = self.buscar(id_)
        foco = next((f for f in (grupo or {}).get("focos", []) if f["mac"] == mac), None)
        if foco is None:
            raise KeyError(mac)
        return foco

    def renombrar_foco(self, id_: str, mac: str, nombre: str) -> None:
        with self._candado:
            self.foco(id_, mac)["nombre"] = _limpiar_nombre(nombre)

    def actualizar_ip(self, id_: str, mac: str, ip: str) -> None:
        with self._candado:
            with contextlib.suppress(KeyError):
                self.foco(id_, mac)["ip"] = ip

    def poner_favoritas(self, id_: str, ids: list[int]) -> None:
        with self._candado:
            grupo = self.buscar(id_)
            if grupo is None:
                raise KeyError(id_)
            if _favoritas_validas(ids) != list(ids) or len(ids) > MAX_FAVORITAS:
                raise ValueError(f"Favoritas inválidas (hasta {MAX_FAVORITAS} escenas distintas)")
            grupo["favoritas"] = list(ids)

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
            if estado and dispositivo["tipo"] == "wiz_grupo":
                dispositivo["ultimo_estado"] = {k: v for k, v in estado.items() if k in CLAVES_CACHE_WIZ}
            elif estado:
                dispositivo["ultimo_estado"].update({k: v for k, v in estado.items() if k in CLAVES_CACHE})
            if fuentes is not None:
                dispositivo["fuentes"] = list(fuentes)
