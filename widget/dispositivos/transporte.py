"""Transporte BLE: interfaz común (para poder simular el sable en pruebas) e implementación real con bleak."""
import asyncio
from typing import Callable, Protocol

from bleak import BleakClient, BleakScanner


class SableNoEncontrado(Exception):
    """El sable no apareció al buscarlo (apagado, lejos o conectado a otro dispositivo)."""


class Transporte(Protocol):
    al_desconectar: Callable[[], None] | None

    @property
    def conectado(self) -> bool: ...

    async def conectar(self) -> None: ...

    async def desconectar(self) -> None: ...

    async def suscribir(self, uuid: str, callback: Callable[[bytes], None]) -> None: ...

    async def escribir(self, uuid: str, datos: bytes, con_respuesta: bool) -> None: ...

    async def leer(self, uuid: str) -> bytes: ...


class TransporteBleak:
    """Conexión real por Bluetooth con bleak. `al_desconectar` se llama en el hilo del bucle asyncio."""

    def __init__(self, direccion: str, timeout_busqueda: float = 10.0, timeout_conexion: float = 40.0):
        self.direccion = direccion
        self.al_desconectar: Callable[[], None] | None = None
        self._timeout_busqueda = timeout_busqueda
        self._timeout_conexion = timeout_conexion
        self._cliente: BleakClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def conectado(self) -> bool:
        return self._cliente is not None and self._cliente.is_connected

    async def conectar(self) -> None:
        self._loop = asyncio.get_running_loop()
        dispositivo = await BleakScanner.find_device_by_address(self.direccion, timeout=self._timeout_busqueda)
        if dispositivo is None:
            raise SableNoEncontrado(self.direccion)
        self._cliente = BleakClient(dispositivo, disconnected_callback=self._al_corte, timeout=self._timeout_conexion)
        await self._cliente.connect()

    def _al_corte(self, _cliente) -> None:
        if self.al_desconectar is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self.al_desconectar)

    async def desconectar(self) -> None:
        if self._cliente is not None and self._cliente.is_connected:
            await self._cliente.disconnect()

    async def suscribir(self, uuid: str, callback: Callable[[bytes], None]) -> None:
        await self._cliente.start_notify(uuid, lambda _car, datos: callback(bytes(datos)))

    async def escribir(self, uuid: str, datos: bytes, con_respuesta: bool) -> None:
        await self._cliente.write_gatt_char(uuid, datos, response=con_respuesta)

    async def leer(self, uuid: str) -> bytes:
        return bytes(await self._cliente.read_gatt_char(uuid))
