import pytest

from widget.dispositivos import protocolo as p


def test_armar_volumen():
    assert p.armar("Volume", 20) == b'[2,{"Volume":20}]'


def test_armar_color():
    assert p.armar("BackgroundColor", [0, 255, 0]) == b'[2,{"BackgroundColor":[0,255,0]}]'


def test_armar_fuente():
    assert p.armar("fontname", "/14") == b'[2,{"fontname":"/14"}]'


def test_armar_encendido():
    assert p.armar("PowerOn", True) == b'[2,{"PowerOn":true}]'


@pytest.mark.parametrize("clave, valor", [
    ("Reset", True),
    ("HardwareType", "RGB"),
    ("FileTransfer", ["download", "update.bin"]),
    ("rm", "/1"),
    ("Volume", 101),
    ("Volume", -1),
    ("Volume", True),
    ("Volume", "20"),
    ("Brightness", 20.5),
    ("BackgroundColor", [0, 255]),
    ("BackgroundColor", [0, 256, 0]),
    ("PowerOn", 1),
    ("ls", "/setting"),
    ("fontname", "/1/../x"),
    ("CurrentSoundPackageNo", -1),
])
def test_comandos_invalidos(clave, valor):
    with pytest.raises(p.ComandoInvalido):
        p.armar(clave, valor)


def test_handshake_y_autorizacion_exactos():
    assert p.MENSAJE_HANDSHAKE == b'[2,{"HandShake":"HelloDamien"}]'
    assert p.MENSAJE_AUTORIZAR == b'[2,{"Authorize":"SaberOfDamien"}]'


def test_ensamblador_mensaje_completo():
    assert p.Ensamblador().agregar(b'[3,{"Volume":20}]') == [(3, {"Volume": 20})]


def test_ensamblador_mensaje_partido():
    e = p.Ensamblador()
    assert e.agregar(b'[3,{"Vol') == []
    assert e.agregar(b'ume":20}]') == [(3, {"Volume": 20})]


def test_ensamblador_utf8_partido():
    datos = '[3,{"fontname":"Niño"}]'.encode("utf-8")
    corte = datos.index("ñ".encode("utf-8")) + 1  # parte el carácter de 2 bytes
    e = p.Ensamblador()
    assert e.agregar(datos[:corte]) == []
    assert e.agregar(datos[corte:]) == [(3, {"fontname": "Niño"})]


def test_ensamblador_descarta_basura_larga():
    e = p.Ensamblador()
    assert e.agregar(b"x" * 5000) == []
    assert e.agregar(b'[3,{"A":1}]') == [(3, {"A": 1})]


def test_ensamblador_ignora_json_con_otra_forma():
    e = p.Ensamblador()
    assert e.agregar(b'{"a":1}') == []
    assert e.agregar(b'[3,{"A":1}]') == [(3, {"A": 1})]
