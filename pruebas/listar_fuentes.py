"""Lista las fuentes de sonido del sable (solo lectura).

Protocolo (ver PROTOCOLO.md §5):
    [2,{"ls":"/"}]          -> [3,{"ls":[primera, última]}]      rango de carpetas de fuentes
    [2,{"fontname":"/N"}]   -> [3,{"fontname":["/N","Nombre"]}]  nombre de la carpeta N
"""
import asyncio

from xeno import Xeno


async def esperar(sable: Xeno, clave: str, segundos: float = 3.0):
    """Espera el próximo mensaje [3,{clave:...}] y devuelve su valor (o None si no llega)."""
    fin = asyncio.get_running_loop().time() + segundos
    while (resto := fin - asyncio.get_running_loop().time()) > 0:
        try:
            tipo, cuerpo = await asyncio.wait_for(sable.mensajes.get(), resto)
        except asyncio.TimeoutError:
            break
        if tipo == 3 and clave in cuerpo:
            return cuerpo[clave]
    return None


async def main():
    sable = Xeno()
    try:
        await sable.conectar()
        while not sable.mensajes.empty():
            sable.mensajes.get_nowait()

        await sable.enviar("ls", "/")
        rango = await esperar(sable, "ls")
        if not rango or len(rango) < 2:
            sable.log(f"Respuesta inesperada a ls: {rango!r}")
            return
        primera, ultima = rango[0], rango[-1]

        fuentes = {}
        for n in range(primera, ultima + 1):
            await sable.enviar("fontname", f"/{n}")
            valor = await esperar(sable, "fontname")
            fuentes[n] = valor[1] if isinstance(valor, list) and len(valor) > 1 else None

        # CurrentSoundPackageNo cuenta desde 0; las carpetas, desde 1.
        actual = sable.estado.get("CurrentSoundPackageNo", -2) + 1
        sable.log("Fuentes en el sable:")
        for n, nombre in fuentes.items():
            sable.log(f"  {n:2d}  {nombre}{'   <- actual' if n == actual else ''}")
    finally:
        await sable.desconectar()


if __name__ == "__main__":
    asyncio.run(main())
