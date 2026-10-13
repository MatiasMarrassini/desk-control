import asyncio

import pytest

from tests.sable_simulado import FUENTES, SableSimulado
from widget.dispositivos import protocolo as p
from widget.dispositivos.xeno import ErrorProtocolo, SableXeno


async def test_conectar_saluda_autoriza_y_carga_estado():
    sim = SableSimulado()
    sable = SableXeno(sim, timeout_respuesta=0.5)
    await sable.conectar()
    assert sim.escrituras[0] == (p.CAR_HANDSHAKE, p.MENSAJE_HANDSHAKE)
    assert sim.escrituras[1] == (p.CAR_DATOS, p.MENSAJE_AUTORIZAR)
    assert sable.estado["Volume"] == 20
    assert sable.estado["HandShake"] == "OK"


async def test_conectar_falla_si_no_saluda():
    with pytest.raises(ErrorProtocolo):
        await SableXeno(SableSimulado(responde_saludo=False), timeout_respuesta=0.2).conectar()


async def test_conectar_falla_si_rechaza_autorizacion():
    with pytest.raises(ErrorProtocolo):
        await SableXeno(SableSimulado(autoriza=False), timeout_respuesta=0.2).conectar()


async def test_autorizacion_por_lectura_si_no_llega_notificacion():
    sable = SableXeno(SableSimulado(autoriza_por_notificacion=False), timeout_respuesta=0.2)
    await sable.conectar()  # no lanza: la lectura de 3ab1 dice AccessAllowed


async def test_enviar_actualiza_estado_y_avisa():
    sable = SableXeno(SableSimulado(), timeout_respuesta=0.5)
    await sable.conectar()
    cambios = []
    sable.al_cambiar = cambios.append
    await sable.enviar("Volume", 50)
    await asyncio.sleep(0.01)
    assert sable.estado["Volume"] == 50
    assert {"Volume": 50} in cambios


async def test_enviar_comando_prohibido_no_escribe():
    sim = SableSimulado()
    sable = SableXeno(sim, timeout_respuesta=0.5)
    await sable.conectar()
    with pytest.raises(p.ComandoInvalido):
        await sable.enviar("Reset", True)
    assert not any(b"Reset" in d for _, d in sim.escrituras)


async def test_error_tipo_4_avisa_y_no_cambia_estado():
    sable = SableXeno(SableSimulado(errores={"Volume": "fuera de rango"}), timeout_respuesta=0.5)
    await sable.conectar()
    errores = []
    sable.al_error = lambda clave, mensaje: errores.append((clave, mensaje))
    await sable.enviar("Volume", 30)
    await asyncio.sleep(0.01)
    assert errores == [("Volume", "fuera de rango")]
    assert sable.estado["Volume"] == 20


async def test_listar_fuentes_no_ensucia_el_estado():
    sable = SableXeno(SableSimulado(), timeout_respuesta=0.5)
    await sable.conectar()
    assert await sable.listar_fuentes() == FUENTES
    assert sable.estado["fontname"] == "The Princess"
    assert "ls" not in sable.estado
