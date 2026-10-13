from tests.foco_simulado import iniciar_foco
from widget.dispositivos import wiz_protocolo as w
from widget.dispositivos import wiz_transporte as t


async def test_pedir_recibe_la_respuesta():
    foco = await iniciar_foco()
    r = await t.pedir("127.0.0.1", w.armar_lectura("getPilot"), metodo="getPilot", puerto=foco.puerto)
    assert r["result"]["dimming"] == 100 and r["result"]["mac"] == foco.mac
    foco.cerrar()


async def test_pedir_reintenta_si_se_pierden_paquetes():
    foco = await iniciar_foco(perder=2)
    r = await t.pedir("127.0.0.1", w.armar_set({"dimming": 30}), metodo="setPilot", puerto=foco.puerto,
                      timeout=0.1, intentos=3)
    assert r["result"]["success"] is True and foco.estado["dimming"] == 30
    assert len(foco.recibidos) == 3
    foco.cerrar()


async def test_pedir_devuelve_none_si_no_responde():
    foco = await iniciar_foco(perder=3)
    r = await t.pedir("127.0.0.1", w.armar_lectura("getPilot"), metodo="getPilot", puerto=foco.puerto,
                      timeout=0.1, intentos=3)
    assert r is None
    foco.cerrar()


async def test_pedir_ignora_respuestas_de_otro_metodo():
    foco = await iniciar_foco(metodo_equivocado=True)
    r = await t.pedir("127.0.0.1", w.armar_lectura("getPilot"), metodo="getPilot", puerto=foco.puerto, timeout=0.3)
    assert r["method"] == "getPilot"
    foco.cerrar()


async def test_difundir_junta_las_respuestas_de_varios_focos():
    uno = await iniciar_foco(mac="aa0000000001")
    dos = await iniciar_foco(mac="aa0000000002")
    respuestas = await t.difundir([w.armar_lectura("getSystemConfig")],
                                  [("127.0.0.1", uno.puerto), ("127.0.0.1", dos.puerto)], segundos=0.3)
    assert sorted(r["result"]["mac"] for _, r in respuestas) == ["aa0000000001", "aa0000000002"]
    assert {origen for origen, _ in respuestas} == {("127.0.0.1", uno.puerto), ("127.0.0.1", dos.puerto)}
    uno.cerrar()
    dos.cerrar()


def test_direccion_de_difusion():
    assert t.direccion_difusion("192.168.1.8") == "192.168.1.255"
    assert t.direccion_difusion("10.0.0.37") == "10.0.0.255"
