"""Paso 3: se conecta a un dispositivo y lista sus servicios y características (solo lectura, no escribe nada).

Uso: python pruebas/inspeccionar.py <DIRECCION> [<DIRECCION> ...]
"""
import asyncio
import sys

from bleak import BleakClient

SERVICIOS_XENO = {
    "0000dae0-0000-1000-8000-00805f9b34fb",
    "00003ab0-0000-1000-8000-00805f9b34fb",
}


async def inspeccionar(direccion: str):
    print(f"\n=== {direccion} ===")
    try:
        async with BleakClient(direccion, timeout=40.0) as cliente:
            print(f"Conectado. MTU: {cliente.mtu_size}")
            es_xeno = False
            for servicio in cliente.services:
                if servicio.uuid.lower() in SERVICIOS_XENO:
                    es_xeno = True
                print(f"Servicio {servicio.uuid}  ({servicio.description})")
                for car in servicio.characteristics:
                    print(f"   Caract. {car.uuid}  [{', '.join(car.properties)}]")
            print(">>> ES UNA PLACA XENO" if es_xeno else "No tiene los servicios Xeno.")
    except Exception as e:
        print(f"No se pudo conectar: {type(e).__name__}: {e}")


async def main():
    for direccion in sys.argv[1:]:
        await inspeccionar(direccion)


if __name__ == "__main__":
    asyncio.run(main())
