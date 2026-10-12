"""Envía comandos al sable desde la línea de comandos.

Uso:
    python pruebas/enviar.py                          -> solo conecta y muestra el estado
    python pruebas/enviar.py PowerOn false            -> un comando
    python pruebas/enviar.py Volume 20 BackgroundColor [0,255,0]   -> varios, en orden

Los valores se interpretan como JSON (números, true/false, [r,g,b]); si no son JSON válido se envían como texto.
"""
import asyncio
import json
import sys

from xeno import Xeno

CLAVES_RESUMEN = ["PowerOn", "Power", "Volume", "BackgroundColor", "Brightness", "CurrentSoundPackageNo", "fontname"]


def interpretar(valor: str):
    try:
        return json.loads(valor)
    except json.JSONDecodeError:
        return valor


async def main(argumentos: list[str]):
    if len(argumentos) % 2:
        sys.exit("Los argumentos deben ir en pares: Clave valor")
    pares = [(argumentos[i], interpretar(argumentos[i + 1])) for i in range(0, len(argumentos), 2)]

    sable = Xeno()
    try:
        await sable.conectar()
        for clave, valor in pares:
            await sable.enviar(clave, valor)
            await asyncio.sleep(1.5)
        resumen = {k: sable.estado.get(k) for k in CLAVES_RESUMEN}
        sable.log("Resumen: " + json.dumps(resumen, ensure_ascii=False))
    finally:
        await sable.desconectar()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
