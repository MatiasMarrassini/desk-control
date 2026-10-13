"""UDP con asyncio para los focos WiZ.

No hay sockets en escucha en un puerto fijo: cada pedido o búsqueda usa un socket efímero que solo recibe
las respuestas a lo que envió, y se cierra al terminar.
"""
import asyncio
import ipaddress
import socket

from widget.dispositivos.wiz_protocolo import PUERTO, interpretar


class _Receptor(asyncio.DatagramProtocol):
    def __init__(self):
        self.cola: asyncio.Queue = asyncio.Queue()

    def datagram_received(self, datos, origen):
        self.cola.put_nowait((datos, origen))

    def error_received(self, exc):
        pass  # p. ej. "puerto inalcanzable": se trata como falta de respuesta


def ip_local() -> str:
    """IP de esta PC en la red local ("conectar" un socket UDP no envía nada: solo elige la interfaz)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]


def direccion_difusion(ip: str) -> str:
    return str(ipaddress.ip_network(f"{ip}/24", strict=False).broadcast_address)


async def _esperar(receptor: _Receptor, segundos: float):
    try:
        return await asyncio.wait_for(receptor.cola.get(), segundos)
    except asyncio.TimeoutError:
        return None


async def pedir(ip: str, mensaje: bytes, *, metodo: str, puerto: int = PUERTO, timeout: float = 0.6,
                intentos: int = 3) -> dict | None:
    """Envía `mensaje` y devuelve la primera respuesta válida del mismo `metodo`, reintentando si se pierde."""
    loop = asyncio.get_running_loop()
    transporte, receptor = await loop.create_datagram_endpoint(_Receptor, remote_addr=(ip, puerto))
    try:
        for _ in range(intentos):
            transporte.sendto(mensaje)
            fin = loop.time() + timeout
            while (resto := fin - loop.time()) > 0:
                llegada = await _esperar(receptor, resto)
                if llegada is None:
                    break
                respuesta = interpretar(llegada[0])
                if respuesta is not None and respuesta.get("method") == metodo:
                    return respuesta
        return None
    finally:
        transporte.close()


async def difundir(mensajes: list[bytes], destinos: list[tuple[str, int]], *,
                   segundos: float = 2.0) -> list[tuple[tuple[str, int], dict]]:
    """Envía cada mensaje a cada destino (p. ej. la dirección de difusión) y junta respuestas por `segundos`."""
    loop = asyncio.get_running_loop()
    transporte, receptor = await loop.create_datagram_endpoint(
        _Receptor, local_addr=("0.0.0.0", 0), allow_broadcast=True)
    try:
        for destino in destinos:
            for mensaje in mensajes:
                transporte.sendto(mensaje, destino)
        respuestas = []
        fin = loop.time() + segundos
        while (resto := fin - loop.time()) > 0:
            llegada = await _esperar(receptor, resto)
            if llegada is None:
                break
            respuesta = interpretar(llegada[0])
            if respuesta is not None:
                respuestas.append((tuple(llegada[1][:2]), respuesta))
        return respuestas
    finally:
        transporte.close()
