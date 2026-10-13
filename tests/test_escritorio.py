import uuid
import winreg

import pytest

from widget.escritorio import atajo, autoarranque, bandeja, instancia, ventana

CLAVE_PRUEBA = r"Software\DeskControl\Pruebas"


def test_interpretar_atajo_por_defecto():
    assert atajo.interpretar("ctrl+shift+space") == (0x0002 | 0x0004 | 0x4000, 0x20)


def test_interpretar_mayusculas_y_espacios():
    assert atajo.interpretar(" Ctrl + Alt + X ") == (0x0002 | 0x0001 | 0x4000, ord("X"))
    assert atajo.interpretar("win+f12") == (0x0008 | 0x4000, 0x7B)


@pytest.mark.parametrize("texto", ["space", "ctrl+", "hyper+x", "ctrl+ctrl+x", "ctrl+ñ", "ctrl+shift+abc", ""])
def test_interpretar_invalidos(texto):
    with pytest.raises(atajo.AtajoInvalido):
        atajo.interpretar(texto)


def test_atajo_ocupado_no_se_registra():
    primero = atajo.AtajoGlobal("ctrl+alt+shift+f11", lambda: None)
    segundo = atajo.AtajoGlobal("ctrl+alt+shift+f11", lambda: None)
    try:
        assert primero.iniciar() is True
        assert segundo.iniciar() is False
    finally:
        primero.detener()
        segundo.detener()


def test_segunda_instancia_rechazada():
    nombre = f"Local\\DeskControl.Prueba-{uuid.uuid4().hex}"
    primera = instancia.adquirir_instancia_unica(nombre)
    assert primera
    assert instancia.adquirir_instancia_unica(nombre) is None
    instancia.liberar(primera)
    tercera = instancia.adquirir_instancia_unica(nombre)
    assert tercera
    instancia.liberar(tercera)


def test_autoarranque_activar_y_desactivar():
    try:
        assert autoarranque.esta_activo(CLAVE_PRUEBA, "Prueba") is False
        autoarranque.activar(CLAVE_PRUEBA, "Prueba")
        assert autoarranque.esta_activo(CLAVE_PRUEBA, "Prueba") is True
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, CLAVE_PRUEBA) as k:  # proyecto movido de carpeta
            winreg.SetValueEx(k, "Prueba", 0, winreg.REG_SZ, '"C:\\viejo\\pythonw.exe" x')
        assert autoarranque.esta_activo(CLAVE_PRUEBA, "Prueba") is False
        autoarranque.desactivar(CLAVE_PRUEBA, "Prueba")
        assert autoarranque.esta_activo(CLAVE_PRUEBA, "Prueba") is False
        autoarranque.desactivar(CLAVE_PRUEBA, "Prueba")  # dos veces no falla
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, CLAVE_PRUEBA)
        except OSError:
            pass


def test_comando_de_autoarranque_usa_pythonw_y_oculto():
    c = autoarranque.comando()
    assert "pythonw.exe" in c and c.endswith('desk_control.pyw" --oculto')


def test_elegir_posicion_prefiere_monitor_vertical():
    horizontal = (0, 0, 1920, 1040)
    vertical = (-1080, -400, 0, 1480)
    assert ventana.elegir_posicion([horizontal, vertical]) == (-1068, -388)
    assert ventana.elegir_posicion([horizontal]) == (12, 12)
    assert ventana.elegir_posicion([]) == (12, 12)


def test_posicion_guardada_se_usa_si_esta_en_pantalla():
    areas = [(0, 0, 1920, 1040), (-1080, -400, 0, 1480)]
    assert ventana.posicion_inicial(-900, 100, areas) == (-900, 100)


def test_posicion_guardada_fuera_de_pantalla_vuelve_a_la_de_defecto():
    # Se desconectó el monitor vertical: la posición guardada quedó fuera de toda pantalla.
    areas = [(0, 0, 1920, 1040)]
    assert ventana.posicion_inicial(-900, 100, areas) == (12, 12)
    assert ventana.posicion_inicial(None, None, areas) == (12, 12)


def test_listar_areas_de_trabajo_real():
    areas = ventana.listar_areas_de_trabajo()
    assert areas and all(len(a) == 4 for a in areas)


def test_icono_de_bandeja():
    img = bandeja.crear_icono()
    assert img.size == (64, 64) and img.mode == "RGBA"
    assert img.getbbox() is not None  # tiene algo dibujado


def test_menu_de_bandeja():
    icono = bandeja.crear_bandeja(al_alternar=lambda: None, al_agregar=lambda: None,
                                  autoarranque_activo=lambda: True, al_cambiar_autoarranque=lambda: None,
                                  al_salir=lambda: None)
    textos = [item.text for item in icono.menu.items]
    assert "Mostrar / ocultar" in textos and "Agregar dispositivo" in textos and "Salir" in textos
