import asyncio

import pytest

from tests.ayudas import esperar_hasta
from tests.foco_simulado import iniciar_foco
from widget.dispositivos.wiz import GrupoWiz, combinar, params_de_pilot
from widget.dispositivos.wiz_protocolo import ComandoInvalido


async def grupo_de_dos(**opciones):
    uno = await iniciar_foco(mac="aa0000000001")
    dos = await iniciar_foco(mac="aa0000000002")
    focos = [{"mac": f.mac, "ip": "127.0.0.1", "puerto": f.puerto, "nombre": n} for f, n in ((uno, "Mesa"), (dos, "Escritorio"))]
    grupo = GrupoWiz(focos, timeout=0.1, intentos=2, intervalo=0.1, espera_rebusqueda=0, **opciones)
    eventos = []
    grupo.al_evento = lambda tipo, datos: eventos.append((tipo, datos))
    return grupo, uno, dos, eventos


def test_combinar_excluye_los_otros_modos():
    assert combinar({"temp": 4200, "dimming": 100}, {"r": 1, "g": 2, "b": 3}) == {"r": 1, "g": 2, "b": 3, "dimming": 100}
    assert combinar({"r": 1, "g": 2, "b": 3}, {"sceneId": 4, "speed": 100}) == {"sceneId": 4}
    assert combinar({"sceneId": 12, "state": True}, {"temp": 3000}) == {"temp": 3000, "state": True}


def test_params_de_pilot_prioriza_la_escena():
    assert params_de_pilot({"mac": "x", "state": True, "sceneId": 12, "temp": 4200, "dimming": 100}) == \
        {"state": True, "dimming": 100, "sceneId": 12}
    assert params_de_pilot({"state": False, "sceneId": 0, "temp": 3000, "dimming": 40}) == \
        {"state": False, "dimming": 40, "temp": 3000}
    assert params_de_pilot({"state": True, "sceneId": 0, "r": 1, "g": 2, "b": 3, "dimming": 10}) == \
        {"state": True, "dimming": 10, "r": 1, "g": 2, "b": 3}


async def test_enviar_al_grupo_llega_a_los_dos():
    grupo, uno, dos, eventos = await grupo_de_dos()
    assert await grupo.enviar({"dimming": 30}) is True
    assert uno.estado["dimming"] == dos.estado["dimming"] == 30
    assert grupo.estado["dimming"] == 30 and grupo.conexion == "conectado"
    assert any(t == "estado" and d["grupo"]["dimming"] == 30 for t, d in eventos)
    uno.cerrar(); dos.cerrar()


async def test_enviar_a_un_foco_no_toca_el_otro_ni_el_grupo():
    grupo, uno, dos, _ = await grupo_de_dos()
    await grupo.enviar({"state": False}, mac="aa0000000001")
    assert uno.estado["state"] is False and dos.estado["state"] is True
    assert "state" not in grupo.estado
    assert grupo.sincronizados is False
    uno.cerrar(); dos.cerrar()


async def test_sincronizar_iguala_los_focos():
    grupo, uno, dos, _ = await grupo_de_dos()
    await grupo.enviar({"state": True, "temp": 3000, "dimming": 60})
    await grupo.enviar({"state": False}, mac="aa0000000002")
    assert await grupo.sincronizar() is True
    assert dos.estado["state"] is True and dos.estado["temp"] == 3000
    assert grupo.sincronizados is True
    uno.cerrar(); dos.cerrar()


async def test_parcial_si_un_foco_no_responde():
    grupo, uno, dos, eventos = await grupo_de_dos(buscar=lambda: asyncio.sleep(0, result=[]))
    dos.activo = False
    assert await grupo.enviar({"dimming": 50}) is True
    assert uno.estado["dimming"] == 50
    assert grupo.conexion == "parcial"
    assert ("conexion", {"estado": "parcial", "responden": 1, "total": 2}) in eventos
    uno.cerrar(); dos.cerrar()


async def test_sin_respuesta_si_ninguno_responde():
    grupo, uno, dos, _ = await grupo_de_dos(buscar=lambda: asyncio.sleep(0, result=[]))
    uno.activo = dos.activo = False
    assert await grupo.enviar({"dimming": 50}) is False
    assert grupo.conexion == "sin_respuesta"
    uno.cerrar(); dos.cerrar()


async def test_reubica_por_mac_y_avisa():
    nuevo = await iniciar_foco(mac="bb0000000001")

    async def buscar():
        return [(("127.0.0.1", nuevo.puerto), {"method": "getSystemConfig", "result": {"mac": "bb0000000001"}})]

    # La IP "vieja" apunta a un puerto donde no hay nadie (como si el router le hubiera cambiado la IP).
    grupo = GrupoWiz([{"mac": "bb0000000001", "ip": "127.0.0.1", "puerto": 9}], buscar=buscar,
                     timeout=0.1, intentos=1, espera_rebusqueda=0)
    eventos = []
    grupo.al_evento = lambda tipo, datos: eventos.append((tipo, datos))
    assert await grupo.enviar({"dimming": 70}) is True
    assert nuevo.estado["dimming"] == 70
    assert grupo.focos[0]["puerto"] == nuevo.puerto
    assert ("ip", {"mac": "bb0000000001", "ip": "127.0.0.1"}) in eventos
    nuevo.cerrar()


async def test_consultar_lee_cambios_del_celular():
    grupo, uno, dos, _ = await grupo_de_dos()
    uno.estado.update(sceneId=0, temp=2700, dimming=40)  # cambiado desde la app WiZ
    await grupo.consultar()
    assert grupo.focos[0]["estado"] == {"state": True, "dimming": 40, "temp": 2700}
    assert grupo.estado == {"state": True, "dimming": 40, "temp": 2700}  # el del primer foco que responde
    assert grupo.sincronizados is False
    uno.cerrar(); dos.cerrar()


async def test_visible_consulta_y_se_pausa():
    grupo, uno, dos, _ = await grupo_de_dos()
    await grupo.visible(True)
    await esperar_hasta(lambda: len(uno.recibidos) >= 2, segundos=2)
    await grupo.visible(False)
    await asyncio.sleep(0.15)
    cantidad = len(uno.recibidos)
    await asyncio.sleep(0.4)
    assert len(uno.recibidos) == cantidad
    uno.cerrar(); dos.cerrar()


async def test_comando_invalido_no_envia_nada():
    grupo, uno, dos, _ = await grupo_de_dos()
    with pytest.raises(ComandoInvalido):
        await grupo.enviar({"reboot": True})
    with pytest.raises(KeyError):
        await grupo.enviar({"dimming": 50}, mac="ffffffffffff")
    assert uno.recibidos == [] and dos.recibidos == []
    uno.cerrar(); dos.cerrar()


async def test_cerrar_detiene_la_consulta():
    grupo, uno, dos, _ = await grupo_de_dos()
    await grupo.visible(True)
    await esperar_hasta(lambda: len(uno.recibidos) >= 1, segundos=2)
    await grupo.cerrar()
    cantidad = len(uno.recibidos)
    await asyncio.sleep(0.4)
    assert len(uno.recibidos) == cantidad
    uno.cerrar(); dos.cerrar()
