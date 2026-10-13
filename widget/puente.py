"""API que la ventana (JavaScript) llama vía pywebview, y eventos que Python le envía.

pywebview expone a JS todos los métodos y atributos públicos de este objeto: lo interno lleva guion bajo.
"""
import asyncio
import contextlib
import json
import logging
import threading
from typing import Callable

from widget.bucle import BucleAsync
from widget.config import Config
from widget.dispositivos import wiz_protocolo
from widget.dispositivos.busqueda import agrupar_por_cuarto, buscar_focos, buscar_sables
from widget.dispositivos.protocolo import ComandoInvalido
from widget.dispositivos.sesion import CONECTADO, ESPERA, SesionSable, es_bluetooth_apagado
from widget.dispositivos.wiz import GrupoWiz

log = logging.getLogger(__name__)

TIMEOUT_CORTO = 5
TIMEOUT_LUCES = 10  # peor caso: 3 intentos + re-búsqueda por MAC (2 s) + 3 intentos ≈ 5,6 s
TIMEOUT_CIERRE = 15
TIMEOUT_BUSQUEDA = 30
TIMEOUT_FUENTES = 180


class Puente:
    def __init__(self, config: Config, bucle: BucleAsync, crear_controlador: Callable[[dict], object],
                 buscar=buscar_sables, buscar_focos=buscar_focos):
        self._config = config
        self._bucle = bucle
        self._crear_sesion = crear_controlador  # SesionSable (xeno) o GrupoWiz (wiz_grupo) según el tipo
        self._buscar = buscar
        self._buscar_focos = buscar_focos
        self._sesiones: dict[str, object] = {}
        self._candado_sesiones = threading.Lock()  # pywebview atiende cada llamada de JS en un hilo distinto
        self._ventana = None
        self._al_ocultar: Callable[[], None] | None = None
        self._ventana_esta_visible = True
        self._pestanas_visibles: set[str] = set()

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
        async def ambos():
            return await asyncio.gather(self._buscar(), self._buscar_focos(), return_exceptions=True)

        try:
            sables, focos = self._bucle.ejecutar(ambos()).result(TIMEOUT_BUSQUEDA)
        except Exception:
            log.exception("Error al buscar dispositivos")
            return {"ok": False, "error": "fallo"}
        error_bluetooth = isinstance(sables, BaseException)
        if error_bluetooth and not es_bluetooth_apagado(sables):
            log.error("Error al buscar sables: %r", sables)
        if isinstance(focos, BaseException):
            log.error("Error al buscar focos: %r", focos)
            focos = []
        guardadas = {d["direccion"] for d in self._config.dispositivos}
        encontrados = [] if error_bluetooth else [
            {**s, "tipo": "xeno", "guardado": s["direccion"] in guardadas} for s in sables]
        encontrados += [{**g, "guardado": f"WIZ:{g['clave']}" in guardadas} for g in agrupar_por_cuarto(focos)]
        return {"ok": True, "encontrados": encontrados, "error_bluetooth": error_bluetooth}

    def guardar_dispositivo(self, direccion, nombre) -> dict:
        try:
            dispositivo = self._config.agregar_dispositivo("xeno", nombre, direccion)
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        self._guardar()
        return {"ok": True, "dispositivo": self._vista_dispositivo(dispositivo)}

    def guardar_grupo(self, clave, nombre, focos) -> dict:
        try:
            grupo = self._config.agregar_grupo_wiz(nombre, str(clave), focos)
        except (ValueError, TypeError) as error:
            return {"ok": False, "error": str(error)}
        self._guardar()
        return {"ok": True, "dispositivo": self._vista_dispositivo(grupo)}

    def luces_enviar(self, id_, params, mac=None) -> dict:
        try:
            ok = self._bucle.ejecutar(self._grupo(id_).enviar(params, mac)).result(TIMEOUT_LUCES)
        except (wiz_protocolo.ComandoInvalido, KeyError) as error:
            return {"ok": False, "error": str(error).strip("'")}
        return {"ok": True} if ok else {"ok": False, "error": "Ningún foco respondió"}

    def luces_sincronizar(self, id_) -> dict:
        try:
            ok = self._bucle.ejecutar(self._grupo(id_).sincronizar()).result(TIMEOUT_LUCES)
        except KeyError as error:
            return {"ok": False, "error": str(error).strip("'")}
        return {"ok": True} if ok else {"ok": False, "error": "Ningún foco respondió"}

    def luces_reintentar(self, id_) -> dict:
        try:
            self._bucle.ejecutar(self._grupo(id_).reintentar()).result(TIMEOUT_BUSQUEDA)
        except KeyError as error:
            return {"ok": False, "error": str(error).strip("'")}
        return {"ok": True}

    def luces_visible(self, id_, visible) -> dict:
        if visible:
            self._pestanas_visibles.add(id_)
        else:
            self._pestanas_visibles.discard(id_)
        try:
            self._aplicar_visibilidad(id_)
        except KeyError as error:
            return {"ok": False, "error": str(error).strip("'")}
        return {"ok": True}

    def luces_favoritas(self, id_, ids) -> dict:
        try:
            self._config.poner_favoritas(id_, ids)
        except (ValueError, KeyError) as error:
            return {"ok": False, "error": str(error).strip("'")}
        self._guardar()
        return {"ok": True}

    def renombrar_foco(self, id_, mac, nombre) -> dict:
        try:
            self._config.renombrar_foco(id_, mac, nombre)
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        except KeyError:
            return {"ok": False, "error": "Foco desconocido"}
        controlador = self._sesiones.get(id_)
        if isinstance(controlador, GrupoWiz):
            controlador.renombrar_foco(mac, self._config.foco(id_, mac)["nombre"])
        self._guardar()
        return {"ok": True}

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
        self._pestanas_visibles.discard(id_)
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
        controlador = self._sesiones.get(d["id"])
        with self._config.candado:  # el hilo del Bluetooth/UDP actualiza la caché mientras tanto
            estado = dict(controlador.estado) if controlador else dict(d["ultimo_estado"])
            base = {"id": d["id"], "tipo": d["tipo"], "nombre": d["nombre"], "direccion": d["direccion"],
                    "conexion": controlador.conexion if controlador else ESPERA, "estado": estado}
            if d["tipo"] == "wiz_grupo":
                nombres = {f["mac"]: f["nombre"] for f in d["focos"]}
                focos = controlador.vista_focos() if controlador else [
                    {"mac": f["mac"], "nombre": f["nombre"], "estado": {}, "responde": None} for f in d["focos"]]
                for foco in focos:
                    foco["nombre"] = nombres.get(foco["mac"], foco["nombre"])
                return {**base, "focos": focos, "favoritas": list(d["favoritas"]),
                        "sincronizados": controlador.sincronizados if controlador else True,
                        "escenas": wiz_protocolo.lista_escenas()}
            return {**base, "fuentes": list(d["fuentes"])}

    def _grupo(self, id_: str) -> GrupoWiz:
        controlador = self._sesion(id_)
        if not isinstance(controlador, GrupoWiz):
            raise KeyError("No es un grupo de focos")
        return controlador

    def _ventana_visible(self, visible: bool) -> None:
        """Lo llama main al mostrar/ocultar la ventana: sin ventana visible no se consulta a los focos."""
        self._ventana_esta_visible = visible
        for id_ in list(self._pestanas_visibles):
            with contextlib.suppress(KeyError):
                self._aplicar_visibilidad(id_)

    def _aplicar_visibilidad(self, id_: str) -> None:
        efectivo = self._ventana_esta_visible and id_ in self._pestanas_visibles
        self._bucle.ejecutar(self._grupo(id_).visible(efectivo)).result(TIMEOUT_CORTO)

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
        """Corre en el hilo del Bluetooth/UDP."""
        if isinstance(self._sesiones.get(id_), GrupoWiz):
            if tipo == "ip":
                self._config.actualizar_ip(id_, datos["mac"], datos["ip"])
                self._guardar()
                return
            if tipo == "estado":
                self._config.actualizar_cache(id_, estado=datos["grupo"])
            self._emitir({"id": id_, "tipo": tipo, "datos": datos})
            return
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
