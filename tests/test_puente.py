import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from bleak.exc import BleakBluetoothNotAvailableError, BleakBluetoothNotAvailableReason

from tests.ayudas import esperar_sync
from tests.sable_simulado import FUENTES, SableSimulado
from widget.bucle import BucleAsync
from widget.config import Config
from tests.foco_simulado import iniciar_foco
from widget.dispositivos.sesion import SesionSable
from widget.dispositivos.wiz import GrupoWiz
from widget.puente import Puente

PREFIJO = "window.deskControl && window.deskControl.recibir("


class VentanaFalsa:
    def __init__(self):
        self.scripts = []

    def run_js(self, script):
        self.scripts.append(script)

    def eventos(self):
        return [json.loads(s[len(PREFIJO):-1]) for s in self.scripts if s.startswith(PREFIJO)]


@pytest.fixture
def entorno(tmp_path):
    config = Config.cargar(tmp_path / "config.json")
    dispositivo = config.agregar_dispositivo("xeno", "Mi sable", "AA:BB:CC:DD:EE:FF")
    bucle = BucleAsync()
    bucle.iniciar()
    simulados = []
    resultado_busqueda = {"valor": []}

    def crear_sesion(d):
        if d["tipo"] == "wiz_grupo":
            return GrupoWiz(d["focos"], estado_inicial=d.get("ultimo_estado"), timeout=0.1, intentos=2,
                            intervalo=0.1, espera_rebusqueda=0, buscar=lambda: asyncio.sleep(0, result=[]))

        def fabrica():
            sim = SableSimulado()
            simulados.append(sim)
            return sim
        return SesionSable(fabrica, estado_inicial=d.get("ultimo_estado"), pausa_reintento=0.01,
                           inactividad=5, timeout_respuesta=0.5)

    async def buscar_falso():
        if isinstance(resultado_busqueda["valor"], Exception):
            raise resultado_busqueda["valor"]
        return resultado_busqueda["valor"]

    resultado_focos = {"valor": []}

    async def buscar_focos_falso():
        return resultado_focos["valor"]

    puente = Puente(config, bucle, crear_sesion, buscar=buscar_falso, buscar_focos=buscar_focos_falso)
    ventana = VentanaFalsa()
    ocultadas = []
    puente._conectar_ventana(ventana, al_ocultar=lambda: ocultadas.append(True))
    yield SimpleNamespace(config=config, id=dispositivo["id"], puente=puente, ventana=ventana,
                          simulados=simulados, busqueda=resultado_busqueda, ocultadas=ocultadas,
                          focos_busqueda=resultado_focos, bucle=bucle)
    bucle.ejecutar(puente._cerrar()).result(5)
    bucle.detener()


def test_inicial_muestra_cache(entorno):
    entorno.config.actualizar_cache(entorno.id, estado={"Volume": 5})
    d = entorno.puente.inicial()["dispositivos"][0]
    assert d["nombre"] == "Mi sable" and d["conexion"] == "espera" and d["estado"]["Volume"] == 5


def test_enviar_conecta_emite_eventos_y_actualiza_cache(entorno):
    assert entorno.puente.sable_enviar(entorno.id, "Volume", 30) == {"ok": True}
    esperar_sync(lambda: any(e["tipo"] == "estado" and e["datos"].get("Volume") == 30
                             for e in entorno.ventana.eventos()))
    assert {"id": entorno.id, "tipo": "conexion", "datos": {"estado": "conectado"}} in entorno.ventana.eventos()
    assert entorno.config.buscar(entorno.id)["ultimo_estado"]["Volume"] == 30


def test_al_conectar_sin_cache_lee_las_fuentes_solo(entorno):
    entorno.puente.sable_enviar(entorno.id, "Volume", 30)
    esperar_sync(lambda: any(e["tipo"] == "fuentes" for e in entorno.ventana.eventos()))
    assert entorno.config.buscar(entorno.id)["fuentes"] == FUENTES


def test_enviar_invalido_devuelve_error_sin_conectar(entorno):
    r = entorno.puente.sable_enviar(entorno.id, "Reset", True)
    assert r["ok"] is False and "no permitido" in r["error"]
    assert entorno.simulados == []


def test_fuentes_desde_cache_sin_conectar(entorno):
    entorno.config.actualizar_cache(entorno.id, fuentes=["A", "B"])
    assert entorno.puente.sable_fuentes(entorno.id) == {"ok": True, "fuentes": ["A", "B"]}
    assert entorno.simulados == []


