"""Búsqueda de placas Xeno3 cercanas (solo las que anuncian sus servicios: nada de teles ni auriculares)."""
from typing import Iterable

from bleak import BleakScanner

from widget.dispositivos.protocolo import SERVICIOS_XENO


def es_xeno(service_uuids: Iterable[str]) -> bool:
    return any(u.lower() in SERVICIOS_XENO for u in service_uuids)


async def buscar_sables(segundos: float = 8.0) -> list[dict]:
    encontrados = await BleakScanner.discover(timeout=segundos, return_adv=True)
    sables = [
        {"direccion": d.address.upper(), "nombre": adv.local_name or d.name or "Sable Xeno3", "rssi": adv.rssi}
        for d, adv in encontrados.values()
        if es_xeno(adv.service_uuids)
    ]
    return sorted(sables, key=lambda s: -s["rssi"])
