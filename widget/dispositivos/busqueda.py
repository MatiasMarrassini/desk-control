"""Búsqueda de placas Xeno3 cercanas (solo las que anuncian sus servicios: nada de teles ni auriculares)."""
from typing import Iterable

from bleak import BleakScanner

from widget.dispositivos import wiz_protocolo as wp
from widget.dispositivos import wiz_transporte as wt
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


async def buscar_focos(destinos: list[tuple[str, int]] | None = None, segundos: float = 2.0) -> list[dict]:
    """Focos WiZ de la red local (difusión de getSystemConfig y getPilot; solo lectura)."""
    if destinos is None:
        destinos = [(wt.direccion_difusion(wt.ip_local()), wp.PUERTO)]
    respuestas = await wt.difundir([wp.armar_lectura("getSystemConfig"), wp.armar_lectura("getPilot")],
                                   destinos, segundos=segundos)
    focos: dict[str, dict] = {}
    for (ip, puerto), r in respuestas:
        resultado = r.get("result")
        if not isinstance(resultado, dict) or not isinstance(resultado.get("mac"), str):
            continue
        foco = focos.setdefault(resultado["mac"], {"mac": resultado["mac"], "ip": ip, "puerto": puerto,
                                                   "modelo": None, "room": None, "rssi": None})
        if r.get("method") == "getSystemConfig":
            foco["modelo"] = resultado.get("moduleName")
            foco["room"] = resultado.get("roomId")
        elif r.get("method") == "getPilot":
            foco["rssi"] = resultado.get("rssi")
    return sorted(focos.values(), key=lambda f: f["mac"])


def agrupar_por_cuarto(focos: list[dict]) -> list[dict]:
    """Un grupo por habitación de la cuenta WiZ (roomId), con nombre sugerido "Cuarto"."""
    grupos: dict[str, dict] = {}
    for foco in focos:
        clave = str(foco.get("room") if foco.get("room") is not None else foco["mac"])
        grupo = grupos.setdefault(clave, {"tipo": "wiz_grupo", "clave": clave, "nombre": "Cuarto", "focos": []})
        grupo["focos"].append({"mac": foco["mac"], "ip": foco["ip"]})
    return list(grupos.values())