def test_fuentes_refrescar_lee_del_sable(entorno):
    entorno.config.actualizar_cache(entorno.id, fuentes=["A"])
    assert entorno.puente.sable_fuentes(entorno.id, True) == {"ok": True, "fuentes": FUENTES}


def test_buscar_marca_guardados(entorno):
    entorno.busqueda["valor"] = [{"direccion": "AA:BB:CC:DD:EE:FF", "nombre": "Saber", "rssi": -80},
                                 {"direccion": "11:22:33:44:55:66", "nombre": "Saber", "rssi": -90}]
    r = entorno.puente.buscar()
    assert [s["guardado"] for s in r["encontrados"]] == [True, False]
    assert all(s["tipo"] == "xeno" for s in r["encontrados"])


def test_buscar_con_bluetooth_apagado_igual_encuentra_focos(entorno):
    entorno.busqueda["valor"] = BleakBluetoothNotAvailableError("off", BleakBluetoothNotAvailableReason.POWERED_OFF)
    entorno.focos_busqueda["valor"] = [{"mac": "aa01", "ip": "192.168.1.6", "puerto": 38899, "room": 7}]
    r = entorno.puente.buscar()
    assert r["ok"] is True and r["error_bluetooth"] is True
    assert r["encontrados"] == [{"tipo": "wiz_grupo", "clave": "7", "nombre": "Cuarto",
                                 "focos": [{"mac": "aa01", "ip": "192.168.1.6"}], "guardado": False}]


def test_guardar_duplicado_y_renombrar(entorno):
    assert entorno.puente.guardar_dispositivo("aa:bb:cc:dd:ee:ff", "Otro")["ok"] is False
    r = entorno.puente.guardar_dispositivo("11:22:33:44:55:66", "Segundo")
    assert r["ok"] and r["dispositivo"]["nombre"] == "Segundo"
    assert entorno.puente.renombrar_dispositivo(r["dispositivo"]["id"], "   ")["ok"] is False


def test_quitar_cierra_la_sesion(entorno):
    entorno.puente.sable_enviar(entorno.id, "Volume", 30)
    esperar_sync(lambda: entorno.simulados and entorno.simulados[0].conectado)
    assert entorno.puente.quitar_dispositivo(entorno.id) == {"ok": True}
    assert not entorno.simulados[0].conectado
    assert entorno.config.dispositivos == []


