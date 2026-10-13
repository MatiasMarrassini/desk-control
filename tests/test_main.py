from webview.util import is_local_url

from widget import main


class VentanaFalsa:
    def __init__(self):
        self.ocultada = False

    def hide(self):
        self.ocultada = True


def test_cerrar_la_ventana_la_oculta_en_vez_de_salir():
    # Alt+F4 (o cualquier cierre que no venga de "Salir") solo oculta el widget.
    ocultas = []
    control = main.ControlVentana(VentanaFalsa(), visible=True, al_ocultar=lambda: ocultas.append(True))
    assert control.al_cerrar() is False  # False cancela el cierre en pywebview
    assert ocultas == [True]


def test_salir_desde_la_bandeja_si_cierra():
    control = main.ControlVentana(VentanaFalsa(), visible=True, al_ocultar=lambda: None)
    control.saliendo = True
    assert control.al_cerrar() is True


def test_la_interfaz_se_carga_sin_servidor_http():
    # pywebview levanta un servidor HTTP local para rutas "locales"; con file:// no abre ningún puerto.
    url = main.url_interfaz()
    assert url.startswith("file:///") and url.endswith("/widget/ui/index.html")
    assert is_local_url(url) is False


class VentanaQueSeMuestra(VentanaFalsa):
    def show(self):
        pass


def test_mostrar_y_ocultar_avisan_la_visibilidad():
    cambios = []
    control = main.ControlVentana(VentanaQueSeMuestra(), visible=True, al_visibilidad=cambios.append)
    control.ocultar()
    control.mostrar()
    assert cambios == [False, True]


def test_cerrar_oculta_aunque_falle_el_aviso():
    # Si ocultar falla (p. ej. el bucle no contesta a tiempo), Alt+F4 igual NO cierra el programa.
    def falla():
        raise TimeoutError
    control = main.ControlVentana(VentanaFalsa(), visible=True, al_ocultar=falla)
    assert control.al_cerrar() is False


def test_ocultar_y_mostrar_piden_el_nivel_de_memoria():
    # Oculta, WebView2 recorta memoria; al volver a mostrarse recupera el nivel normal (antes del show).
    pedidos = []
    ventana = VentanaQueSeMuestra()
    control = main.ControlVentana(ventana, visible=True, memoria_baja=lambda v, baja: pedidos.append((v, baja)))
    control.ocultar()
    control.mostrar()
    assert pedidos == [(ventana, True), (ventana, False)]


def test_falla_del_nivel_de_memoria_no_impide_ocultar_ni_mostrar():
    def falla(_ventana, _baja):
        raise RuntimeError("WebView2 no responde")
    cambios = []
    ventana = VentanaQueSeMuestra()
    control = main.ControlVentana(ventana, visible=True, al_visibilidad=cambios.append, memoria_baja=falla)
    assert control.al_cerrar() is False  # Alt+F4 sigue sin cerrar el programa
    assert ventana.ocultada and control.visible is False
    control.mostrar()
    assert control.visible is True and cambios == [False, True]


def test_nivel_de_memoria_sin_webview2_no_hace_nada():
    # Antes de que pywebview cree el formulario (o con otro motor) no hay control .NET que tocar.
    main.fijar_memoria_baja(VentanaFalsa(), True)
