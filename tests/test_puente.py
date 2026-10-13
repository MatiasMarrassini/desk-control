import json
from types import SimpleNamespace

import pytest
from bleak.exc import BleakBluetoothNotAvailableError, BleakBluetoothNotAvailableReason

from tests.ayudas import esperar_sync
from tests.sable_simulado import FUENTES, SableSimulado
from widget.bucle import BucleAsync
from widget.config import Config
from widget.dispositivos.sesion import SesionSable
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

    puente = Puente(config, bucle, crear_sesion, buscar=buscar_falso)
    ventana = VentanaFalsa()
    ocultadas = []
    puente._conectar_ventana(ventana, al_ocultar=lambda: ocultadas.append(True))
    yield SimpleNamespace(config=config, id=dispositivo["id"], puente=puente, ventana=ventana,
                          simulados=simulados, busqueda=resultado_busqueda, ocultadas=ocultadas)
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


def test_buscar_sin_bluetooth(entorno):
    entorno.busqueda["valor"] = BleakBluetoothNotAvailableError("off", BleakBluetoothNotAvailableReason.POWERED_OFF)
    assert entorno.puente.buscar() == {"ok": False, "error": "sin_bluetooth"}


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


def test_emitir_codifica_texto_raro(entorno):
    raro = '<b>"x"</b> \'; alert(1)//'
    entorno.puente._emitir({"id": "x", "tipo": "fuentes", "datos": [raro]})
    assert entorno.ventana.eventos()[-1]["datos"] == [raro]
    assert " " not in entorno.ventana.scripts[-1]


def test_ocultar_llama_al_callback(entorno):
    assert entorno.puente.ocultar() == {"ok": True}
    assert entorno.ocultadas == [True]
