"""Cliente BLE para placas Xeno3 (protocolo en PROTOCOLO.md).

Uso como script (paso 4): conecta, hace handshake + autorización y escucha el estado que reporta el sable.
    python pruebas/xeno.py [DIRECCION]

Sin dirección, busca la primera placa Xeno3 cercana (o usa la variable de entorno XENO_SABLE).
"""
import asyncio
import datetime
import json
import os
import pathlib
import sys

from bleak import BleakClient, BleakScanner

SERVICIOS_XENO = {"0000dae0-0000-1000-8000-00805f9b34fb", "00003ab0-0000-1000-8000-00805f9b34fb"}
CAR_HANDSHAKE = "0000dae1-0000-1000-8000-00805f9b34fb"
CAR_DATOS = "00003ab1-0000-1000-8000-00805f9b34fb"

CARPETA_LOGS = pathlib.Path(__file__).resolve().parent.parent / "logs"


async def buscar_sable(segundos: float = 15.0):
    """Devuelve el primer dispositivo que anuncia los servicios Xeno3, o None."""
    return await BleakScanner.find_device_by_filter(
        lambda _d, adv: bool({u.lower() for u in adv.service_uuids} & SERVICIOS_XENO), timeout=segundos)


class Xeno:
    def __init__(self, direccion: str | None = None):
        self.direccion = direccion or os.environ.get("XENO_SABLE")
        self.cliente: BleakClient | None = None
        self.estado: dict = {}
        self.mensajes: asyncio.Queue = asyncio.Queue()
        self._buffers = {CAR_HANDSHAKE: b"", CAR_DATOS: b""}
        CARPETA_LOGS.mkdir(exist_ok=True)
        marca = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self._log = open(CARPETA_LOGS / f"sesion_{marca}.log", "a", encoding="utf-8")

    def log(self, texto: str):
        linea = f"{datetime.datetime.now():%H:%M:%S.%f}"[:-3] + f"  {texto}"
        print(linea)
        self._log.write(linea + "\n")
        self._log.flush()

    def _al_notificar(self, uuid: str):
        canal = "dae1" if uuid == CAR_HANDSHAKE else "3ab1"

        def manejar(_car, datos: bytearray):
            # Un mensaje largo puede llegar partido en varias notificaciones: se acumula hasta que sea JSON válido.
            self._buffers[uuid] += bytes(datos)
            texto = self._buffers[uuid].decode("utf-8", errors="replace")
            try:
                mensaje = json.loads(texto)
            except json.JSONDecodeError:
                return
            self._buffers[uuid] = b""
            self.log(f"<- [{canal}] {texto}")
            if isinstance(mensaje, list) and len(mensaje) == 2 and isinstance(mensaje[1], dict):
                if mensaje[0] == 3:
                    self.estado.update(mensaje[1])
                self.mensajes.put_nowait(mensaje)

        return manejar

    async def _escribir(self, uuid: str, mensaje: str):
        canal = "dae1" if uuid == CAR_HANDSHAKE else "3ab1"
        self.log(f"-> [{canal}] {mensaje}")
        # dae1 admite escritura con respuesta; 3ab1 solo sin respuesta.
        await self.cliente.write_gatt_char(uuid, mensaje.encode("utf-8"), response=(uuid == CAR_HANDSHAKE))

    async def conectar(self):
        destino = self.direccion
        if not destino:
            self.log("Buscando una placa Xeno3...")
            destino = await buscar_sable()
            if destino is None:
                raise RuntimeError("No se encontró ninguna placa Xeno3. ¿Está encendida, cerca y sin el teléfono conectado?")
        self.cliente = BleakClient(destino, timeout=40.0)
        self.log(f"Conectando a {getattr(destino, 'address', destino)}...")
        await self.cliente.connect()
        self.log(f"Conectado (MTU {self.cliente.mtu_size})")

        await self.cliente.start_notify(CAR_HANDSHAKE, self._al_notificar(CAR_HANDSHAKE))
        await self._escribir(CAR_HANDSHAKE, '[2,{"HandShake":"HelloDamien"}]')
        await asyncio.sleep(1.0)

        await self.cliente.start_notify(CAR_DATOS, self._al_notificar(CAR_DATOS))
        await self._escribir(CAR_DATOS, '[2,{"Authorize":"SaberOfDamien"}]')
        await asyncio.sleep(1.0)
        leido = await self.cliente.read_gatt_char(CAR_DATOS)
        self.log(f"<- [3ab1 lectura] {bytes(leido).decode('utf-8', errors='replace')}")
        if self.estado.get("Authorize") != "AccessAllowed":
            try:
                if json.loads(bytes(leido))[1].get("Authorize") == "AccessAllowed":
                    self.estado["Authorize"] = "AccessAllowed"
            except (ValueError, IndexError, AttributeError, TypeError):
                pass
        self.log(f"Autorizado: {self.estado.get('Authorize') == 'AccessAllowed'}")

    async def enviar(self, clave: str, valor):
        """Envía un comando [2,{clave:valor}] por el canal de datos."""
        await self._escribir(CAR_DATOS, json.dumps([2, {clave: valor}], separators=(",", ":")))

    async def desconectar(self):
        if self.cliente and self.cliente.is_connected:
            await self.cliente.disconnect()
        self.log("Desconectado")
        self._log.close()


async def main():
    sable = Xeno(sys.argv[1] if len(sys.argv) > 1 else None)
    try:
        await sable.conectar()
        sable.log("Escuchando 10 s...")
        await asyncio.sleep(10)
        sable.log("Estado reportado:\n" + json.dumps(sable.estado, indent=2, ensure_ascii=False))
    finally:
        await sable.desconectar()


if __name__ == "__main__":
    asyncio.run(main())
