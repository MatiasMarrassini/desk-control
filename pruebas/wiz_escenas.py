"""Verifica con un foco real que cada sceneId de la tabla es aceptado y reportado igual (y restaura el estado).

Uso: python pruebas/wiz_escenas.py IP     (tarda ~1 minuto; el foco cambia de escena varias veces)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from widget.dispositivos import wiz_protocolo as w  # noqa: E402
from widget.dispositivos import wiz_transporte as t  # noqa: E402
from widget.dispositivos.wiz import params_de_pilot  # noqa: E402


async def main(ip: str) -> None:
    antes = await t.pedir(ip, w.armar_lectura("getPilot"), metodo="getPilot")
    if not antes:
        sys.exit("El foco no responde")
    original = params_de_pilot(antes["result"])
    malas = []
    for escena_id, nombre in w.ESCENAS.items():
        r = await t.pedir(ip, w.armar_set({"state": True, "sceneId": escena_id}), metodo="setPilot")
        await asyncio.sleep(1.2)
        leido = await t.pedir(ip, w.armar_lectura("getPilot"), metodo="getPilot")
        reportada = (leido or {}).get("result", {}).get("sceneId")
        ok = bool(r and r.get("result", {}).get("success")) and reportada == escena_id
        print(f"{escena_id:3d} {nombre:22s} {'OK' if ok else f'DISTINTA (reporta {reportada})'}")
        if not ok:
            malas.append(escena_id)
    await t.pedir(ip, w.armar_set(original), metodo="setPilot")
    print("Restaurado:", original)
    print("Todas verificadas" if not malas else f"Revisar: {malas}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
