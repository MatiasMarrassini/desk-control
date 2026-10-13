"""Envía un setPilot a uno o varios focos WiZ y muestra la respuesta.

Uso: python pruebas/wiz_enviar.py '<params JSON>' IP [IP ...]
Ej.: python pruebas/wiz_enviar.py '{"dimming":30}' 192.168.1.6 192.168.1.7
     python pruebas/wiz_enviar.py '{"r":0,"g":80,"b":255,"dimming":100}' 192.168.1.6
     python pruebas/wiz_enviar.py '{"sceneId":12,"dimming":100}' 192.168.1.6
"""
import json
import socket
import sys

PUERTO = 38899


def enviar(ip: str, params: dict, intentos: int = 3) -> dict | None:
    mensaje = json.dumps({"method": "setPilot", "params": params}).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(0.6)
        for _ in range(intentos):  # UDP puede perder paquetes: se reintenta
            s.sendto(mensaje, (ip, PUERTO))
            try:
                datos, _ = s.recvfrom(4096)
                return json.loads(datos)
            except (socket.timeout, ValueError):
                continue
    return None


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    params = json.loads(sys.argv[1])
    for ip in sys.argv[2:]:
        print(f"{ip}: {enviar(ip, params)}")


if __name__ == "__main__":
    main()