def test_llamadas_simultaneas_crean_una_sola_sesion(tmp_path):
    # pywebview atiende cada llamada de JS en un hilo nuevo: dos primeras órdenes casi juntas no deben abrir 2 conexiones.
    import threading
    import time
    config = Config.cargar(tmp_path / "config.json")
    d = config.agregar_dispositivo("xeno", "Mi sable", "AA:BB:CC:DD:EE:FF")
    bucle = BucleAsync()
    bucle.iniciar()
    creadas = []

    def crear_sesion(_d):
        time.sleep(0.05)  # agranda la ventana de la carrera
        creadas.append(1)
        return SesionSable(lambda: SableSimulado(), pausa_reintento=0.01, inactividad=5, timeout_respuesta=0.5)

    puente = Puente(config, bucle, crear_sesion)
    hilos = [threading.Thread(target=puente.sable_enviar, args=(d["id"], "Volume", 10 + i)) for i in range(5)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert len(creadas) == 1
    bucle.ejecutar(puente._cerrar()).result(5)
    bucle.detener()


def test_emitir_codifica_texto_raro(entorno):
    raro = '<b>"x"</b> \'; alert(1)//'
    entorno.puente._emitir({"id": "x", "tipo": "fuentes", "datos": [raro]})
    assert entorno.ventana.eventos()[-1]["datos"] == [raro]
    assert " " not in entorno.ventana.scripts[-1]


def test_ocultar_llama_al_callback(entorno):
    assert entorno.puente.ocultar() == {"ok": True}
    assert entorno.ocultadas == [True]


def grupo_con_focos(entorno):
    uno = entorno.bucle.ejecutar(iniciar_foco(mac="aa0000000001")).result(2)
    dos = entorno.bucle.ejecutar(iniciar_foco(mac="aa0000000002")).result(2)
    focos = [{"mac": f.mac, "ip": "127.0.0.1"} for f in (uno, dos)]
    g = entorno.config.agregar_grupo_wiz("Cuarto", "7", focos)
    g["focos"][0]["puerto"], g["focos"][1]["puerto"] = uno.puerto, dos.puerto  # solo para pruebas
    return g, uno, dos


def test_inicial_muestra_el_grupo_de_focos(entorno):
    g, uno, dos = grupo_con_focos(entorno)
    vista = next(d for d in entorno.puente.inicial()["dispositivos"] if d["id"] == g["id"])
    assert vista["tipo"] == "wiz_grupo" and [f["nombre"] for f in vista["focos"]] == ["Foco 1", "Foco 2"]
    assert vista["favoritas"] == [12, 15, 16, 14, 4, 5, 1] and len(vista["escenas"]) == 33
    assert vista["sincronizados"] is True
    uno.cerrar(); dos.cerrar()


def test_luces_enviar_llega_a_los_focos_y_emite_estado(entorno):
    g, uno, dos = grupo_con_focos(entorno)
    assert entorno.puente.luces_enviar(g["id"], {"dimming": 40}) == {"ok": True}
    assert uno.estado["dimming"] == dos.estado["dimming"] == 40
    esperar_sync(lambda: any(e["id"] == g["id"] and e["tipo"] == "estado" and e["datos"]["grupo"].get("dimming") == 40
                             for e in entorno.ventana.eventos()))
    assert entorno.config.buscar(g["id"])["ultimo_estado"]["dimming"] == 40
    uno.cerrar(); dos.cerrar()


def test_luces_enviar_invalido_o_sin_respuesta(entorno):
    g, uno, dos = grupo_con_focos(entorno)
    r = entorno.puente.luces_enviar(g["id"], {"reboot": True})
    assert r["ok"] is False and "no permitido" in r["error"]
    uno.activo = dos.activo = False
    r = entorno.puente.luces_enviar(g["id"], {"dimming": 40})
    assert r == {"ok": False, "error": "Ningún foco respondió"}
    uno.cerrar(); dos.cerrar()


def test_luces_un_foco_y_sincronizar(entorno):
    g, uno, dos = grupo_con_focos(entorno)
    entorno.puente.luces_enviar(g["id"], {"state": True, "temp": 3000})
    entorno.puente.luces_enviar(g["id"], {"state": False}, "aa0000000002")
    assert dos.estado["state"] is False and uno.estado["state"] is True
    assert entorno.puente.luces_sincronizar(g["id"]) == {"ok": True}
    assert dos.estado["state"] is True
    uno.cerrar(); dos.cerrar()


def test_visibilidad_combina_ventana_y_pestana(entorno):
    g, uno, dos = grupo_con_focos(entorno)
    entorno.puente._ventana_visible(True)
    entorno.puente.luces_visible(g["id"], True)
    esperar_sync(lambda: len(uno.recibidos) >= 2)
    entorno.puente._ventana_visible(False)  # ocultar el widget pausa la consulta
    time.sleep(0.2)
    cantidad = len(uno.recibidos)
    time.sleep(0.4)
    assert len(uno.recibidos) == cantidad
    entorno.puente._ventana_visible(True)  # al volver a mostrarlo, la pestaña sigue activa: retoma
    esperar_sync(lambda: len(uno.recibidos) > cantidad)
    entorno.puente.luces_visible(g["id"], False)
    uno.cerrar(); dos.cerrar()


def test_cambio_de_ip_se_guarda(entorno):
    g, uno, dos = grupo_con_focos(entorno)
    controlador = entorno.puente._sesion(g["id"])
    controlador.al_evento("ip", {"mac": "aa0000000001", "ip": "192.168.1.30"})
    assert entorno.config.buscar(g["id"])["focos"][0]["ip"] == "192.168.1.30"
    uno.cerrar(); dos.cerrar()


def test_favoritas_y_nombres_de_focos(entorno):
    g, uno, dos = grupo_con_focos(entorno)
    assert entorno.puente.luces_favoritas(g["id"], [4, 5]) == {"ok": True}
    assert entorno.puente.luces_favoritas(g["id"], [999])["ok"] is False
    assert entorno.puente.renombrar_foco(g["id"], "aa0000000001", "Mesa de luz") == {"ok": True}
    vista = next(d for d in entorno.puente.inicial()["dispositivos"] if d["id"] == g["id"])
    assert vista["focos"][0]["nombre"] == "Mesa de luz" and vista["favoritas"] == [4, 5]
    uno.cerrar(); dos.cerrar()


def test_guardar_grupo(entorno):
    r = entorno.puente.guardar_grupo("9", "Living", [{"mac": "cc01", "ip": "192.168.1.9"}])
    assert r["ok"] and r["dispositivo"]["tipo"] == "wiz_grupo" and r["dispositivo"]["nombre"] == "Living"
    assert entorno.puente.guardar_grupo("9", "Otra vez", [{"mac": "cc01", "ip": "192.168.1.9"}])["ok"] is False
