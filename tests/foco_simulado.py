"""Foco WiZ falso: responde por UDP en 127.0.0.1 (puerto efímero) como los focos reales."""
import asyncio
import json


class FocoSimulado(asyncio.DatagramProtocol):
    def __init__(self, mac="444f8e000001", room_id=23013550, perder=0, metodo_equivocado=False):
        self.mac = mac
        self.room_id = room_id
        self.estado = {"state": True, "sceneId": 12, "temp": 4200, "dimming": 100}
        self.recibidos: list[dict] = []
        self.activo = True             # False = foco sin corriente (no responde)
        self.perder = perder           # cantidad de pedidos a ignorar (pérdida de paquetes)
        self.metodo_equivocado = metodo_equivocado  # responde primero con otro método
        self.puerto = None
        self._transporte = None

    def connection_made(self, transporte):
        self._transporte = transporte

    def datagram_received(self, datos, origen):
        if not self.activo:
            return
        mensaje = json.loads(datos)
        self.recibidos.append(mensaje)
        if self.perder > 0:
            self.perder -= 1
            return
        if self.metodo_equivocado:
            self.metodo_equivocado = False
            self._responder(origen, "getSystemConfig", {"mac": self.mac})
        metodo = mensaje.get("method")
        if metodo == "getPilot":
            self._responder(origen, metodo, {"mac": self.mac, "rssi": -73, **self.estado})
        elif metodo == "getSystemConfig":
            self._responder(origen, metodo, {"mac": self.mac, "homeId": 1, "roomId": self.room_id, "groupId": 3,
                                             "moduleName": "ESP24_SHRGBC_01", "fwVersion": "1.38.0"})
        elif metodo == "setPilot":
            self._aplicar(mensaje["params"])
            self._responder(origen, metodo, {"success": True})
        else:
            datos = {"method": metodo, "error": {"code": -32601, "message": "Method not found"}}
            self._transporte.sendto(json.dumps(datos).encode(), origen)

    def _aplicar(self, params):
        if "temp" in params:
            for k in ("r", "g", "b"):
                self.estado.pop(k, None)
            self.estado["sceneId"] = 0
        if "r" in params:
            self.estado.pop("temp", None)
            self.estado["sceneId"] = 0
        if "sceneId" in params:
            for k in ("r", "g", "b", "temp"):
                self.estado.pop(k, None)
        self.estado.update({k: v for k, v in params.items() if k != "speed"})

    def _responder(self, origen, metodo, resultado):
        respuesta = {"method": metodo, "env": "pro", "result": resultado}
        self._transporte.sendto(json.dumps(respuesta).encode(), origen)

    def cerrar(self):
        if self._transporte:
            self._transporte.close()


async def iniciar_foco(**opciones) -> FocoSimulado:
    foco = FocoSimulado(**opciones)
    transporte, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: foco, local_addr=("127.0.0.1", 0))
    foco.puerto = transporte.get_extra_info("sockname")[1]
    return foco
