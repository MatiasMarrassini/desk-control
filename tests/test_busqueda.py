from widget.dispositivos.busqueda import es_xeno


def test_reconoce_servicios_xeno():
    assert es_xeno(["0000dae0-0000-1000-8000-00805f9b34fb"])
    assert es_xeno(["0000180F-0000-1000-8000-00805F9B34FB", "00003AB0-0000-1000-8000-00805F9B34FB"])


def test_rechaza_otros_dispositivos():
    assert not es_xeno([])
    assert not es_xeno(["0000fe9f-0000-1000-8000-00805f9b34fb"])
