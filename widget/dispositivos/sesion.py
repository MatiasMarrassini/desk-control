"""Conexión a demanda con un sable: cola de órdenes, reintentos y desconexión por inactividad."""
import asyncio
import contextlib
import logging
from typing import Callable

from bleak.exc import BleakBluetoothNotAvailableError

from widget.dispositivos.protocolo import validar
from widget.dispositivos.transporte import Transporte
from widget.dispositivos.xeno import SableXeno

log = logging.getLogger(__name__)

ESPERA = "espera"
CONECTANDO = "conectando"
CONECTADO = "conectado"
NO_ENCONTRADO = "no_encontrado"
SIN_BLUETOOTH = "sin_bluetooth"


def es_bluetooth_apagado(error: BaseException) -> bool:
    return isinstance(error, BleakBluetoothNotAvailableError)


class SesionSable:
    def __init__(self, crear_transporte: Callable[[], Transporte], *, estado_inicial: dict | None = None,
                 intentos: int = 3, pausa_reintento: float = 2.0, inactividad: float = 60.0,
                 timeout_respuesta: float = 5.0):
        self.estado: dict = dict(estado_inicial or {})
        self.conexion = ESPERA
        self.al_evento: Callable[[str, dict], None] | None = None
        self._crear_transporte = crear_transporte
        self._intentos = intentos
        self._pausa = pausa_reintento
        self._inactividad = inactividad
        self._timeout = timeout_respuesta
        self._sable: SableXeno | None = None
        self._pendientes: dict = {}
        self._trabajo: asyncio.Task | None = None
        self._tarea_inactividad: asyncio.Task | None = None
        self._candado = asyncio.Lock()

    # ---- API ----
    async def pedir(self, clave: str, valor) -> None:
        """Encola una orden (valida antes; si ya había una con la misma clave, queda solo la última)."""
        validar(clave, valor)
        self._pendientes.pop(clave, None)
        self._pendientes[clave] = valor
        if self._trabajo is None or self._trabajo.done():
            self._trabajo = asyncio.create_task(self._procesar())

    async def reintentar(self) -> None:
        if self._trabajo is None or self._trabajo.done():
            self._trabajo = asyncio.create_task(self._asegurar_conexion())

    async def fuentes(self) -> list[str] | None:
        """Lista de fuentes del sable, o None si no se pudo conectar o leer."""
        if not await self._asegurar_conexion():
            return None
        try:
            nombres = await self._sable.listar_fuentes()
        except Exception:
            log.exception("No se pudo leer la lista de fuentes")
            return None
        self._reiniciar_inactividad()
        return nombres

    async def cerrar(self) -> None:
        for tarea in (self._trabajo, self._tarea_inactividad):
            if tarea is not None and not tarea.done():
                tarea.cancel()
        self._pendientes.clear()
        await self._desconectar()

    # ---- interno ----
    async def _procesar(self) -> None:
        while self._pendientes:
            if not await self._asegurar_conexion():
                self._pendientes.clear()
                return
            clave = next(iter(self._pendientes))
            valor = self._pendientes.pop(clave)
            try:
                await self._sable.enviar(clave, valor)
            except Exception:
                log.exception("Fallo al enviar %s", clave)
                self._pendientes.clear()
                self._emitir("error", {"clave": clave, "mensaje": "No se pudo enviar al sable"})
                await self._desconectar()
                self._cambiar_conexion(ESPERA)
                return
            self._reiniciar_inactividad()

    async def _asegurar_conexion(self) -> bool:
        async with self._candado:
            if self._sable is not None and self._sable.transporte.conectado:
                return True
            for intento in range(1, self._intentos + 1):
                self._cambiar_conexion(CONECTANDO, intento=intento)
                transporte = self._crear_transporte()
                sable = SableXeno(transporte, self._timeout)
                sable.al_cambiar = self._al_cambiar
                sable.al_error = self._al_error
                try:
                    await sable.conectar()
                except Exception as error:
                    log.info("Intento %d de conexión fallido: %r", intento, error)
                    with contextlib.suppress(Exception):
                        await sable.desconectar()
                    if es_bluetooth_apagado(error):
                        self._cambiar_conexion(SIN_BLUETOOTH)
                        return False
                    if intento < self._intentos:
                        await asyncio.sleep(self._pausa)
                    continue
                transporte.al_desconectar = lambda s=sable: self._al_corte(s)
                self._sable = sable
                self._cambiar_conexion(CONECTADO)
                self._reiniciar_inactividad()
                return True
            self._cambiar_conexion(NO_ENCONTRADO)
            return False

    def _al_corte(self, sable: SableXeno) -> None:
        if sable is not self._sable:  # corte de una conexión que ya cerramos nosotros
            return
        self._sable = None
        if self._tarea_inactividad is not None:
            self._tarea_inactividad.cancel()
        self._cambiar_conexion(ESPERA)

    async def _desconectar(self) -> None:
        sable, self._sable = self._sable, None
        if sable is not None:
            with contextlib.suppress(Exception):
                await sable.desconectar()

    def _reiniciar_inactividad(self) -> None:
        if self._tarea_inactividad is not None and not self._tarea_inactividad.done():
            self._tarea_inactividad.cancel()
        self._tarea_inactividad = asyncio.create_task(self._esperar_inactividad())

    async def _esperar_inactividad(self) -> None:
        await asyncio.sleep(self._inactividad)
        async with self._candado:
            if self._pendientes or self._sable is None:
                return
            await self._desconectar()
            self._cambiar_conexion(ESPERA)

    def _al_cambiar(self, cambios: dict) -> None:
        self.estado.update(cambios)
        self._emitir("estado", dict(cambios))

    def _al_error(self, clave: str, mensaje: str) -> None:
        self._emitir("error", {"clave": clave, "mensaje": mensaje})

    def _cambiar_conexion(self, estado: str, **extra) -> None:
        self.conexion = estado
        self._emitir("conexion", {"estado": estado, **extra})

    def _emitir(self, tipo: str, datos: dict) -> None:
        if self.al_evento is None:
            return
        try:
            self.al_evento(tipo, datos)
        except Exception:
            log.exception("Error al emitir el evento %s", tipo)
