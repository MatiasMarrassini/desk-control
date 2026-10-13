"""Grupo de focos WiZ: órdenes sincronizadas, estado por foco, consulta periódica y re-ubicación por MAC."""
import asyncio
import contextlib
import logging
import math
import time
from typing import Awaitable, Callable

from widget.dispositivos import wiz_protocolo as p
from widget.dispositivos import wiz_transporte as t

log = logging.getLogger(__name__)

ESPERA = "espera"
CONECTADO = "conectado"
PARCIAL = "parcial"
SIN_RESPUESTA = "sin_respuesta"
BUSCANDO = "buscando"

_MODOS = (frozenset({"r", "g", "b"}), frozenset({"temp"}), frozenset({"sceneId"}))
CLAVES_ESTADO = ("state", "dimming", "temp", "r", "g", "b", "sceneId")


def combinar(estado: dict, params: dict) -> dict:
    """Aplica `params` sobre `estado`: color, temperatura y escena se excluyen entre sí."""
    nuevo = dict(estado)
    for modo in _MODOS:
        if modo & params.keys():
            for otro in _MODOS:
                if otro is not modo:
                    for clave in otro:
                        nuevo.pop(clave, None)
    nuevo.update({k: v for k, v in params.items() if k != "speed"})
    return nuevo


def params_de_pilot(resultado: dict) -> dict:
    """Estado normalizado de un getPilot: estado, brillo y UNO de escena / color / temperatura."""
    salida = {}
    if "state" in resultado:
        salida["state"] = bool(resultado["state"])
    if "dimming" in resultado:
        salida["dimming"] = resultado["dimming"]
    if resultado.get("sceneId"):
        salida["sceneId"] = resultado["sceneId"]
    elif all(k in resultado for k in ("r", "g", "b")):
        salida.update(r=resultado["r"], g=resultado["g"], b=resultado["b"])
    elif "temp" in resultado:
        salida["temp"] = resultado["temp"]
    return salida


