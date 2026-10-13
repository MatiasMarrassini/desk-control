"""API que la ventana (JavaScript) llama vía pywebview, y eventos que Python le envía.

pywebview expone a JS todos los métodos y atributos públicos de este objeto: lo interno lleva guion bajo.
"""
import asyncio
import json
import logging
import threading
from typing import Callable

from widget.bucle import BucleAsync
from widget.config import Config
from widget.dispositivos.busqueda import buscar_sables
from widget.dispositivos.protocolo import ComandoInvalido
from widget.dispositivos.sesion import CONECTADO, ESPERA, SesionSable, es_bluetooth_apagado

log = logging.getLogger(__name__)

TIMEOUT_CORTO = 5
TIMEOUT_CIERRE = 15
TIMEOUT_BUSQUEDA = 30
TIMEOUT_FUENTES = 180


class Puente:
    def __init__(self, config: Config, bucle: BucleAsync, crear_sesion: Callable[[dict], SesionSable],
                 buscar=buscar_sables):
        self._config = config
        self._bucle = bucle
        self._crear_sesion = crear_sesion
        self._buscar = buscar
        self._sesiones: dict[str, SesionSable] = {}
        self._candado_sesiones = threading.Lock()  # pywebview atiende cada llamada de JS en un hilo distinto
        self._ventana = None
        self._al_ocultar: Callable[[], None] | None = None

    def _conectar_ventana(self, ventana, al_ocultar: Callable[[], None]) -> None:
        self._ventana = ventana
        self._al_ocultar = al_ocultar

    # ---- API para JavaScript ----
    def inicial(self) -> dict:
        return {"dispositivos": [self._vista_dispositivo(d) for d in self._config.dispositivos]}

    def sable_enviar(self, id_, clave, valor) -> dict:
        try:
            self._bucle.ejecutar(self._sesion(id_).pedir(clave, valor)).result(TIMEOUT_CORTO)
        except (ComandoInvalido, KeyError) as error:
            return {"ok": False, "error": str(error).strip("'")}
        return {"ok": True}

    def sable_reintentar(self, id_) -> dict:
        try:
            self._bucle.ejecutar(self._sesion(id_).reintentar()).result(TIMEOUT_CORTO)
        except KeyError as error:
            return {"ok": False, "error": str(error).strip("'")}
        return {"ok": True}

    def sable_fuentes(self, id_, refrescar=False) -> dict:
        dispositivo = self._config.buscar(id_)
        if dispositivo is None:
            return {"ok": False, "error": "Dispositivo desconocido"}
        if dispositivo["fuentes"] and not refrescar:
            return {"ok": True, "fuentes": list(dispositivo["fuentes"])}
        nombres = self._bucle.ejecutar(self._sesion(id_).fuentes()).result(TIMEOUT_FUENTES)
        if not nombres:
            return {"ok": False, "error": "No se pudo leer la lista de fuentes"}
        self._config.actualizar_cache(id_, fuentes=nombres)
        self._guardar()
        return {"ok": True, "fuentes": nombres}

    def buscar(self) -> dict:
        try:
            encontrados = self._bucle.ejecutar(self._buscar()).result(TIMEOUT_BUSQUEDA)
        except Exception as error:
            if es_bluetooth_apagado(error):
                return {"ok": False, "error": "sin_bluetooth"}
            log.exception("Error al buscar dispositivos")
            return {"ok": False, "error": "fallo"}
        guardadas = {d["direccion"] for d in self._config.dispositivos}
        return {"ok": True, "encontrados": [{**s, "guardado": s["direccion"] in guardadas} for s in encontrados]}

    def guardar_dispositivo(self, direccion, nombre) -> dict:
        try:
            dispositivo = self._config.agregar_dispositivo("xeno", nombre, direccion)
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        self._guardar()
        return {"ok": True, "dispositivo": self._vista_dispositivo(dispositivo)}

    def renombrar_dispositivo(self, id_, nombre) -> dict:
        try:
            self._config.renombrar(id_, nombre)
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        except KeyError:
            return {"ok": False, "error": "Dispositivo desconocido"}
        self._guardar()
        return {"ok": True}

    def quitar_dispositivo(self, id_) -> dict:
        with self._candado_sesiones:
            sesion = self._sesiones.pop(id_, None)
        if sesion is not None:
            self._bucle.ejecutar(sesion.cerrar()).result(TIMEOUT_CIERRE)
        self._config.quitar(id_)
        self._guardar()
        return {"ok": True}

    def ocultar(self) -> dict:
        if self._al_ocultar is not None:
            self._al_ocultar()
        return {"ok": True}

    # ---- interno ----
    async def _cerrar(self) -> None:
        with self._candado_sesiones:
            sesiones = list(self._sesiones.values())
        for sesion in sesiones:
            await sesion.cerrar()

    def _vista_dispositivo(self, d: dict) -> dict:
        sesion = self._sesiones.get(d["id"])
        with self._config.candado:  # el hilo del Bluetooth actualiza la caché mientras tanto
            estado = dict(sesion.estado) if sesion else dict(d["ultimo_estado"])
            fuentes = list(d["fuentes"])
        return {
            "id": d["id"], "tipo": d["tipo"], "nombre": d["nombre"], "direccion": d["direccion"],
            "conexion": sesion.conexion if sesion else ESPERA, "estado": estado, "fuentes": fuentes,
        }

    def _sesion(self, id_: str) -> SesionSable:
        with self._candado_sesiones:
            if id_ not in self._sesiones:
                dispositivo = self._config.buscar(id_)
                if dispositivo is None:
                    raise KeyError("Dispositivo desconocido")
                sesion = self._crear_sesion(dispositivo)
                sesion.al_evento = lambda tipo, datos, i=id_: self._al_evento(i, tipo, datos)
                self._sesiones[id_] = sesion
            return self._sesiones[id_]

    def _al_evento(self, id_: str, tipo: str, datos: dict) -> None:
        """Corre en el hilo del Bluetooth."""
        if tipo == "estado":
            self._config.actualizar_cache(id_, estado=datos)
        elif tipo == "conexion" and datos["estado"] == ESPERA:
            self._guardar()
        elif tipo == "conexion" and datos["estado"] == CONECTADO:
            dispositivo = self._config.buscar(id_)
            total = self._sesiones[id_].estado.get("TotalSoundPackage")
            if dispositivo is not None and (not dispositivo["fuentes"] or (total and total != len(dispositivo["fuentes"]))):
                asyncio.ensure_future(self._refrescar_fuentes(id_))
        self._emitir({"id": id_, "tipo": tipo, "datos": datos})

    async def _refrescar_fuentes(self, id_: str) -> None:
        sesion = self._sesiones.get(id_)
        nombres = await sesion.fuentes() if sesion else None
        if nombres:
            self._config.actualizar_cache(id_, fuentes=nombres)
            self._guardar()
            self._emitir({"id": id_, "tipo": "fuentes", "datos": nombres})

    def _emitir(self, evento: dict) -> None:
        if self._ventana is None:
            return
        # json.dumps con ensure_ascii escapa comillas, < > y  : el texto del sable no puede inyectar código.
        script = f"window.deskControl && window.deskControl.recibir({json.dumps(evento)})"
        try:
            self._ventana.run_js(script)
        except Exception:
            log.debug("La ventana no pudo recibir el evento", exc_info=True)

    def _guardar(self) -> None:
        try:
            self._config.guardar()
        except OSError:
            log.exception("No se pudo guardar la configuración")
