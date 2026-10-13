import asyncio

import pytest

from tests.ayudas import esperar_hasta
from tests.sable_simulado import FUENTES, SableSimulado
from widget.dispositivos.protocolo import ComandoInvalido
from widget.dispositivos.sesion import SesionSable


def sesion_con(*simulados, inactividad=5.0, estado_inicial=None):
    pendientes = list(simulados)
    creados = []

    def fabrica():
        sim = pendientes.pop(0) if pendientes else SableSimulado()
        creados.append(sim)
        return sim

    sesion = SesionSable(fabrica, estado_inicial=estado_inicial, intentos=3, pausa_reintento=0.01,
                         inactividad=inactividad, timeout_respuesta=0.3)
    eventos = []
    sesion.al_evento = lambda tipo, datos: eventos.append((tipo, datos))
    return sesion, creados, eventos


async def test_pedir_conecta_y_envia():
    s, creados, eventos = sesion_con()
    await s.pedir("Volume", 30)
    await esperar_hasta(lambda: s.estado.get("Volume") == 30)
    assert creados[0].comandos() == [{"Volume": 30}]
    assert ("conexion", {"estado": "conectando", "intento": 1}) in eventos
    assert ("conexion", {"estado": "conectado"}) in eventos
    await s.cerrar()


async def test_ordenes_repetidas_se_coalescen():
    s, creados, _ = sesion_con()
    for v in (10, 20, 30):
        await s.pedir("Volume", v)
    await s.pedir("Brightness", 50)
    await esperar_hasta(lambda: s.estado.get("Brightness") == 50)
    assert creados[0].comandos() == [{"Volume": 30}, {"Brightness": 50}]
    await s.cerrar()


async def test_reintenta_y_conecta_al_tercer_intento():
    s, creados, eventos = sesion_con(SableSimulado(fallos_conexion=1), SableSimulado(fallos_conexion=1))
    await s.pedir("Volume", 40)
    await esperar_hasta(lambda: s.conexion == "conectado")
    assert ("conexion", {"estado": "conectando", "intento": 3}) in eventos
    await esperar_hasta(lambda: creados[2].comandos() == [{"Volume": 40}])
    await s.cerrar()


async def test_no_encontrado_tras_tres_intentos():
    fallan = [SableSimulado(fallos_conexion=1) for _ in range(3)]
    s, creados, eventos = sesion_con(*fallan)
    await s.pedir("Volume", 40)
    await esperar_hasta(lambda: s.conexion == "no_encontrado")
    assert len(creados) == 3
    assert ("conexion", {"estado": "no_encontrado"}) in eventos
    await s.cerrar()


async def test_sin_bluetooth_no_reintenta():
    s, creados, eventos = sesion_con(SableSimulado(sin_bluetooth=True))
    await s.pedir("Volume", 40)
    await esperar_hasta(lambda: s.conexion == "sin_bluetooth")
    assert len(creados) == 1
    await s.cerrar()


async def test_desconecta_por_inactividad():
    s, creados, eventos = sesion_con(inactividad=0.1)
    await s.pedir("Volume", 30)
    await esperar_hasta(lambda: s.conexion == "conectado")
    await esperar_hasta(lambda: not creados[0].conectado, segundos=1.0)
    assert s.conexion == "espera"
    await s.cerrar()


async def test_corte_inesperado_vuelve_a_espera_y_reconecta():
    s, creados, _ = sesion_con()
    await s.pedir("Volume", 30)
    await esperar_hasta(lambda: s.estado.get("Volume") == 30)
    creados[0].simular_corte()
    assert s.conexion == "espera"
    await s.pedir("Volume", 45)
    await esperar_hasta(lambda: len(creados) == 2 and creados[1].comandos() == [{"Volume": 45}])
    await s.cerrar()


async def test_corte_durante_envio_avisa_y_reconecta():
    s, creados, eventos = sesion_con(SableSimulado(corta_en="Volume"))
    await s.pedir("Volume", 30)
    await esperar_hasta(lambda: any(t == "error" for t, _ in eventos))
    assert ("error", {"clave": "Volume", "mensaje": "No se pudo enviar al sable"}) in eventos
    assert s.conexion == "espera"
    await s.pedir("Brightness", 60)
    await esperar_hasta(lambda: len(creados) == 2 and creados[1].comandos() == [{"Brightness": 60}])
    await s.cerrar()


async def test_error_del_sable_se_emite():
    s, _, eventos = sesion_con(SableSimulado(errores={"Volume": "fuera de rango"}))
    await s.pedir("Volume", 30)
    await esperar_hasta(lambda: ("error", {"clave": "Volume", "mensaje": "fuera de rango"}) in eventos)
    await s.cerrar()


async def test_comando_prohibido_falla_sin_conectar():
    s, creados, _ = sesion_con()
    with pytest.raises(ComandoInvalido):
        await s.pedir("Reset", True)
    await asyncio.sleep(0.05)
    assert creados == []


async def test_fuentes_conecta_y_lista():
    s, _, _ = sesion_con()
    assert await s.fuentes() == FUENTES
    await s.cerrar()


async def test_fuentes_devuelve_none_si_no_conecta():
    s, _, _ = sesion_con(*[SableSimulado(fallos_conexion=1) for _ in range(3)])
    assert await s.fuentes() is None
    await s.cerrar()


async def test_estado_inicial_precargado_y_actualizado():
    s, _, _ = sesion_con(estado_inicial={"Volume": 5})
    assert s.estado["Volume"] == 5
    await s.pedir("Brightness", 70)
    await esperar_hasta(lambda: s.estado.get("Volume") == 20)  # el sable reporta su valor real al conectar
    await s.cerrar()
