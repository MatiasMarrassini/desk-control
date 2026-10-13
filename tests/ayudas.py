import asyncio
import time


async def esperar_hasta(condicion, segundos: float = 2.0):
    fin = asyncio.get_running_loop().time() + segundos
    while not condicion():
        if asyncio.get_running_loop().time() > fin:
            raise AssertionError("La condición no se cumplió a tiempo")
        await asyncio.sleep(0.01)


def esperar_sync(condicion, segundos: float = 3.0):
    fin = time.monotonic() + segundos
    while not condicion():
        if time.monotonic() > fin:
            raise AssertionError("La condición no se cumplió a tiempo")
        time.sleep(0.02)
