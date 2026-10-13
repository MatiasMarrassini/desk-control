"""Controlador de una placa Xeno3 sobre un Transporte (protocolo en PROTOCOLO.md)."""
import asyncio
import json
from typing import Callable

from widget.dispositivos import protocolo as p
from widget.dispositivos.transporte import Transporte


class ErrorProtocolo(Exception):
    """El sable no respondió como indica el protocolo."""


def _es_respuesta_de_archivos(clave: str, valor) -> bool:
    # ls y fontname con la forma ["/N","Nombre"] responden a consultas de archivos: no son estado del sable.
    return clave == "ls" or (clave == "fontname" and isinstance(valor, list))


class SableXeno:
    def __init__(self, transporte: Transporte, timeout_respuesta: float = 5.0):
        self.transporte = transporte
        self.estado: dict = {}
        self.al_cambiar: Callable[[dict], None] | None = None
        self.al_error: Callable[[str, str], None] | None = None
        self._timeout = timeout_respuesta
        self._esperas: dict[str, list[asyncio.Future]] = {}
        self._ensambladores = {p.CAR_HANDSHAKE: p.Ensamblador(), p.CAR_DATOS: p.Ensamblador()}

    async def conectar(self) -> None:
        """Conecta, saluda (el sable responde con todo su estado) y pide autorización."""
        t = self.transporte
        await t.conectar()
        await t.suscribir(p.CAR_HANDSHAKE, self._receptor(p.CAR_HANDSHAKE))
        saludo = self._esperar("HandShake")
        await t.escribir(p.CAR_HANDSHAKE, p.MENSAJE_HANDSHAKE, True)
        try:
            await asyncio.wait_for(saludo, self._timeout)
        except asyncio.TimeoutError:
            raise ErrorProtocolo("El sable no respondió al saludo") from None

        await t.suscribir(p.CAR_DATOS, self._receptor(p.CAR_DATOS))
        permiso = self._esperar("Authorize")
        await t.escribir(p.CAR_DATOS, p.MENSAJE_AUTORIZAR, False)
        try:
            valor = await asyncio.wait_for(permiso, self._timeout)
        except asyncio.TimeoutError:
            valor = self._autorizacion_leida(await t.leer(p.CAR_DATOS))
        if valor != "AccessAllowed":
            raise ErrorProtocolo(f"Autorización rechazada: {valor!r}")

    @staticmethod
    def _autorizacion_leida(datos: bytes):
        try:
            tipo, cuerpo = json.loads(datos.decode("utf-8"))
            return cuerpo.get("Authorize") if tipo == p.TIPO_RESPUESTA else None
        except (ValueError, TypeError, AttributeError):
            return None

    async def enviar(self, clave: str, valor) -> None:
        """Envía [2,{clave:valor}]. La confirmación llega después como cambio de estado."""
        await self.transporte.escribir(p.CAR_DATOS, p.armar(clave, valor), False)

    async def listar_fuentes(self) -> list[str]:
        """Nombres de las fuentes en orden de carpeta (índice 0 = carpeta 1). Solo lectura."""
        rango = await self._consultar("ls", "/")
        if not (isinstance(rango, list) and len(rango) >= 2 and all(isinstance(n, int) for n in rango)):
            return []
        nombres = []
        for n in range(rango[0], rango[-1] + 1):
            valor = await self._consultar("fontname", f"/{n}")
            valido = isinstance(valor, list) and len(valor) > 1 and isinstance(valor[1], str)
            nombres.append(valor[1] if valido else f"Fuente {n}")
        return nombres

    async def desconectar(self) -> None:
        for esperas in self._esperas.values():
            for futuro in esperas:
                if not futuro.done():
                    futuro.cancel()
        self._esperas.clear()
        await self.transporte.desconectar()

    async def _consultar(self, clave: str, valor):
        espera = self._esperar(clave)
        await self.enviar(clave, valor)
        try:
            return await asyncio.wait_for(espera, self._timeout)
        except asyncio.TimeoutError:
            raise ErrorProtocolo(f"Sin respuesta a {clave}") from None

    def _esperar(self, clave: str) -> asyncio.Future:
        futuro = asyncio.get_running_loop().create_future()
        self._esperas.setdefault(clave, []).append(futuro)
        return futuro

    def _resolver(self, clave: str, valor) -> None:
        for futuro in self._esperas.pop(clave, []):
            if not futuro.done():
                futuro.set_result(valor)

    def _receptor(self, uuid: str) -> Callable[[bytes], None]:
        def recibir(datos: bytes) -> None:
            for tipo, cuerpo in self._ensambladores[uuid].agregar(datos):
                self._procesar(tipo, cuerpo)
        return recibir

    def _procesar(self, tipo: int, cuerpo: dict) -> None:
        if tipo == p.TIPO_ERROR:
            for clave, mensaje in cuerpo.items():
                self._resolver(clave, None)
                if self.al_error:
                    self.al_error(clave, str(mensaje))
            return
        if tipo != p.TIPO_RESPUESTA:
            return
        cambios = {k: v for k, v in cuerpo.items() if not _es_respuesta_de_archivos(k, v)}
        self.estado.update(cambios)
        for clave, valor in cuerpo.items():
            self._resolver(clave, valor)
        if cambios and self.al_cambiar:
            self.al_cambiar(cambios)