class GrupoWiz:
    def __init__(self, focos: list[dict], *, estado_inicial: dict | None = None,
                 buscar: Callable[[], Awaitable[list]] | None = None, intervalo: float = 5.0,
                 timeout: float = 0.6, intentos: int = 3, espera_rebusqueda: float = 30.0):
        self.focos = [{"mac": f["mac"], "nombre": f.get("nombre", ""), "ip": f["ip"],
                       "puerto": f.get("puerto", p.PUERTO), "estado": {}, "responde": None} for f in focos]
        self.estado = {k: v for k, v in (estado_inicial or {}).items() if k in CLAVES_ESTADO}
        self.conexion = ESPERA
        self.al_evento: Callable[[str, dict], None] | None = None
        self._buscar = buscar or self._buscar_en_red
        self._intervalo = intervalo
        self._timeout = timeout
        self._intentos = intentos
        self._espera_rebusqueda = espera_rebusqueda
        self._ultima_busqueda = -math.inf
        self._ubicaciones: dict[str, tuple[str, int]] = {}
        self._candado_busqueda = asyncio.Lock()
        self._tarea_consulta: asyncio.Task | None = None
        self._ultima_conexion = None
        self._tocado_por_separado = False  # un foco recibió una orden propia y no se volvió a sincronizar

    @property
    def sincronizados(self) -> bool:
        if self._tocado_por_separado:
            return False
        estados = [f["estado"] for f in self.focos if f["responde"]]
        return all(e == estados[0] for e in estados[1:])

    # ---- órdenes ----
    async def enviar(self, params: dict, mac: str | None = None) -> bool:
        """Envía setPilot al grupo (o a un foco). True si al menos un foco confirmó."""
        mensaje = p.armar_set(params)  # valida: lanza ComandoInvalido
        destinos = [f for f in self.focos if mac is None or f["mac"] == mac]
        if not destinos:
            raise KeyError("Foco desconocido")
        resultados = await asyncio.gather(*(self._enviar_a(f, mensaje, params) for f in destinos))
        if mac is None and any(resultados):
            self.estado = combinar(self.estado, params)
        elif mac is not None and any(resultados):
            self._tocado_por_separado = True
        self._actualizar_conexion()
        self._emitir_estado()
        return any(resultados)

    async def sincronizar(self) -> bool:
        params = {k: v for k, v in self.estado.items() if k in CLAVES_ESTADO}
        if not params:
            return False
        ok = await self.enviar(params)
        if ok:
            self._tocado_por_separado = False
            self._emitir_estado()
        return ok

    async def _enviar_a(self, foco: dict, mensaje: bytes, params: dict) -> bool:
        respuesta = await self._pedir(foco, mensaje, "setPilot")
        ok = bool(respuesta) and isinstance(respuesta.get("result"), dict) and respuesta["result"].get("success") is True
        if ok:
            foco["estado"] = combinar(foco["estado"], params)
        return ok

    # ---- lectura ----
    async def consultar(self) -> None:
        mensaje = p.armar_lectura("getPilot")
        respuestas = await asyncio.gather(*(self._pedir(f, mensaje, "getPilot") for f in self.focos))
        for foco, respuesta in zip(self.focos, respuestas):
            if respuesta and isinstance(respuesta.get("result"), dict):
                foco["estado"] = params_de_pilot(respuesta["result"])
        if all(f["responde"] for f in self.focos):
            self._tocado_por_separado = False  # se leyó el estado real de todos: decide la comparación
        primero = next((f for f in self.focos if f["responde"]), None)
        if primero is not None:
            self.estado = dict(primero["estado"])
        self._actualizar_conexion()
        self._emitir_estado()

    async def visible(self, si: bool) -> None:
        """Con la pestaña visible consulta cada `intervalo` s; oculta, no consulta nada."""
        if si and (self._tarea_consulta is None or self._tarea_consulta.done()):
            self._tarea_consulta = asyncio.create_task(self._consultar_siempre())
        elif not si and self._tarea_consulta is not None:
            self._tarea_consulta.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._tarea_consulta
            self._tarea_consulta = None

    async def reintentar(self) -> None:
        self._ultima_busqueda = -math.inf
        await self.consultar()

    async def cerrar(self) -> None:
        await self.visible(False)

    def renombrar_foco(self, mac: str, nombre: str) -> None:
        for foco in self.focos:
            if foco["mac"] == mac:
                foco["nombre"] = nombre

    def vista_focos(self) -> list[dict]:
        return [{"mac": f["mac"], "nombre": f["nombre"], "estado": dict(f["estado"]), "responde": f["responde"]}
                for f in self.focos]

    # ---- interno ----
    async def _consultar_siempre(self) -> None:
        while True:
            try:
                await self.consultar()
            except Exception:
                log.exception("Error al consultar los focos")
            await asyncio.sleep(self._intervalo)

    async def _pedir(self, foco: dict, mensaje: bytes, metodo: str) -> dict | None:
        respuesta = await self._pedir_ip(foco, mensaje, metodo)
        if respuesta is None and await self._reubicar(foco):
            respuesta = await self._pedir_ip(foco, mensaje, metodo)
        foco["responde"] = respuesta is not None
        return respuesta

    async def _pedir_ip(self, foco: dict, mensaje: bytes, metodo: str) -> dict | None:
        try:
            return await t.pedir(foco["ip"], mensaje, metodo=metodo, puerto=foco["puerto"],
                                 timeout=self._timeout, intentos=self._intentos)
        except OSError:
            return None

    async def _reubicar(self, foco: dict) -> bool:
        """Busca por MAC la dirección nueva del foco (difusión), como máximo cada `espera_rebusqueda` s."""
        async with self._candado_busqueda:
            if time.monotonic() - self._ultima_busqueda >= self._espera_rebusqueda:
                self._ultima_busqueda = time.monotonic()
                self._cambiar_conexion(BUSCANDO)
                try:
                    encontrados = await self._buscar()
                except OSError:
                    encontrados = []
                self._ubicaciones = {
                    r["result"]["mac"]: origen for origen, r in encontrados
                    if isinstance(r.get("result"), dict) and r["result"].get("mac")}
            nueva = self._ubicaciones.get(foco["mac"])
            if nueva is None or (nueva[0], nueva[1]) == (foco["ip"], foco["puerto"]):
                return False
            foco["ip"], foco["puerto"] = nueva[0], nueva[1]
            self._emitir("ip", {"mac": foco["mac"], "ip": foco["ip"]})
            return True

    async def _buscar_en_red(self) -> list:
        destino = (t.direccion_difusion(t.ip_local()), p.PUERTO)
        return await t.difundir([p.armar_lectura("getSystemConfig")], [destino], segundos=2.0)

    def _actualizar_conexion(self) -> None:
        total = len(self.focos)
        responden = sum(1 for f in self.focos if f["responde"])
        estado = CONECTADO if responden == total else PARCIAL if responden else SIN_RESPUESTA
        self._cambiar_conexion(estado, responden=responden, total=total)

    def _cambiar_conexion(self, estado: str, **extra) -> None:
        clave = (estado, tuple(sorted(extra.items())))
        self.conexion = estado
        if clave != self._ultima_conexion:  # no repetir el mismo evento en cada consulta
            self._ultima_conexion = clave
            self._emitir("conexion", {"estado": estado, **extra})

    def _emitir_estado(self) -> None:
        self._emitir("estado", {"grupo": dict(self.estado), "focos": self.vista_focos(),
                                "sincronizados": self.sincronizados})

    def _emitir(self, tipo: str, datos: dict) -> None:
        if self.al_evento is None:
            return
        try:
            self.al_evento(tipo, datos)
        except Exception:
            log.exception("Error al emitir el evento %s", tipo)
