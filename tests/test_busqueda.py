from widget.dispositivos.busqueda import es_xeno


def test_reconoce_servicios_xeno():
    assert es_xeno(["0000dae0-0000-1000-8000-00805f9b34fb"])
    assert es_xeno(["0000180F-0000-1000-8000-00805F9B34FB", "00003AB0-0000-1000-8000-00805F9B34FB"])


def test_rechaza_otros_dispositivos():
    assert not es_xeno([])
    assert not es_xeno(["0000fe9f-0000-1000-8000-00805f9b34fb"])


from tests.foco_simulado import iniciar_foco  # noqa: E402
from widget.dispositivos.busqueda import agrupar_por_cuarto, buscar_focos  # noqa: E402


async def test_buscar_focos_junta_config_y_estado():
    uno = await iniciar_foco(mac="aa0000000002", room_id=7)
    dos = await iniciar_foco(mac="aa0000000001", room_id=7)
    focos = await buscar_focos(destinos=[("127.0.0.1", uno.puerto), ("127.0.0.1", dos.puerto)], segundos=0.3)
    assert [f["mac"] for f in focos] == ["aa0000000001", "aa0000000002"]
    assert focos[0]["room"] == 7 and focos[0]["modelo"] == "ESP24_SHRGBC_01" and focos[0]["rssi"] == -73
    assert focos[0]["puerto"] == dos.puerto
    uno.cerrar()
    dos.cerrar()


def test_agrupar_por_cuarto():
    focos = [{"mac": "a", "ip": "1", "puerto": 38899, "room": 7}, {"mac": "b", "ip": "2", "puerto": 38899, "room": 7},
             {"mac": "c", "ip": "3", "puerto": 38899, "room": 9}]
    grupos = agrupar_por_cuarto(focos)
    assert grupos[0] == {"tipo": "wiz_grupo", "clave": "7", "nombre": "Cuarto",
                         "focos": [{"mac": "a", "ip": "1"}, {"mac": "b", "ip": "2"}]}
    assert grupos[1]["clave"] == "9" and len(grupos[1]["focos"]) == 1
