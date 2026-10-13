"""Sable falso que implementa Transporte y responde como el real (según los logs de las pruebas manuales)."""
import asyncio
import json

from bleak.exc import BleakBluetoothNotAvailableError, BleakBluetoothNotAvailableReason

from widget.dispositivos import protocolo as p
from widget.dispositivos.transporte import SableNoEncontrado

FUENTES = ["The Chosen", "New Horizon", "The Princess"]
COLORES_POR_FUENTE = [[255, 0, 0], [0, 80, 255], [0, 255, 0]]


def estado_inicial() -> dict:
    return {
        "HardwareVersion": "XENOA000000000000", "SoftwareVersion": "DMN_XENO_B_SV1.4.0",
        "PowerOn": False, "CurrentSoundPackageNo": 2, "TotalSoundPackage": 3, "Power": 77,
        "Volume": 20, "BackgroundColor": [0, 255, 0], "Brightness": 100, "fontname": "The Princess",
    }


class SableSimulado:
    def __init__(self, *, fallos_conexion=0, sin_bluetooth=False, responde_saludo=True, autoriza=True,
                 autoriza_por_notificacion=True, errores=None, corta_en=None, retardo=0.0):
        self.al_desconectar = None
        self.retardo = retardo  # > 0: responde en serie, una notificación cada `retardo` s (como el sable real)
        self._proxima = 0.0
        self.estado = estado_inicial()
        self.fuentes = list(FUENTES)
        self.escrituras: list[tuple[str, bytes]] = []
        self.conexiones = 0
        self.fallos_conexion = fallos_conexion
        self.sin_bluetooth = sin_bluetooth
        self.responde_saludo = responde_saludo
        self.autoriza = autoriza
        self.autoriza_por_notificacion = autoriza_por_notificacion
        self.errores = errores or {}
        self.corta_en = corta_en
        self._conectado = False
        self._callbacks = {}

    @property
    def conectado(self) -> bool:
        return self._conectado

    async def conectar(self):
        if self.sin_bluetooth:
            raise BleakBluetoothNotAvailableError("Bluetooth apagado", BleakBluetoothNotAvailableReason.POWERED_OFF)
        if self.fallos_conexion > 0:
            self.fallos_conexion -= 1
            raise SableNoEncontrado("simulado")
        self.conexiones += 1
        self._conectado = True

    async def desconectar(self):
        if self._conectado:
            self._conectado = False
            if self.al_desconectar:  # bleak también avisa en las desconexiones pedidas
                self.al_desconectar()

    def simular_corte(self):
        self._conectado = False
        if self.al_desconectar:
            self.al_desconectar()

    async def suscribir(self, uuid, callback):
        self._callbacks[uuid] = callback

    async def leer(self, uuid):
        valor = "AccessAllowed" if self.autoriza else "AccessDenied"
        return json.dumps([3, {"Authorize": valor}]).encode()

    async def escribir(self, uuid, datos, con_respuesta):
        if not self._conectado:
            raise ConnectionError("no conectado")
        self.escrituras.append((uuid, bytes(datos)))
        _, cuerpo = json.loads(datos)
        (clave, valor), = cuerpo.items()
        if clave == self.corta_en:
            self.simular_corte()
            raise ConnectionError("corte simulado")
        if clave == "HandShake":
            if self.responde_saludo:
                partes = list(self.estado.items())
                for i in range(0, len(partes), 4):
                    self._notificar(p.CAR_HANDSHAKE, dict(partes[i:i + 4]))
                self._notificar(p.CAR_HANDSHAKE, {"HandShake": "OK"})
        elif clave == "Authorize":
            if self.autoriza and self.autoriza_por_notificacion:
                self._notificar(p.CAR_DATOS, {"Authorize": "AccessAllowed"})
        elif clave in self.errores:
            self._notificar(p.CAR_DATOS, {clave: self.errores[clave]}, tipo=p.TIPO_ERROR)
        elif clave == "ls":
            self._notificar(p.CAR_DATOS, {"ls": [1, len(self.fuentes)]})
        elif clave == "fontname":
            self._notificar(p.CAR_DATOS, {"fontname": [valor, self.fuentes[int(valor[1:]) - 1]]})
        elif clave == "CurrentSoundPackageNo":
            cambios = {"CurrentSoundPackageNo": valor, "fontname": self.fuentes[valor],
                       "BackgroundColor": COLORES_POR_FUENTE[valor]}
            self.estado.update(cambios)
            self._notificar(p.CAR_HANDSHAKE, cambios)
        else:
            self.estado[clave] = valor
            self._notificar(p.CAR_HANDSHAKE, {clave: valor})

    def _notificar(self, uuid, cuerpo, tipo=p.TIPO_RESPUESTA):
        datos = json.dumps([tipo, cuerpo], separators=(",", ":")).encode()
        callback = self._callbacks.get(uuid)
        if not callback:
            return
        loop = asyncio.get_running_loop()
        if self.retardo:
            self._proxima = max(loop.time(), self._proxima) + self.retardo
            loop.call_at(self._proxima, callback, datos)
        else:
            loop.call_soon(callback, datos)

    def comandos(self) -> list[dict]:
        """Comandos enviados por el canal de datos, sin contar la autorización."""
        return [json.loads(d)[1] for u, d in self.escrituras if u == p.CAR_DATOS and b"Authorize" not in d]
