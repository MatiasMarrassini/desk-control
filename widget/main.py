"""Arranque de Desk Control: ventana, bandeja, atajo global y motor Bluetooth."""
import argparse
import logging
import logging.handlers
import threading
from pathlib import Path

import webview

from widget.bucle import BucleAsync
from widget.config import CARPETA, Config
from widget.dispositivos.sesion import SesionSable
from widget.dispositivos.transporte import TransporteBleak
from widget.escritorio import autoarranque
from widget.escritorio.atajo import AtajoGlobal, AtajoInvalido
from widget.escritorio.bandeja import crear_bandeja
from widget.escritorio.instancia import adquirir_instancia_unica
from widget.escritorio.ventana import (buscar_ventana, es_primer_plano, listar_areas_de_trabajo, posicion_inicial,
                                       redondear_esquinas, traer_al_frente)
from widget.puente import Puente

TITULO = "Desk Control"
UI = Path(__file__).resolve().parent / "ui" / "index.html"
ANCHO, ALTO = 380, 600
log = logging.getLogger("widget")


def url_interfaz() -> str:
    """Dirección file:// de la interfaz. Con una ruta común pywebview abriría un servidor HTTP local."""
    return UI.as_uri()


def configurar_registro(debug: bool) -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    manejador = logging.handlers.RotatingFileHandler(CARPETA / "widget.log", maxBytes=1_000_000,
                                                     backupCount=2, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, handlers=[manejador])


class ControlVentana:
    """Mostrar/ocultar. El atajo oculta solo si el widget ya está al frente; si está tapado, lo trae."""

    def __init__(self, ventana, visible: bool, al_ocultar=None):
        self.ventana = ventana
        self.visible = visible
        self.al_ocultar = al_ocultar or self.ocultar  # ocultar "completo" (p. ej. guardando la posición)
        self.saliendo = False  # lo activa "Salir" de la bandeja: solo entonces cerrar la ventana cierra el programa

    def al_cerrar(self, *_args) -> bool:
        """Manejador de `closing` de pywebview: devolver False cancela el cierre (Alt+F4 solo oculta)."""
        if self.saliendo:
            return True
        self.al_ocultar()
        return False

    def ajustar_estilo(self) -> None:
        # Al quitar los bordes, WinForms achica la ventana (380×600 → 364×561): se restaura el tamaño pedido.
        self.ventana.resize(ANCHO, ALTO)
        hwnd = buscar_ventana(TITULO)
        if hwnd:
            redondear_esquinas(hwnd)

    def mostrar(self) -> None:
        self.ventana.show()
        self.visible = True
        hwnd = buscar_ventana(TITULO)
        if hwnd:
            redondear_esquinas(hwnd)
            traer_al_frente(hwnd)

    def ocultar(self) -> None:
        self.ventana.hide()
        self.visible = False

    def alternar(self) -> None:
        hwnd = buscar_ventana(TITULO)
        if self.visible and hwnd and es_primer_plano(hwnd):
            self.al_ocultar()
        else:
            self.mostrar()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="desk-control")
    parser.add_argument("--oculto", action="store_true", help="arrancar oculto en la bandeja")
    parser.add_argument("--debug", action="store_true", help="registro detallado y herramientas de desarrollo")
    args = parser.parse_args(argv)

    instancia = adquirir_instancia_unica("Local\\DeskControl.Instancia")
    if instancia is None:
        return 0  # ya hay un Desk Control abierto
    configurar_registro(args.debug)
    log.info("Iniciando Desk Control")

    config = Config.cargar()
    if config.datos.get("autoarranque") and not autoarranque.esta_activo():
        autoarranque.activar()

    bucle = BucleAsync()
    bucle.iniciar()

    def crear_sesion(dispositivo: dict) -> SesionSable:
        return SesionSable(lambda: TransporteBleak(dispositivo["direccion"]),
                           estado_inicial=dispositivo.get("ultimo_estado"))

    puente = Puente(config, bucle, crear_sesion)

    posicion = config.datos["ventana"]
    x, y = posicion_inicial(posicion.get("x"), posicion.get("y"), listar_areas_de_trabajo())
    ventana = webview.create_window(TITULO, url_interfaz(), js_api=puente, width=ANCHO, height=ALTO, x=x, y=y,
                                    resizable=False, frameless=True, easy_drag=False, hidden=args.oculto,
                                    background_color="#1C1C20")
    control = ControlVentana(ventana, visible=not args.oculto)

    def guardar_posicion(*_args) -> None:
        if isinstance(ventana.x, int) and isinstance(ventana.y, int):
            config.datos["ventana"] = {"x": ventana.x, "y": ventana.y}

    def ocultar() -> None:
        guardar_posicion()
        control.ocultar()
        puente._guardar()

    control.al_ocultar = ocultar
    ventana.events.moved += guardar_posicion
    ventana.events.shown += lambda *_args: control.ajustar_estilo()
    ventana.events.closing += control.al_cerrar
    puente._conectar_ventana(ventana, al_ocultar=ocultar)

    atajo = None
    try:
        atajo = AtajoGlobal(config.datos.get("atajo", "ctrl+shift+space"), control.alternar)
        atajo_ok = atajo.iniciar()
    except AtajoInvalido:
        atajo, atajo_ok = None, False

    def cambiar_autoarranque() -> None:
        activo = not autoarranque.esta_activo()
        if activo:
            autoarranque.activar()
        else:
            autoarranque.desactivar()
        config.datos["autoarranque"] = activo
        puente._guardar()

    def salir() -> None:
        control.saliendo = True
        ventana.destroy()

    def agregar() -> None:
        control.mostrar()
        ventana.run_js("window.deskControl && window.deskControl.abrirBusqueda()")

    bandeja = crear_bandeja(al_alternar=control.alternar, al_agregar=agregar,
                            autoarranque_activo=autoarranque.esta_activo,
                            al_cambiar_autoarranque=cambiar_autoarranque, al_salir=salir)
    bandeja.run_detached()
    if not atajo_ok:
        aviso = f"El atajo «{config.datos.get('atajo')}» no está disponible. Cambialo en config.json."
        log.warning(aviso)
        threading.Timer(3, lambda: bandeja.notify(aviso, TITULO)).start()

    try:
        webview.start(debug=args.debug, private_mode=True)
    finally:
        log.info("Cerrando Desk Control")
        if atajo is not None:
            atajo.detener()
        bandeja.stop()
        try:
            bucle.ejecutar(puente._cerrar()).result(15)
        except Exception:
            log.exception("Error al cerrar las sesiones")
        puente._guardar()
        bucle.detener()
    return 0
