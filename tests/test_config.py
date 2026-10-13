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


FOCOS = [{"mac": "444F8E000001", "ip": "192.168.1.6"}, {"mac": "444f8e000002", "ip": "192.168.1.7"}]


def test_agregar_grupo_wiz(tmp_path):
    c = Config.cargar(tmp_path / "c.json")
    g = c.agregar_grupo_wiz("Cuarto", "23013550", FOCOS)
    assert g["tipo"] == "wiz_grupo" and g["direccion"] == "WIZ:23013550"
    assert [f["nombre"] for f in g["focos"]] == ["Foco 1", "Foco 2"]
    assert g["focos"][0]["mac"] == "444f8e000001"  # MAC en minúsculas, como la reporta el foco
    assert g["favoritas"] == [12, 15, 16, 14, 4, 5, 1]
    with pytest.raises(ValueError):
        c.agregar_grupo_wiz("Otro", "23013550", FOCOS)
    with pytest.raises(ValueError):
        c.agregar_grupo_wiz("Vacío", "1", [])


def test_grupo_wiz_sobrevive_guardar_y_cargar(tmp_path):
    ruta = tmp_path / "c.json"
    c = Config.cargar(ruta)
    g = c.agregar_grupo_wiz("Cuarto", "23013550", FOCOS)
    c.guardar()
    assert Config.cargar(ruta).buscar(g["id"])["focos"][1]["ip"] == "192.168.1.7"


def test_config_corrupta_filtra_focos_invalidos(tmp_path):
    ruta = tmp_path / "c.json"
    grupo = {"id": "g1", "tipo": "wiz_grupo", "nombre": "Cuarto", "direccion": "WIZ:1",
             "focos": [{"mac": "aa", "ip": "1.2.3.4", "nombre": "A"}, {"mac": 5}, "x"], "favoritas": [12, 999, "x"]}
    vacio = {"id": "g2", "tipo": "wiz_grupo", "nombre": "Nada", "direccion": "WIZ:2", "focos": []}
    ruta.write_text(json.dumps({"dispositivos": [grupo, vacio]}), encoding="utf-8")
    c = Config.cargar(ruta)
    assert [d["id"] for d in c.dispositivos] == ["g1"]
    assert c.dispositivos[0]["focos"] == [{"mac": "aa", "ip": "1.2.3.4", "nombre": "A"}]
    assert c.dispositivos[0]["favoritas"] == [12]


def test_renombrar_foco_actualizar_ip_y_favoritas(tmp_path):
    c = Config.cargar(tmp_path / "c.json")
    g = c.agregar_grupo_wiz("Cuarto", "1", FOCOS)
    c.renombrar_foco(g["id"], "444f8e000002", "  Escritorio ")
    assert c.buscar(g["id"])["focos"][1]["nombre"] == "Escritorio"
    with pytest.raises(ValueError):
        c.renombrar_foco(g["id"], "444f8e000002", "   ")
    with pytest.raises(KeyError):
        c.renombrar_foco(g["id"], "ffffffffffff", "X")
    c.actualizar_ip(g["id"], "444f8e000001", "192.168.1.20")
    assert c.buscar(g["id"])["focos"][0]["ip"] == "192.168.1.20"
    c.poner_favoritas(g["id"], [4, 5])
    assert c.buscar(g["id"])["favoritas"] == [4, 5]
    for malas in ([1, 2, 3, 4, 5, 6, 7, 8], [999], [4, 4]):
        with pytest.raises(ValueError):
            c.poner_favoritas(g["id"], malas)


def test_cache_de_grupo_wiz_reemplaza_el_estado(tmp_path):
    c = Config.cargar(tmp_path / "c.json")
    g = c.agregar_grupo_wiz("Cuarto", "1", FOCOS)
    c.actualizar_cache(g["id"], estado={"state": True, "temp": 3000, "dimming": 50, "rssi": -70})
    c.actualizar_cache(g["id"], estado={"state": True, "sceneId": 4, "dimming": 50})
    assert c.buscar(g["id"])["ultimo_estado"] == {"state": True, "sceneId": 4, "dimming": 50}
