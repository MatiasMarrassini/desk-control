"""Prueba manual del motor con el sable real (solo lectura): python -m widget.diagnostico"""
import asyncio

from widget.config import CLAVES_CACHE
from widget.dispositivos.busqueda import buscar_sables
from widget.dispositivos.sesion import SesionSable
from widget.dispositivos.transporte import TransporteBleak


async def main() -> None:
    print("Buscando sables (8 s)...")
    sables = await buscar_sables()
    for s in sables:
        print(f"  {s['nombre']}  {s['direccion']}  {s['rssi']} dBm")
    if not sables:
        print("No se encontró ninguno. ¿Está encendido y sin el teléfono conectado?")
        return
    sesion = SesionSable(lambda: TransporteBleak(sables[0]["direccion"]))
    sesion.al_evento = lambda tipo, datos: print(f"  [{tipo}] {datos}" if tipo != "estado" else f"  [estado] {len(datos)} claves")
    fuentes = await sesion.fuentes()
    print("Fuentes:", fuentes)
    print("Estado:", {k: sesion.estado.get(k) for k in CLAVES_CACHE})
    await sesion.cerrar()


if __name__ == "__main__":
    asyncio.run(main())
