"""Paso 5: primeros comandos de escritura (volumen, encender hoja, color)."""
import asyncio
import json

from xeno import Xeno

PASOS = [
    ("Volume", 20),
    ("PowerOn", True),
    ("BackgroundColor", [0, 255, 0]),
]


async def main():
    sable = Xeno()
    try:
        await sable.conectar()
        for clave, valor in PASOS:
            await sable.enviar(clave, valor)
            await asyncio.sleep(3)
            sable.log(f"   estado de {clave} según el sable: {json.dumps(sable.estado.get(clave))}")
    finally:
        await sable.desconectar()


if __name__ == "__main__":
    asyncio.run(main())
