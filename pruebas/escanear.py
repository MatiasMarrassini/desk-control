"""Paso 2: escanea dispositivos BLE sin conectarse y marca los que parecen placas Xeno3."""
import asyncio

from bleak import BleakScanner

SERVICIOS_XENO = {
    "0000dae0-0000-1000-8000-00805f9b34fb",
    "00003ab0-0000-1000-8000-00805f9b34fb",
}


async def main(segundos: float = 10.0):
    print(f"Escaneando {segundos:.0f} s...")
    encontrados = await BleakScanner.discover(timeout=segundos, return_adv=True)

    filas = []
    for dispositivo, adv in encontrados.values():
        uuids = {u.lower() for u in adv.service_uuids}
        es_xeno = bool(uuids & SERVICIOS_XENO)
        filas.append((es_xeno, adv.rssi, dispositivo.address, adv.local_name or dispositivo.name or "", sorted(uuids)))

    filas.sort(key=lambda f: (not f[0], -f[1]))
    for es_xeno, rssi, direccion, nombre, uuids in filas:
        marca = ">>> XENO" if es_xeno else "        "
        print(f"{marca} {rssi:4d} dBm  {direccion}  {nombre!r:30}  {', '.join(u[4:8] for u in uuids)}")

    if not any(f[0] for f in filas):
        print("\nNo apareció ninguna placa Xeno (servicios dae0 / 3ab0).")


if __name__ == "__main__":
    asyncio.run(main())
