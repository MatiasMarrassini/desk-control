import threading

from widget.bucle import BucleAsync


def test_ejecuta_corrutinas_en_el_hilo_ble():
    bucle = BucleAsync()
    bucle.iniciar()

    async def nombre_del_hilo():
        return threading.current_thread().name

    assert bucle.ejecutar(nombre_del_hilo()).result(2) == "ble"
    bucle.detener()
    assert not bucle._hilo.is_alive()
