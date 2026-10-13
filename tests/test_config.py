import json

import pytest

from widget.config import Config


def test_sin_archivo_usa_valores_por_defecto(tmp_path):
    c = Config.cargar(tmp_path / "config.json")
    assert c.datos["atajo"] == "ctrl+shift+space"
    assert c.datos["autoarranque"] is True
    assert c.dispositivos == []


def test_guardar_y_volver_a_cargar(tmp_path):
    ruta = tmp_path / "sub" / "config.json"
    c = Config.cargar(ruta)
    d = c.agregar_dispositivo("xeno", "Mi sable", "f4:65:0b:c0:38:5e")
    c.guardar()
    otra = Config.cargar(ruta)
    assert otra.buscar(d["id"])["direccion"] == "F4:65:0B:C0:38:5E"
    assert otra.buscar(d["id"])["nombre"] == "Mi sable"


def test_config_corrupta_usa_defecto_y_guarda_copia(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text("{ esto no es json", encoding="utf-8")
    c = Config.cargar(ruta)
    assert c.dispositivos == []
    assert len(list(tmp_path.glob("config.corrupto-*.json"))) == 1


def test_config_corrupta_con_tipos_incorrectos(tmp_path):
    ruta = tmp_path / "config.json"
    ruta.write_text(json.dumps({"dispositivos": "no es lista"}), encoding="utf-8")
    assert Config.cargar(ruta).dispositivos == []


def test_config_corrupta_filtra_dispositivos_incompletos(tmp_path):
    ruta = tmp_path / "config.json"
    validos = {"id": "a1", "tipo": "xeno", "nombre": "Sable", "direccion": "AA:BB:CC:DD:EE:FF"}
    ruta.write_text(json.dumps({"dispositivos": [validos, {"id": "b2"}, "basura"]}), encoding="utf-8")
    c = Config.cargar(ruta)
    assert [d["id"] for d in c.dispositivos] == ["a1"]
    assert c.dispositivos[0]["ultimo_estado"] == {} and c.dispositivos[0]["fuentes"] == []


def test_no_permite_duplicados(tmp_path):
    c = Config.cargar(tmp_path / "config.json")
    c.agregar_dispositivo("xeno", "Uno", "AA:BB:CC:DD:EE:FF")
    with pytest.raises(ValueError):
        c.agregar_dispositivo("xeno", "Dos", "aa:bb:cc:dd:ee:ff")


@pytest.mark.parametrize("nombre", ["", "   ", "\n\t"])
def test_nombre_vacio_falla(tmp_path, nombre):
    with pytest.raises(ValueError):
        Config.cargar(tmp_path / "c.json").agregar_dispositivo("xeno", nombre, "AA:BB:CC:DD:EE:FF")


def test_nombre_se_limpia_y_recorta(tmp_path):
    c = Config.cargar(tmp_path / "c.json")
    d = c.agregar_dispositivo("xeno", "  Sable   de\nObi-Wan " + "x" * 60, "AA:BB:CC:DD:EE:FF")
    assert d["nombre"].startswith("Sable de Obi-Wan x")
    assert len(d["nombre"]) == 40


def test_renombrar_y_quitar(tmp_path):
    c = Config.cargar(tmp_path / "c.json")
    d = c.agregar_dispositivo("xeno", "Uno", "AA:BB:CC:DD:EE:FF")
    c.renombrar(d["id"], "Otro")
    assert c.buscar(d["id"])["nombre"] == "Otro"
    with pytest.raises(KeyError):
        c.renombrar("no-existe", "X")
    c.quitar(d["id"])
    assert c.dispositivos == []


def test_cache_solo_guarda_claves_relevantes(tmp_path):
    c = Config.cargar(tmp_path / "c.json")
    d = c.agregar_dispositivo("xeno", "Uno", "AA:BB:CC:DD:EE:FF")
    c.actualizar_cache(d["id"], estado={"Volume": 30, "SwingSensitivity": 400}, fuentes=["A", "B"])
    assert c.buscar(d["id"])["ultimo_estado"] == {"Volume": 30}
    assert c.buscar(d["id"])["fuentes"] == ["A", "B"]
    c.actualizar_cache("no-existe", estado={"Volume": 1})  # no falla
