"""Busca focos WiZ en la red local y muestra su estado (solo lectura: getPilot y getSystemConfig).

Protocolo local de WiZ: JSON por UDP al puerto 38899, p. ej. {"method":"getPilot","params":{}}.
Uso: python pruebas/wiz_descubrir.py
"""
import ipaddress
import json
import socket
import time

PUERTO = 38899
CONSULTAS = [{"method": "getPilot", "params": {}}, {"method": "getSystemConfig", "params": {}}]


def ip_local() -> str:
    # "Conectar" un socket UDP no envía nada: solo elige la interfaz de salida.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]


def main(segundos: float = 3.0) -> None:
    ip = ip_local()
    difusion = str(ipaddress.ip_network(f"{ip}/24", strict=False).broadcast_address)
    print(f"IP de esta PC: {ip}  ->  difusión a {difusion}:{PUERTO}")

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.bind((ip, 0))
    s.settimeout(0.3)
    for consulta in CONSULTAS:
        s.sendto(json.dumps(consulta).encode(), (difusion, PUERTO))

    focos: dict[str, dict] = {}
    fin = time.monotonic() + segundos
    while time.monotonic() < fin:
        try:
            datos, (origen, _) = s.recvfrom(4096)
        except socket.timeout:
            continue
        try:
            respuesta = json.loads(datos)
        except ValueError:
            continue
        focos.setdefault(origen, {})[respuesta.get("method")] = respuesta.get("result", respuesta)
    s.close()

    if not focos:
        print("No respondió ningún foco. ¿Están encendidos (con corriente) y en la misma red wifi que la PC?")
        return
    for origen, r in sorted(focos.items()):
        print(f"\n=== Foco en {origen} ===")
        for metodo, resultado in r.items():
            print(f"  {metodo}: {json.dumps(resultado, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
