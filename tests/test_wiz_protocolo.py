import json

import pytest

from widget.dispositivos import wiz_protocolo as w


def test_armar_set_brillo():
    assert json.loads(w.armar_set({"dimming": 30})) == {"method": "setPilot", "params": {"dimming": 30}}


def test_armar_set_color_y_estado():
    params = {"state": True, "r": 0, "g": 80, "b": 255, "dimming": 100}
    assert json.loads(w.armar_set(params))["params"] == params


def test_armar_set_escena_animada_con_velocidad():
    assert json.loads(w.armar_set({"sceneId": 4, "speed": 120}))["params"] == {"sceneId": 4, "speed": 120}


def test_armar_lectura():
    assert json.loads(w.armar_lectura("getPilot")) == {"method": "getPilot", "params": {}}


@pytest.mark.parametrize("metodo", ["reboot", "reset", "setSystemConfig", "setWifiConfig", "upgrade", "registration"])
def test_metodos_prohibidos(metodo):
    with pytest.raises(w.ComandoInvalido):
        w.armar_lectura(metodo)


@pytest.mark.parametrize("params", [
    {},
    {"fadeIn": 100},
    {"dimming": 5},
    {"dimming": 101},
    {"dimming": True},
    {"temp": 9000},
    {"temp": 2000},
    {"sceneId": 99},
    {"r": 255},
    {"r": 255, "g": 0, "b": 300},
    {"r": 255, "g": 0, "b": 0, "temp": 3000},
    {"temp": 3000, "sceneId": 12},
    {"state": "true"},
    {"speed": 100},
    {"sceneId": 12, "speed": 100},
    {"sceneId": 4, "speed": 300},
    "no es un dict",
])
def test_params_invalidos(params):
    with pytest.raises(w.ComandoInvalido):
        w.armar_set(params)


def test_interpretar_respuesta_valida():
    assert w.interpretar(b'{"method":"setPilot","result":{"success":true}}') == {
        "method": "setPilot", "result": {"success": True}}


@pytest.mark.parametrize("datos", [b"basura", b"[1,2]", b'{"result":{}}', "ñ".encode("utf-16")])
def test_interpretar_descarta_lo_invalido(datos):
    assert w.interpretar(datos) is None


def test_lista_de_escenas_con_nombres_oficiales():
    escenas = w.lista_escenas()
    assert escenas[0]["animada"] is False and escenas[-1]["animada"] is True
    assert {"id": 12, "nombre": "Luz de día", "animada": False} in escenas
    assert {"id": 4, "nombre": "Fiesta", "animada": True} in escenas
    assert len(escenas) == len(w.ESCENAS) == 33
    assert all(i in w.ESCENAS for i in w.FAVORITAS_POR_DEFECTO) and len(w.FAVORITAS_POR_DEFECTO) == w.MAX_FAVORITAS
