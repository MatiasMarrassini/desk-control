# Desk Control — etapa 1 (sable Xeno3): plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un widget de escritorio para Windows (ventana sin bordes, bandeja, atajo global) que controla el sable Xeno3 por Bluetooth: encendido, color, volumen, brillo, fuentes y batería.

**Architecture:** Un solo proceso Python. pywebview (WebView2) dibuja la interfaz HTML/CSS/JS en el hilo principal. Un hilo aparte corre un bucle `asyncio` con `bleak` para el Bluetooth. Un objeto `Puente` es la única API que ve JavaScript: recibe llamadas y devuelve eventos con `window.run_js`. El protocolo, la conexión a demanda y la configuración son módulos puros que se prueban con un sable simulado.

**Tech Stack:** Python 3.12 · bleak 3.0.2 · pywebview 6.2.1 · pystray 0.19.5 · Pillow 12.3.0 · pytest 9.1.1 + pytest-asyncio 1.4.0 · HTML/CSS/JS sin frameworks.

**Spec:** `docs/superpowers/specs/2026-10-12-widget-sable-design.md` (léelo junto con `PROTOCOLO.md`).

## Global Constraints

- Plataforma: Windows 11, Python 3.12, entorno virtual en `.venv/` (ya ignorado por git). Todos los comandos se ejecutan desde la raíz del proyecto con `.venv/Scripts/python`.
- Dependencias fijadas exactamente: `bleak==3.0.2`, `pywebview==6.2.1`, `pystray==0.19.5`, `Pillow==12.3.0`; desarrollo: `pytest==9.1.1`, `pytest-asyncio==1.4.0`. No agregar otras.
- **Sin red:** no abrir sockets ni servidores. Nunca pasar `http_server=True` a pywebview. La UI solo carga archivos locales de `widget/ui/`; no usar CDN ni recursos remotos.
- **Comandos permitidos al sable**, solo estos: `PowerOn`, `Volume`, `Brightness`, `BackgroundColor`, `CurrentSoundPackageNo`, `ls`, `fontname` (más el handshake y la autorización internos). `Reset`, `HardwareType`, `SoftwareType`, `ButtonNum`, `FileTransfer`, `rm`, `cp` y `setname` no deben poder enviarse.
- **Texto que viene del sable o del usuario** (nombres de fuentes y de dispositivos) se inserta en el DOM solo con `textContent`, nunca con `innerHTML`.
- Configuración en `%APPDATA%\DeskControl\config.json` y registro en `%APPDATA%\DeskControl\widget.log`.
- Ventana: título `Desk Control`, 380×600 px, sin bordes, no redimensionable, fondo `#1C1C20`, esquinas redondeadas (DWM).
- Atajo por defecto: `ctrl+shift+space`. Arranque con Windows activado por defecto y oculto (`--oculto`).
- Tiempos: 3 intentos de conexión con 2 s entre intentos; búsqueda del dispositivo 10 s; conexión 40 s; respuesta del sable 5 s; desconexión por inactividad a los 60 s; envío de deslizadores cada 150 ms como máximo.
- Batería baja: `Power` menor que 20 **con la hoja apagada** (con la hoja encendida la lectura no es fiable).
- `CurrentSoundPackageNo` cuenta desde 0 y las carpetas de fuentes desde 1. La UI muestra los números desde 1.
- Textos de la interfaz en español rioplatense (voseo), como en las maquetas.
- Consumo objetivo: menos de 200 MB de RAM en total (Python más WebView2) y alrededor de 0 % de CPU en reposo.
- Commits en español, terminados con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, seguidos de `git push`.

## Review Focus

1. **Texto hostil del sable o del usuario** (un nombre de fuente o de dispositivo con `<b>`, comillas o `\u2028`): debe verse literal y no romper los eventos Python→JS. Lo cubre el test `test_emitir_codifica_texto_raro` (tarea 6) y el uso exclusivo de `textContent` (tareas 8 y 9).
2. **Corte de conexión con órdenes en cola o a mitad de un envío:** aviso de error, estado "en espera" y la próxima orden reconecta. Lo cubre `test_corte_durante_envio_avisa_y_reconecta` (tarea 3).
3. **Deslizador arrastrado muy rápido** (decenas de valores): solo viaja el último valor, sin cola acumulada. Lo cubren `test_ordenes_repetidas_se_coalescen` (tarea 3) y `util.limitar` (tarea 8).
4. **`config.json` corrupto o editado a mano** (JSON inválido, tipos incorrectos, dispositivos incompletos): arranca con valores por defecto o filtra lo inválido y guarda una copia del archivo malo. Lo cubren `test_config_corrupta_*` (tarea 4).
5. **Dos instancias a la vez** (autoarranque más doble clic) **o el atajo tomado por otro programa:** la segunda instancia sale sin duplicar bandeja ni atajo, y un atajo ocupado se informa en lugar de fallar en silencio. Lo cubren `test_segunda_instancia_rechazada` y `test_atajo_ocupado_no_se_registra` (tarea 7).

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `requirements.txt`, `requirements-dev.txt`, `pytest.ini` | Dependencias y configuración de pruebas |
| `desk_control.pyw` | Lanzador sin consola (lo usa el arranque con Windows) |
| `widget/__main__.py` | `python -m widget` |
| `widget/main.py` | Arma todo: registro, config, bucle, puente, ventana, bandeja, atajo |
| `widget/bucle.py` | Hilo con el bucle `asyncio` del Bluetooth |
| `widget/puente.py` | API para JavaScript y eventos hacia la ventana |
| `widget/config.py` | `config.json`: dispositivos guardados, caché de estado y fuentes, posición |
| `widget/diagnostico.py` | Prueba manual del motor con el sable real |
| `widget/dispositivos/protocolo.py` | Mensajes Xeno3: UUIDs, validación, armado y ensamblado |
| `widget/dispositivos/transporte.py` | Interfaz `Transporte` + `TransporteBleak` (real) |
| `widget/dispositivos/xeno.py` | `SableXeno`: handshake, autorización, envío, estado, fuentes |
| `widget/dispositivos/sesion.py` | `SesionSable`: conexión a demanda, cola, reintentos, inactividad |
| `widget/dispositivos/busqueda.py` | Búsqueda de placas Xeno3 cercanas |
| `widget/escritorio/atajo.py` | Atajo global con `RegisterHotKey` |
| `widget/escritorio/instancia.py` | Instancia única (mutex con nombre) |
| `widget/escritorio/autoarranque.py` | Valor `Run` en `HKCU` |
| `widget/escritorio/ventana.py` | Monitor vertical, esquinas redondeadas, primer plano |
| `widget/escritorio/bandeja.py` | Icono y menú de la bandeja |
| `widget/ui/index.html`, `estilos.css`, `util.js`, `app.js`, `busqueda.js` | Interfaz base y pantalla de búsqueda |
| `widget/ui/sable.css`, `sable.js`, `rueda.js` | Panel del sable |
| `tests/sable_simulado.py`, `tests/ayudas.py`, `tests/test_*.py` | Pruebas |
| `scripts/medir_consumo.ps1` | Medición de RAM y CPU |

---

### Task 1: Base del proyecto y protocolo Xeno3

**Files:**
- Create: `requirements.txt`, `requirements-dev.txt`, `pytest.ini`
- Create: `widget/__init__.py`, `widget/dispositivos/__init__.py`, `widget/escritorio/__init__.py`, `tests/__init__.py`
- Create: `widget/dispositivos/protocolo.py`
- Test: `tests/test_protocolo.py`

**Interfaces:**
- Consumes: nada.
- Produces: módulo `widget.dispositivos.protocolo` con `SERVICIOS_XENO: frozenset[str]`, `CAR_HANDSHAKE: str`, `CAR_DATOS: str`, `MENSAJE_HANDSHAKE: bytes`, `MENSAJE_AUTORIZAR: bytes`, `TIPO_COMANDO = 2`, `TIPO_RESPUESTA = 3`, `TIPO_ERROR = 4`, `CLAVES_PERMITIDAS: frozenset[str]`, `class ComandoInvalido(ValueError)`, `validar(clave: str, valor) -> None`, `armar(clave: str, valor) -> bytes`, `class Ensamblador` con `agregar(datos: bytes) -> list[tuple[int, dict]]`.

- [ ] **Step 1: Crear archivos de dependencias, pytest y entorno**

`requirements.txt`:
```
bleak==3.0.2
pywebview==6.2.1
pystray==0.19.5
Pillow==12.3.0
```

`requirements-dev.txt`:
```
-r requirements.txt
pytest==9.1.1
pytest-asyncio==1.4.0
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = .
asyncio_mode = auto
asyncio_default_fixture_loop_scope = function
```

Crear vacíos `widget/__init__.py`, `widget/dispositivos/__init__.py`, `widget/escritorio/__init__.py` y `tests/__init__.py`.

Run:
```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
```
Expected: termina con `Successfully installed ...`, sin errores.

- [ ] **Step 2: Escribir las pruebas del protocolo (fallan)**

`tests/test_protocolo.py`:
```python
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
```

- [ ] **Step 3: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python -m pytest tests/test_protocolo.py -v`
Expected: FAIL / ERROR con `ModuleNotFoundError: No module named 'widget.dispositivos.protocolo'`.

- [ ] **Step 4: Implementar el protocolo**

`widget/dispositivos/protocolo.py`:
```python
"""Protocolo BLE de las placas Xeno3 (ver PROTOCOLO.md).

Los mensajes son JSON en UTF-8 con la forma [tipo, {clave: valor}]:
2 = comando (app -> sable), 3 = respuesta/estado (sable -> app), 4 = error (sable -> app).
"""
import json
import re

SERVICIOS_XENO = frozenset({
    "0000dae0-0000-1000-8000-00805f9b34fb",
    "00003ab0-0000-1000-8000-00805f9b34fb",
})
CAR_HANDSHAKE = "0000dae1-0000-1000-8000-00805f9b34fb"
CAR_DATOS = "00003ab1-0000-1000-8000-00805f9b34fb"

MENSAJE_HANDSHAKE = b'[2,{"HandShake":"HelloDamien"}]'
MENSAJE_AUTORIZAR = b'[2,{"Authorize":"SaberOfDamien"}]'

TIPO_COMANDO = 2
TIPO_RESPUESTA = 3
TIPO_ERROR = 4

_MAX_BUFFER = 4096
_RUTA_FUENTE = re.compile(r"^/\d{1,3}$")


class ComandoInvalido(ValueError):
    """El comando no está permitido o su valor no es válido."""


def _entero(valor, minimo: int, maximo: int) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool) and minimo <= valor <= maximo


# Lista blanca: cualquier clave que no esté acá no se puede enviar (Reset, firmware, rm, etc.).
_VALIDADORES = {
    "PowerOn": lambda v: isinstance(v, bool),
    "Volume": lambda v: _entero(v, 0, 100),
    "Brightness": lambda v: _entero(v, 0, 100),
    "BackgroundColor": lambda v: isinstance(v, list) and len(v) == 3 and all(_entero(c, 0, 255) for c in v),
    "CurrentSoundPackageNo": lambda v: _entero(v, 0, 999),
    "ls": lambda v: v == "/",
    "fontname": lambda v: isinstance(v, str) and bool(_RUTA_FUENTE.match(v)),
}
CLAVES_PERMITIDAS = frozenset(_VALIDADORES)


def validar(clave: str, valor) -> None:
    """Lanza ComandoInvalido si la clave no está permitida o el valor no es válido."""
    if clave not in _VALIDADORES:
        raise ComandoInvalido(f"Comando no permitido: {clave}")
    if not _VALIDADORES[clave](valor):
        raise ComandoInvalido(f"Valor inválido para {clave}: {valor!r}")


def armar(clave: str, valor) -> bytes:
    """Arma el comando [2,{clave:valor}] listo para escribir en la característica de datos."""
    validar(clave, valor)
    return json.dumps([TIPO_COMANDO, {clave: valor}], separators=(",", ":")).encode("utf-8")


class Ensamblador:
    """Junta notificaciones BLE hasta formar un mensaje JSON completo [tipo, {...}]."""

    def __init__(self):
        self._buffer = b""

    def agregar(self, datos: bytes) -> list[tuple[int, dict]]:
        self._buffer += bytes(datos)
        try:
            mensaje = json.loads(self._buffer.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            if len(self._buffer) > _MAX_BUFFER:
                self._buffer = b""
            return []
        self._buffer = b""
        if (isinstance(mensaje, list) and len(mensaje) == 2
                and isinstance(mensaje[0], int) and isinstance(mensaje[1], dict)):
            return [(mensaje[0], mensaje[1])]
        return []
```

- [ ] **Step 5: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python -m pytest tests/test_protocolo.py -v`
Expected: PASS (todas).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt pytest.ini widget tests
git commit -m "Base del widget y protocolo Xeno3 con lista blanca de comandos" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 2: Transporte, sable simulado y controlador `SableXeno`

**Files:**
- Create: `widget/dispositivos/transporte.py`
- Create: `widget/dispositivos/xeno.py`
- Create: `tests/sable_simulado.py`, `tests/ayudas.py`
- Test: `tests/test_xeno.py`

**Interfaces:**
- Consumes: `widget.dispositivos.protocolo` (tarea 1).
- Produces:
  - `widget.dispositivos.transporte`: `class SableNoEncontrado(Exception)`; `class Transporte(Protocol)` con `al_desconectar: Callable[[], None] | None`, propiedad `conectado -> bool`, `async conectar()`, `async desconectar()`, `async suscribir(uuid: str, callback: Callable[[bytes], None])`, `async escribir(uuid: str, datos: bytes, con_respuesta: bool)` y `async leer(uuid: str) -> bytes`; `class TransporteBleak(direccion: str, timeout_busqueda: float = 10.0, timeout_conexion: float = 40.0)`, que implementa `Transporte`.
  - `widget.dispositivos.xeno`: `class ErrorProtocolo(Exception)`; `class SableXeno(transporte: Transporte, timeout_respuesta: float = 5.0)` con atributos `transporte`, `estado: dict`, `al_cambiar: Callable[[dict], None] | None` y `al_error: Callable[[str, str], None] | None`, y métodos `async conectar()`, `async enviar(clave, valor)`, `async listar_fuentes() -> list[str]` y `async desconectar()`.
  - `tests/sable_simulado.py`: `FUENTES: list[str]`, `class SableSimulado(**opciones)`, que implementa `Transporte` y tiene `comandos() -> list[dict]` y `simular_corte()`.
  - `tests/ayudas.py`: `async esperar_hasta(condicion, segundos=2.0)` y `esperar_sync(condicion, segundos=3.0)`.

- [ ] **Step 1: Escribir la interfaz de transporte y la implementación real**

`widget/dispositivos/transporte.py`:
```python
"""Transporte BLE: interfaz común (para poder simular el sable en pruebas) e implementación real con bleak."""
import asyncio
from typing import Callable, Protocol

from bleak import BleakClient, BleakScanner


class SableNoEncontrado(Exception):
    """El sable no apareció al buscarlo (apagado, lejos o conectado a otro dispositivo)."""


class Transporte(Protocol):
    al_desconectar: Callable[[], None] | None

    @property
    def conectado(self) -> bool: ...

    async def conectar(self) -> None: ...

    async def desconectar(self) -> None: ...

    async def suscribir(self, uuid: str, callback: Callable[[bytes], None]) -> None: ...

    async def escribir(self, uuid: str, datos: bytes, con_respuesta: bool) -> None: ...

    async def leer(self, uuid: str) -> bytes: ...


class TransporteBleak:
    """Conexión real por Bluetooth con bleak. `al_desconectar` se llama en el hilo del bucle asyncio."""

    def __init__(self, direccion: str, timeout_busqueda: float = 10.0, timeout_conexion: float = 40.0):
        self.direccion = direccion
        self.al_desconectar: Callable[[], None] | None = None
        self._timeout_busqueda = timeout_busqueda
        self._timeout_conexion = timeout_conexion
        self._cliente: BleakClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def conectado(self) -> bool:
        return self._cliente is not None and self._cliente.is_connected

    async def conectar(self) -> None:
        self._loop = asyncio.get_running_loop()
        dispositivo = await BleakScanner.find_device_by_address(self.direccion, timeout=self._timeout_busqueda)
        if dispositivo is None:
            raise SableNoEncontrado(self.direccion)
        self._cliente = BleakClient(dispositivo, disconnected_callback=self._al_corte, timeout=self._timeout_conexion)
        await self._cliente.connect()

    def _al_corte(self, _cliente) -> None:
        if self.al_desconectar is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self.al_desconectar)

    async def desconectar(self) -> None:
        if self._cliente is not None and self._cliente.is_connected:
            await self._cliente.disconnect()

    async def suscribir(self, uuid: str, callback: Callable[[bytes], None]) -> None:
        await self._cliente.start_notify(uuid, lambda _car, datos: callback(bytes(datos)))

    async def escribir(self, uuid: str, datos: bytes, con_respuesta: bool) -> None:
        await self._cliente.write_gatt_char(uuid, datos, response=con_respuesta)

    async def leer(self, uuid: str) -> bytes:
        return bytes(await self._cliente.read_gatt_char(uuid))
```

- [ ] **Step 2: Escribir el sable simulado y las ayudas de prueba**

`tests/sable_simulado.py`:
```python
"""Sable falso que implementa Transporte y responde como el real (según los logs de las pruebas manuales)."""
import asyncio
import json

from bleak.exc import BleakBluetoothNotAvailableError, BleakBluetoothNotAvailableReason

from widget.dispositivos import protocolo as p
from widget.dispositivos.transporte import SableNoEncontrado

FUENTES = ["The Chosen", "New Horizon", "The Princess"]
COLORES_POR_FUENTE = [[255, 0, 0], [0, 80, 255], [0, 255, 0]]


def estado_inicial() -> dict:
    return {
        "HardwareVersion": "XENOA000000000000", "SoftwareVersion": "DMN_XENO_B_SV1.4.0",
        "PowerOn": False, "CurrentSoundPackageNo": 2, "TotalSoundPackage": 3, "Power": 77,
        "Volume": 20, "BackgroundColor": [0, 255, 0], "Brightness": 100, "fontname": "The Princess",
    }


class SableSimulado:
    def __init__(self, *, fallos_conexion=0, sin_bluetooth=False, responde_saludo=True, autoriza=True,
                 autoriza_por_notificacion=True, errores=None, corta_en=None):
        self.al_desconectar = None
        self.estado = estado_inicial()
        self.fuentes = list(FUENTES)
        self.escrituras: list[tuple[str, bytes]] = []
        self.conexiones = 0
        self.fallos_conexion = fallos_conexion
        self.sin_bluetooth = sin_bluetooth
        self.responde_saludo = responde_saludo
        self.autoriza = autoriza
        self.autoriza_por_notificacion = autoriza_por_notificacion
        self.errores = errores or {}
        self.corta_en = corta_en
        self._conectado = False
        self._callbacks = {}

    @property
    def conectado(self) -> bool:
        return self._conectado

    async def conectar(self):
        if self.sin_bluetooth:
            raise BleakBluetoothNotAvailableError("Bluetooth apagado", BleakBluetoothNotAvailableReason.POWERED_OFF)
        if self.fallos_conexion > 0:
            self.fallos_conexion -= 1
            raise SableNoEncontrado("simulado")
        self.conexiones += 1
        self._conectado = True

    async def desconectar(self):
        if self._conectado:
            self._conectado = False
            if self.al_desconectar:  # bleak también avisa en las desconexiones pedidas
                self.al_desconectar()

    def simular_corte(self):
        self._conectado = False
        if self.al_desconectar:
            self.al_desconectar()

    async def suscribir(self, uuid, callback):
        self._callbacks[uuid] = callback

    async def leer(self, uuid):
        valor = "AccessAllowed" if self.autoriza else "AccessDenied"
        return json.dumps([3, {"Authorize": valor}]).encode()

    async def escribir(self, uuid, datos, con_respuesta):
        if not self._conectado:
            raise ConnectionError("no conectado")
        self.escrituras.append((uuid, bytes(datos)))
        _, cuerpo = json.loads(datos)
        (clave, valor), = cuerpo.items()
        if clave == self.corta_en:
            self.simular_corte()
            raise ConnectionError("corte simulado")
        if clave == "HandShake":
            if self.responde_saludo:
                partes = list(self.estado.items())
                for i in range(0, len(partes), 4):
                    self._notificar(p.CAR_HANDSHAKE, dict(partes[i:i + 4]))
                self._notificar(p.CAR_HANDSHAKE, {"HandShake": "OK"})
        elif clave == "Authorize":
            if self.autoriza and self.autoriza_por_notificacion:
                self._notificar(p.CAR_DATOS, {"Authorize": "AccessAllowed"})
        elif clave in self.errores:
            self._notificar(p.CAR_DATOS, {clave: self.errores[clave]}, tipo=p.TIPO_ERROR)
        elif clave == "ls":
            self._notificar(p.CAR_DATOS, {"ls": [1, len(self.fuentes)]})
        elif clave == "fontname":
            self._notificar(p.CAR_DATOS, {"fontname": [valor, self.fuentes[int(valor[1:]) - 1]]})
        elif clave == "CurrentSoundPackageNo":
            cambios = {"CurrentSoundPackageNo": valor, "fontname": self.fuentes[valor],
                       "BackgroundColor": COLORES_POR_FUENTE[valor]}
            self.estado.update(cambios)
            self._notificar(p.CAR_HANDSHAKE, cambios)
        else:
            self.estado[clave] = valor
            self._notificar(p.CAR_HANDSHAKE, {clave: valor})

    def _notificar(self, uuid, cuerpo, tipo=p.TIPO_RESPUESTA):
        datos = json.dumps([tipo, cuerpo], separators=(",", ":")).encode()
        callback = self._callbacks.get(uuid)
        if callback:
            asyncio.get_running_loop().call_soon(callback, datos)

    def comandos(self) -> list[dict]:
        """Comandos enviados por el canal de datos, sin contar la autorización."""
        return [json.loads(d)[1] for u, d in self.escrituras if u == p.CAR_DATOS and b"Authorize" not in d]
```

`tests/ayudas.py`:
```python
import asyncio
import time


async def esperar_hasta(condicion, segundos: float = 2.0):
    fin = asyncio.get_running_loop().time() + segundos
    while not condicion():
        if asyncio.get_running_loop().time() > fin:
            raise AssertionError("La condición no se cumplió a tiempo")
        await asyncio.sleep(0.01)


def esperar_sync(condicion, segundos: float = 3.0):
    fin = time.monotonic() + segundos
    while not condicion():
        if time.monotonic() > fin:
            raise AssertionError("La condición no se cumplió a tiempo")
        time.sleep(0.02)
```

- [ ] **Step 3: Escribir las pruebas de `SableXeno` (fallan)**

`tests/test_xeno.py`:
```python
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
```

- [ ] **Step 4: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python -m pytest tests/test_xeno.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'widget.dispositivos.xeno'`.

- [ ] **Step 5: Implementar `SableXeno`**

`widget/dispositivos/xeno.py`:
```python
"""Controlador de una placa Xeno3 sobre un Transporte (protocolo en PROTOCOLO.md)."""
import asyncio
import json
from typing import Callable

from widget.dispositivos import protocolo as p
from widget.dispositivos.transporte import Transporte


class ErrorProtocolo(Exception):
    """El sable no respondió como indica el protocolo."""


def _es_respuesta_de_archivos(clave: str, valor) -> bool:
    # ls y fontname con la forma ["/N","Nombre"] responden a consultas de archivos: no son estado del sable.
    return clave == "ls" or (clave == "fontname" and isinstance(valor, list))


class SableXeno:
    def __init__(self, transporte: Transporte, timeout_respuesta: float = 5.0):
        self.transporte = transporte
        self.estado: dict = {}
        self.al_cambiar: Callable[[dict], None] | None = None
        self.al_error: Callable[[str, str], None] | None = None
        self._timeout = timeout_respuesta
        self._esperas: dict[str, list[asyncio.Future]] = {}
        self._ensambladores = {p.CAR_HANDSHAKE: p.Ensamblador(), p.CAR_DATOS: p.Ensamblador()}

    async def conectar(self) -> None:
        """Conecta, saluda (el sable responde con todo su estado) y pide autorización."""
        t = self.transporte
        await t.conectar()
        await t.suscribir(p.CAR_HANDSHAKE, self._receptor(p.CAR_HANDSHAKE))
        saludo = self._esperar("HandShake")
        await t.escribir(p.CAR_HANDSHAKE, p.MENSAJE_HANDSHAKE, True)
        try:
            await asyncio.wait_for(saludo, self._timeout)
        except asyncio.TimeoutError:
            raise ErrorProtocolo("El sable no respondió al saludo") from None

        await t.suscribir(p.CAR_DATOS, self._receptor(p.CAR_DATOS))
        permiso = self._esperar("Authorize")
        await t.escribir(p.CAR_DATOS, p.MENSAJE_AUTORIZAR, False)
        try:
            valor = await asyncio.wait_for(permiso, self._timeout)
        except asyncio.TimeoutError:
            valor = self._autorizacion_leida(await t.leer(p.CAR_DATOS))
        if valor != "AccessAllowed":
            raise ErrorProtocolo(f"Autorización rechazada: {valor!r}")

    @staticmethod
    def _autorizacion_leida(datos: bytes):
        try:
            tipo, cuerpo = json.loads(datos.decode("utf-8"))
            return cuerpo.get("Authorize") if tipo == p.TIPO_RESPUESTA else None
        except (ValueError, TypeError, AttributeError):
            return None

    async def enviar(self, clave: str, valor) -> None:
        """Envía [2,{clave:valor}]. La confirmación llega después como cambio de estado."""
        await self.transporte.escribir(p.CAR_DATOS, p.armar(clave, valor), False)

    async def listar_fuentes(self) -> list[str]:
        """Nombres de las fuentes en orden de carpeta (índice 0 = carpeta 1). Solo lectura."""
        rango = await self._consultar("ls", "/")
        if not (isinstance(rango, list) and len(rango) >= 2 and all(isinstance(n, int) for n in rango)):
            return []
        nombres = []
        for n in range(rango[0], rango[-1] + 1):
            valor = await self._consultar("fontname", f"/{n}")
            valido = isinstance(valor, list) and len(valor) > 1 and isinstance(valor[1], str)
            nombres.append(valor[1] if valido else f"Fuente {n}")
        return nombres

    async def desconectar(self) -> None:
        for esperas in self._esperas.values():
            for futuro in esperas:
                if not futuro.done():
                    futuro.cancel()
        self._esperas.clear()
        await self.transporte.desconectar()

    async def _consultar(self, clave: str, valor):
        espera = self._esperar(clave)
        await self.enviar(clave, valor)
        try:
            return await asyncio.wait_for(espera, self._timeout)
        except asyncio.TimeoutError:
            raise ErrorProtocolo(f"Sin respuesta a {clave}") from None

    def _esperar(self, clave: str) -> asyncio.Future:
        futuro = asyncio.get_running_loop().create_future()
        self._esperas.setdefault(clave, []).append(futuro)
        return futuro

    def _resolver(self, clave: str, valor) -> None:
        for futuro in self._esperas.pop(clave, []):
            if not futuro.done():
                futuro.set_result(valor)

    def _receptor(self, uuid: str) -> Callable[[bytes], None]:
        def recibir(datos: bytes) -> None:
            for tipo, cuerpo in self._ensambladores[uuid].agregar(datos):
                self._procesar(tipo, cuerpo)
        return recibir

    def _procesar(self, tipo: int, cuerpo: dict) -> None:
        if tipo == p.TIPO_ERROR:
            for clave, mensaje in cuerpo.items():
                self._resolver(clave, None)
                if self.al_error:
                    self.al_error(clave, str(mensaje))
            return
        if tipo != p.TIPO_RESPUESTA:
            return
        cambios = {k: v for k, v in cuerpo.items() if not _es_respuesta_de_archivos(k, v)}
        self.estado.update(cambios)
        for clave, valor in cuerpo.items():
            self._resolver(clave, valor)
        if cambios and self.al_cambiar:
            self.al_cambiar(cambios)
```

- [ ] **Step 6: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python -m pytest tests/test_xeno.py tests/test_protocolo.py -v`
Expected: PASS (todas).

- [ ] **Step 7: Commit**

```bash
git add widget/dispositivos/transporte.py widget/dispositivos/xeno.py tests/sable_simulado.py tests/ayudas.py tests/test_xeno.py
git commit -m "Controlador SableXeno, transporte bleak y sable simulado para pruebas" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 3: Conexión a demanda (`SesionSable`)

**Files:**
- Create: `widget/dispositivos/sesion.py`
- Test: `tests/test_sesion.py`

**Interfaces:**
- Consumes: `SableXeno`, `ErrorProtocolo` (tarea 2), `Transporte`, `SableNoEncontrado` (tarea 2), `protocolo.validar` (tarea 1).
- Produces: `widget.dispositivos.sesion` con constantes `ESPERA = "espera"`, `CONECTANDO = "conectando"`, `CONECTADO = "conectado"`, `NO_ENCONTRADO = "no_encontrado"` y `SIN_BLUETOOTH = "sin_bluetooth"`; `es_bluetooth_apagado(error) -> bool`; `class SesionSable(crear_transporte: Callable[[], Transporte], *, estado_inicial: dict | None = None, intentos=3, pausa_reintento=2.0, inactividad=60.0, timeout_respuesta=5.0)` con atributos `estado: dict`, `conexion: str` y `al_evento: Callable[[str, dict], None] | None`, y métodos `async pedir(clave, valor)` (lanza `ComandoInvalido` sin conectar), `async reintentar()`, `async fuentes() -> list[str] | None` y `async cerrar()`. Los eventos son `("conexion", {"estado": str, "intento"?: int})`, `("estado", cambios: dict)` y `("error", {"clave": str, "mensaje": str})`.

- [ ] **Step 1: Escribir las pruebas (fallan)**

`tests/test_sesion.py`:
```python
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
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python -m pytest tests/test_sesion.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'widget.dispositivos.sesion'`.

- [ ] **Step 3: Implementar `SesionSable`**

`widget/dispositivos/sesion.py`:
```python
"""Conexión a demanda con un sable: cola de órdenes, reintentos y desconexión por inactividad."""
import asyncio
import contextlib
import logging
from typing import Callable

from bleak.exc import BleakBluetoothNotAvailableError

from widget.dispositivos.protocolo import validar
from widget.dispositivos.transporte import Transporte
from widget.dispositivos.xeno import SableXeno

log = logging.getLogger(__name__)

ESPERA = "espera"
CONECTANDO = "conectando"
CONECTADO = "conectado"
NO_ENCONTRADO = "no_encontrado"
SIN_BLUETOOTH = "sin_bluetooth"


def es_bluetooth_apagado(error: BaseException) -> bool:
    return isinstance(error, BleakBluetoothNotAvailableError)


class SesionSable:
    def __init__(self, crear_transporte: Callable[[], Transporte], *, estado_inicial: dict | None = None,
                 intentos: int = 3, pausa_reintento: float = 2.0, inactividad: float = 60.0,
                 timeout_respuesta: float = 5.0):
        self.estado: dict = dict(estado_inicial or {})
        self.conexion = ESPERA
        self.al_evento: Callable[[str, dict], None] | None = None
        self._crear_transporte = crear_transporte
        self._intentos = intentos
        self._pausa = pausa_reintento
        self._inactividad = inactividad
        self._timeout = timeout_respuesta
        self._sable: SableXeno | None = None
        self._pendientes: dict = {}
        self._trabajo: asyncio.Task | None = None
        self._tarea_inactividad: asyncio.Task | None = None
        self._candado = asyncio.Lock()

    # ---- API ----
    async def pedir(self, clave: str, valor) -> None:
        """Encola una orden (valida antes; si ya había una con la misma clave, queda solo la última)."""
        validar(clave, valor)
        self._pendientes.pop(clave, None)
        self._pendientes[clave] = valor
        if self._trabajo is None or self._trabajo.done():
            self._trabajo = asyncio.create_task(self._procesar())

    async def reintentar(self) -> None:
        if self._trabajo is None or self._trabajo.done():
            self._trabajo = asyncio.create_task(self._asegurar_conexion())

    async def fuentes(self) -> list[str] | None:
        """Lista de fuentes del sable, o None si no se pudo conectar o leer."""
        if not await self._asegurar_conexion():
            return None
        try:
            nombres = await self._sable.listar_fuentes()
        except Exception:
            log.exception("No se pudo leer la lista de fuentes")
            return None
        self._reiniciar_inactividad()
        return nombres

    async def cerrar(self) -> None:
        for tarea in (self._trabajo, self._tarea_inactividad):
            if tarea is not None and not tarea.done():
                tarea.cancel()
        self._pendientes.clear()
        await self._desconectar()

    # ---- interno ----
    async def _procesar(self) -> None:
        while self._pendientes:
            if not await self._asegurar_conexion():
                self._pendientes.clear()
                return
            clave = next(iter(self._pendientes))
            valor = self._pendientes.pop(clave)
            try:
                await self._sable.enviar(clave, valor)
            except Exception:
                log.exception("Fallo al enviar %s", clave)
                self._pendientes.clear()
                self._emitir("error", {"clave": clave, "mensaje": "No se pudo enviar al sable"})
                await self._desconectar()
                self._cambiar_conexion(ESPERA)
                return
            self._reiniciar_inactividad()

    async def _asegurar_conexion(self) -> bool:
        async with self._candado:
            if self._sable is not None and self._sable.transporte.conectado:
                return True
            for intento in range(1, self._intentos + 1):
                self._cambiar_conexion(CONECTANDO, intento=intento)
                transporte = self._crear_transporte()
                sable = SableXeno(transporte, self._timeout)
                sable.al_cambiar = self._al_cambiar
                sable.al_error = self._al_error
                try:
                    await sable.conectar()
                except Exception as error:
                    log.info("Intento %d de conexión fallido: %r", intento, error)
                    with contextlib.suppress(Exception):
                        await sable.desconectar()
                    if es_bluetooth_apagado(error):
                        self._cambiar_conexion(SIN_BLUETOOTH)
                        return False
                    if intento < self._intentos:
                        await asyncio.sleep(self._pausa)
                    continue
                transporte.al_desconectar = lambda s=sable: self._al_corte(s)
                self._sable = sable
                self._cambiar_conexion(CONECTADO)
                self._reiniciar_inactividad()
                return True
            self._cambiar_conexion(NO_ENCONTRADO)
            return False

    def _al_corte(self, sable: SableXeno) -> None:
        if sable is not self._sable:  # corte de una conexión que ya cerramos nosotros
            return
        self._sable = None
        if self._tarea_inactividad is not None:
            self._tarea_inactividad.cancel()
        self._cambiar_conexion(ESPERA)

    async def _desconectar(self) -> None:
        sable, self._sable = self._sable, None
        if sable is not None:
            with contextlib.suppress(Exception):
                await sable.desconectar()

    def _reiniciar_inactividad(self) -> None:
        if self._tarea_inactividad is not None and not self._tarea_inactividad.done():
            self._tarea_inactividad.cancel()
        self._tarea_inactividad = asyncio.create_task(self._esperar_inactividad())

    async def _esperar_inactividad(self) -> None:
        await asyncio.sleep(self._inactividad)
        async with self._candado:
            if self._pendientes or self._sable is None:
                return
            await self._desconectar()
            self._cambiar_conexion(ESPERA)

    def _al_cambiar(self, cambios: dict) -> None:
        self.estado.update(cambios)
        self._emitir("estado", dict(cambios))

    def _al_error(self, clave: str, mensaje: str) -> None:
        self._emitir("error", {"clave": clave, "mensaje": mensaje})

    def _cambiar_conexion(self, estado: str, **extra) -> None:
        self.conexion = estado
        self._emitir("conexion", {"estado": estado, **extra})

    def _emitir(self, tipo: str, datos: dict) -> None:
        if self.al_evento is None:
            return
        try:
            self.al_evento(tipo, datos)
        except Exception:
            log.exception("Error al emitir el evento %s", tipo)
```

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python -m pytest tests/ -v`
Expected: PASS (todas).

- [ ] **Step 5: Commit**

```bash
git add widget/dispositivos/sesion.py tests/test_sesion.py
git commit -m "Conexión a demanda: cola con coalescencia, reintentos e inactividad" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 4: Configuración persistente

**Files:**
- Create: `widget/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nada.
- Produces: `widget.config` con `CARPETA: Path`, `RUTA_POR_DEFECTO: Path`, `CLAVES_CACHE: tuple[str, ...]`, `LARGO_MAX_NOMBRE = 40`, y `class Config(ruta: Path, datos: dict)`. `Config` tiene `Config.cargar(ruta=RUTA_POR_DEFECTO) -> Config`, `guardar()`, la propiedad `dispositivos -> list[dict]`, `buscar(id_) -> dict | None`, `agregar_dispositivo(tipo, nombre, direccion) -> dict` (lanza `ValueError`), `renombrar(id_, nombre)` (lanza `ValueError` o `KeyError`), `quitar(id_)` y `actualizar_cache(id_, estado=None, fuentes=None)`. Cada dispositivo es `{"id", "tipo", "nombre", "direccion", "ultimo_estado": dict, "fuentes": list[str]}`.

- [ ] **Step 1: Escribir las pruebas (fallan)**

`tests/test_config.py`:
```python
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
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'widget.config'`.

- [ ] **Step 3: Implementar `Config`**

`widget/config.py`:
```python
"""Configuración persistente en %APPDATA%\\DeskControl\\config.json (dispositivos, caché, ventana, atajo)."""
import contextlib
import copy
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path

log = logging.getLogger(__name__)

CARPETA = Path(os.environ.get("APPDATA", str(Path.home()))) / "DeskControl"
RUTA_POR_DEFECTO = CARPETA / "config.json"
LARGO_MAX_NOMBRE = 40
CLAVES_CACHE = ("PowerOn", "Power", "Volume", "Brightness", "BackgroundColor",
                "CurrentSoundPackageNo", "TotalSoundPackage", "fontname")
_CAMPOS_DISPOSITIVO = ("id", "tipo", "nombre", "direccion")

POR_DEFECTO = {
    "version": 1,
    "atajo": "ctrl+shift+space",
    "autoarranque": True,
    "ventana": {"x": None, "y": None},
    "dispositivos": [],
}


def _limpiar_nombre(nombre) -> str:
    limpio = " ".join(str(nombre).split())[:LARGO_MAX_NOMBRE]
    if not limpio:
        raise ValueError("El nombre no puede estar vacío")
    return limpio


def _dispositivo_valido(d) -> bool:
    return isinstance(d, dict) and all(isinstance(d.get(k), str) and d.get(k) for k in _CAMPOS_DISPOSITIVO)


class Config:
    def __init__(self, ruta: Path, datos: dict):
        self.ruta = Path(ruta)
        self.datos = datos
        self._candado = threading.RLock()  # la usan el hilo de la ventana, el de la bandeja y el del Bluetooth

    @classmethod
    def cargar(cls, ruta: Path = RUTA_POR_DEFECTO) -> "Config":
        ruta = Path(ruta)
        datos = copy.deepcopy(POR_DEFECTO)
        if ruta.exists():
            try:
                leidos = json.loads(ruta.read_text(encoding="utf-8"))
                if not isinstance(leidos, dict) or not isinstance(leidos.get("dispositivos", []), list):
                    raise ValueError("formato inesperado")
                datos.update(leidos)
            except (ValueError, OSError) as error:
                respaldo = ruta.with_name(f"config.corrupto-{time.strftime('%Y%m%d-%H%M%S')}.json")
                log.warning("config.json inválido (%s); copia en %s", error, respaldo.name)
                with contextlib.suppress(OSError):
                    ruta.replace(respaldo)
                datos = copy.deepcopy(POR_DEFECTO)
        if not isinstance(datos.get("ventana"), dict):
            datos["ventana"] = {"x": None, "y": None}
        dispositivos = [d for d in datos["dispositivos"] if _dispositivo_valido(d)]
        for d in dispositivos:
            if not isinstance(d.get("ultimo_estado"), dict):
                d["ultimo_estado"] = {}
            if not isinstance(d.get("fuentes"), list):
                d["fuentes"] = []
        datos["dispositivos"] = dispositivos
        return cls(ruta, datos)

    def guardar(self) -> None:
        with self._candado:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            temporal = self.ruta.with_suffix(".tmp")
            temporal.write_text(json.dumps(self.datos, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporal, self.ruta)

    @property
    def dispositivos(self) -> list[dict]:
        return self.datos["dispositivos"]

    def buscar(self, id_: str) -> dict | None:
        return next((d for d in self.dispositivos if d["id"] == id_), None)

    def agregar_dispositivo(self, tipo: str, nombre: str, direccion: str) -> dict:
        with self._candado:
            nombre = _limpiar_nombre(nombre)
            direccion = str(direccion).upper()
            if any(d["direccion"] == direccion for d in self.dispositivos):
                raise ValueError("Ese dispositivo ya está guardado")
            dispositivo = {"id": uuid.uuid4().hex[:8], "tipo": tipo, "nombre": nombre, "direccion": direccion,
                           "ultimo_estado": {}, "fuentes": []}
            self.dispositivos.append(dispositivo)
            return dispositivo

    def renombrar(self, id_: str, nombre: str) -> None:
        with self._candado:
            dispositivo = self.buscar(id_)
            if dispositivo is None:
                raise KeyError(id_)
            dispositivo["nombre"] = _limpiar_nombre(nombre)

    def quitar(self, id_: str) -> None:
        with self._candado:
            self.datos["dispositivos"] = [d for d in self.dispositivos if d["id"] != id_]

    def actualizar_cache(self, id_: str, estado: dict | None = None, fuentes: list[str] | None = None) -> None:
        with self._candado:
            dispositivo = self.buscar(id_)
            if dispositivo is None:
                return
            if estado:
                dispositivo["ultimo_estado"].update({k: v for k, v in estado.items() if k in CLAVES_CACHE})
            if fuentes is not None:
                dispositivo["fuentes"] = list(fuentes)
```

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: PASS (todas).

- [ ] **Step 5: Commit**

```bash
git add widget/config.py tests/test_config.py
git commit -m "Configuración persistente con dispositivos guardados y caché" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 5: Búsqueda de sables y diagnóstico con el sable real

**Files:**
- Create: `widget/dispositivos/busqueda.py`
- Create: `widget/diagnostico.py`
- Test: `tests/test_busqueda.py`

**Interfaces:**
- Consumes: `protocolo.SERVICIOS_XENO` (tarea 1), `TransporteBleak` (tarea 2), `SesionSable` (tarea 3), `config.CLAVES_CACHE` (tarea 4).
- Produces: `widget.dispositivos.busqueda` con `es_xeno(service_uuids) -> bool` y `async buscar_sables(segundos: float = 8.0) -> list[dict]` (cada elemento es `{"direccion": str (mayúsculas), "nombre": str, "rssi": int}`, ordenados por señal de mayor a menor). Lanza `BleakBluetoothNotAvailableError` si el Bluetooth está apagado.

- [ ] **Step 1: Escribir las pruebas (fallan)**

`tests/test_busqueda.py`:
```python
from widget.dispositivos.busqueda import es_xeno


def test_reconoce_servicios_xeno():
    assert es_xeno(["0000dae0-0000-1000-8000-00805f9b34fb"])
    assert es_xeno(["0000180F-0000-1000-8000-00805F9B34FB", "00003AB0-0000-1000-8000-00805F9B34FB"])


def test_rechaza_otros_dispositivos():
    assert not es_xeno([])
    assert not es_xeno(["0000fe9f-0000-1000-8000-00805f9b34fb"])
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python -m pytest tests/test_busqueda.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'widget.dispositivos.busqueda'`.

- [ ] **Step 3: Implementar la búsqueda y el diagnóstico**

`widget/dispositivos/busqueda.py`:
```python
"""Búsqueda de placas Xeno3 cercanas (solo las que anuncian sus servicios: nada de teles ni auriculares)."""
from typing import Iterable

from bleak import BleakScanner

from widget.dispositivos.protocolo import SERVICIOS_XENO


def es_xeno(service_uuids: Iterable[str]) -> bool:
    return any(u.lower() in SERVICIOS_XENO for u in service_uuids)


async def buscar_sables(segundos: float = 8.0) -> list[dict]:
    encontrados = await BleakScanner.discover(timeout=segundos, return_adv=True)
    sables = [
        {"direccion": d.address.upper(), "nombre": adv.local_name or d.name or "Sable Xeno3", "rssi": adv.rssi}
        for d, adv in encontrados.values()
        if es_xeno(adv.service_uuids)
    ]
    return sorted(sables, key=lambda s: -s["rssi"])
```

`widget/diagnostico.py`:
```python
"""Prueba manual del motor con el sable real (solo lectura): python -m widget.diagnostico"""
import asyncio

from widget.config import CLAVES_CACHE
from widget.dispositivos.busqueda import buscar_sables
from widget.dispositivos.sesion import SesionSable
from widget.dispositivos.transporte import TransporteBleak


async def main() -> None:
    print("Buscando sables (8 s)...")
    sables = await buscar_sables()
    for s in sables:
        print(f"  {s['nombre']}  {s['direccion']}  {s['rssi']} dBm")
    if not sables:
        print("No se encontró ninguno. ¿Está encendido y sin el teléfono conectado?")
        return
    sesion = SesionSable(lambda: TransporteBleak(sables[0]["direccion"]))
    sesion.al_evento = lambda tipo, datos: print(f"  [{tipo}] {datos}" if tipo != "estado" else f"  [estado] {len(datos)} claves")
    fuentes = await sesion.fuentes()
    print("Fuentes:", fuentes)
    print("Estado:", {k: sesion.estado.get(k) for k in CLAVES_CACHE})
    await sesion.cerrar()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python -m pytest tests/ -v`
Expected: PASS (todas).

- [ ] **Step 5: Verificación manual con el sable real**

Requiere el sable encendido, cerca y con el Bluetooth del iPhone apagado.

Run: `.venv/Scripts/python -m widget.diagnostico`
Expected: lista un `Saber` con su dirección; eventos `[conexion] {'estado': 'conectando', 'intento': 1}` → `{'estado': 'conectado'}`; `Fuentes:` con las 16 fuentes (The Chosen … Truly Lost); `Estado:` con `Volume`, `BackgroundColor`, etc. Si falla por señal débil, repetir (hasta 3 veces).

- [ ] **Step 6: Commit**

```bash
git add widget/dispositivos/busqueda.py widget/diagnostico.py tests/test_busqueda.py
git commit -m "Búsqueda de placas Xeno3 y diagnóstico del motor con el sable real" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 6: Bucle en segundo plano y `Puente` para JavaScript

**Files:**
- Create: `widget/bucle.py`
- Create: `widget/puente.py`
- Test: `tests/test_bucle.py`, `tests/test_puente.py`

**Interfaces:**
- Consumes: `Config` (tarea 4), `SesionSable`, `ESPERA`, `CONECTADO`, `es_bluetooth_apagado` (tarea 3), `buscar_sables` (tarea 5), `ComandoInvalido` (tarea 1).
- Produces:
  - `widget.bucle.BucleAsync`: `iniciar()`, `ejecutar(coro) -> concurrent.futures.Future`, `detener(timeout=5.0)` y el atributo `loop`. El hilo se llama `"ble"`.
  - `widget.puente.Puente(config: Config, bucle: BucleAsync, crear_sesion: Callable[[dict], SesionSable], buscar=buscar_sables)`.
    - API pública para JS (todos los métodos devuelven `dict` JSON):
      - `inicial()` → `{"dispositivos": [{"id", "tipo", "nombre", "direccion", "conexion", "estado", "fuentes"}]}`
      - `sable_enviar(id_, clave, valor)` → `{"ok": bool, "error"?: str}`
      - `sable_reintentar(id_)`
      - `sable_fuentes(id_, refrescar=False)` → `{"ok", "fuentes"?, "error"?}`
      - `buscar()` → `{"ok", "encontrados"?: [{"direccion", "nombre", "rssi", "guardado": bool}], "error"?: "sin_bluetooth" | "fallo"}`
      - `guardar_dispositivo(direccion, nombre)` → `{"ok", "dispositivo"?, "error"?}`
      - `renombrar_dispositivo(id_, nombre)`, `quitar_dispositivo(id_)`, `ocultar()`
    - Interno (con guion bajo, para que pywebview no lo exponga): `_conectar_ventana(ventana, al_ocultar)`, `async _cerrar()`, `_emitir(evento: dict)`, `_guardar()`.
    - Eventos hacia JS, por `ventana.run_js("window.deskControl && window.deskControl.recibir(<json>)")`: `{"id": str, "tipo": "conexion" | "estado" | "error" | "fuentes", "datos": ...}`.

- [ ] **Step 1: Escribir las pruebas (fallan)**

`tests/test_bucle.py`:
```python
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
```

`tests/test_puente.py`:
```python
import json
from types import SimpleNamespace

import pytest
from bleak.exc import BleakBluetoothNotAvailableError, BleakBluetoothNotAvailableReason

from tests.ayudas import esperar_sync
from tests.sable_simulado import FUENTES, SableSimulado
from widget.bucle import BucleAsync
from widget.config import Config
from widget.dispositivos.sesion import SesionSable
from widget.puente import Puente

PREFIJO = "window.deskControl && window.deskControl.recibir("


class VentanaFalsa:
    def __init__(self):
        self.scripts = []

    def run_js(self, script):
        self.scripts.append(script)

    def eventos(self):
        return [json.loads(s[len(PREFIJO):-1]) for s in self.scripts if s.startswith(PREFIJO)]


@pytest.fixture
def entorno(tmp_path):
    config = Config.cargar(tmp_path / "config.json")
    dispositivo = config.agregar_dispositivo("xeno", "Mi sable", "AA:BB:CC:DD:EE:FF")
    bucle = BucleAsync()
    bucle.iniciar()
    simulados = []
    resultado_busqueda = {"valor": []}

    def crear_sesion(d):
        def fabrica():
            sim = SableSimulado()
            simulados.append(sim)
            return sim
        return SesionSable(fabrica, estado_inicial=d.get("ultimo_estado"), pausa_reintento=0.01,
                           inactividad=5, timeout_respuesta=0.5)

    async def buscar_falso():
        if isinstance(resultado_busqueda["valor"], Exception):
            raise resultado_busqueda["valor"]
        return resultado_busqueda["valor"]

    puente = Puente(config, bucle, crear_sesion, buscar=buscar_falso)
    ventana = VentanaFalsa()
    ocultadas = []
    puente._conectar_ventana(ventana, al_ocultar=lambda: ocultadas.append(True))
    yield SimpleNamespace(config=config, id=dispositivo["id"], puente=puente, ventana=ventana,
                          simulados=simulados, busqueda=resultado_busqueda, ocultadas=ocultadas)
    bucle.ejecutar(puente._cerrar()).result(5)
    bucle.detener()


def test_inicial_muestra_cache(entorno):
    entorno.config.actualizar_cache(entorno.id, estado={"Volume": 5})
    d = entorno.puente.inicial()["dispositivos"][0]
    assert d["nombre"] == "Mi sable" and d["conexion"] == "espera" and d["estado"]["Volume"] == 5


def test_enviar_conecta_emite_eventos_y_actualiza_cache(entorno):
    assert entorno.puente.sable_enviar(entorno.id, "Volume", 30) == {"ok": True}
    esperar_sync(lambda: any(e["tipo"] == "estado" and e["datos"].get("Volume") == 30
                             for e in entorno.ventana.eventos()))
    assert {"id": entorno.id, "tipo": "conexion", "datos": {"estado": "conectado"}} in entorno.ventana.eventos()
    assert entorno.config.buscar(entorno.id)["ultimo_estado"]["Volume"] == 30


def test_al_conectar_sin_cache_lee_las_fuentes_solo(entorno):
    entorno.puente.sable_enviar(entorno.id, "Volume", 30)
    esperar_sync(lambda: any(e["tipo"] == "fuentes" for e in entorno.ventana.eventos()))
    assert entorno.config.buscar(entorno.id)["fuentes"] == FUENTES


def test_enviar_invalido_devuelve_error_sin_conectar(entorno):
    r = entorno.puente.sable_enviar(entorno.id, "Reset", True)
    assert r["ok"] is False and "no permitido" in r["error"]
    assert entorno.simulados == []


def test_fuentes_desde_cache_sin_conectar(entorno):
    entorno.config.actualizar_cache(entorno.id, fuentes=["A", "B"])
    assert entorno.puente.sable_fuentes(entorno.id) == {"ok": True, "fuentes": ["A", "B"]}
    assert entorno.simulados == []


def test_fuentes_refrescar_lee_del_sable(entorno):
    entorno.config.actualizar_cache(entorno.id, fuentes=["A"])
    assert entorno.puente.sable_fuentes(entorno.id, True) == {"ok": True, "fuentes": FUENTES}


def test_buscar_marca_guardados(entorno):
    entorno.busqueda["valor"] = [{"direccion": "AA:BB:CC:DD:EE:FF", "nombre": "Saber", "rssi": -80},
                                 {"direccion": "11:22:33:44:55:66", "nombre": "Saber", "rssi": -90}]
    r = entorno.puente.buscar()
    assert [s["guardado"] for s in r["encontrados"]] == [True, False]


def test_buscar_sin_bluetooth(entorno):
    entorno.busqueda["valor"] = BleakBluetoothNotAvailableError("off", BleakBluetoothNotAvailableReason.POWERED_OFF)
    assert entorno.puente.buscar() == {"ok": False, "error": "sin_bluetooth"}


def test_guardar_duplicado_y_renombrar(entorno):
    assert entorno.puente.guardar_dispositivo("aa:bb:cc:dd:ee:ff", "Otro")["ok"] is False
    r = entorno.puente.guardar_dispositivo("11:22:33:44:55:66", "Segundo")
    assert r["ok"] and r["dispositivo"]["nombre"] == "Segundo"
    assert entorno.puente.renombrar_dispositivo(r["dispositivo"]["id"], "   ")["ok"] is False


def test_quitar_cierra_la_sesion(entorno):
    entorno.puente.sable_enviar(entorno.id, "Volume", 30)
    esperar_sync(lambda: entorno.simulados and entorno.simulados[0].conectado)
    assert entorno.puente.quitar_dispositivo(entorno.id) == {"ok": True}
    assert not entorno.simulados[0].conectado
    assert entorno.config.dispositivos == []


def test_emitir_codifica_texto_raro(entorno):
    raro = '<b>"x"</b>\u2028\'; alert(1)//'
    entorno.puente._emitir({"id": "x", "tipo": "fuentes", "datos": [raro]})
    assert entorno.ventana.eventos()[-1]["datos"] == [raro]
    assert "\u2028" not in entorno.ventana.scripts[-1]


def test_ocultar_llama_al_callback(entorno):
    assert entorno.puente.ocultar() == {"ok": True}
    assert entorno.ocultadas == [True]
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python -m pytest tests/test_bucle.py tests/test_puente.py -v`
Expected: ERROR con `ModuleNotFoundError: No module named 'widget.bucle'`.

- [ ] **Step 3: Implementar `BucleAsync`**

`widget/bucle.py`:
```python
"""Bucle asyncio en un hilo aparte: ahí vive todo el Bluetooth, así la ventana nunca se congela."""
import asyncio
import concurrent.futures
import threading


class BucleAsync:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._hilo = threading.Thread(target=self._correr, name="ble", daemon=True)

    def _correr(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def iniciar(self) -> None:
        self._hilo.start()

    def ejecutar(self, coro) -> concurrent.futures.Future:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def detener(self, timeout: float = 5.0) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._hilo.join(timeout)
```

- [ ] **Step 4: Implementar `Puente`**

`widget/puente.py`:
```python
"""API que la ventana (JavaScript) llama vía pywebview, y eventos que Python le envía.

pywebview expone a JS todos los métodos y atributos públicos de este objeto: lo interno lleva guion bajo.
"""
import asyncio
import json
import logging
from typing import Callable

from widget.bucle import BucleAsync
from widget.config import Config
from widget.dispositivos.busqueda import buscar_sables
from widget.dispositivos.protocolo import ComandoInvalido
from widget.dispositivos.sesion import CONECTADO, ESPERA, SesionSable, es_bluetooth_apagado

log = logging.getLogger(__name__)

TIMEOUT_CORTO = 5
TIMEOUT_CIERRE = 15
TIMEOUT_BUSQUEDA = 30
TIMEOUT_FUENTES = 180


class Puente:
    def __init__(self, config: Config, bucle: BucleAsync, crear_sesion: Callable[[dict], SesionSable],
                 buscar=buscar_sables):
        self._config = config
        self._bucle = bucle
        self._crear_sesion = crear_sesion
        self._buscar = buscar
        self._sesiones: dict[str, SesionSable] = {}
        self._ventana = None
        self._al_ocultar: Callable[[], None] | None = None

    def _conectar_ventana(self, ventana, al_ocultar: Callable[[], None]) -> None:
        self._ventana = ventana
        self._al_ocultar = al_ocultar

    # ---- API para JavaScript ----
    def inicial(self) -> dict:
        return {"dispositivos": [self._vista_dispositivo(d) for d in self._config.dispositivos]}

    def sable_enviar(self, id_, clave, valor) -> dict:
        try:
            self._bucle.ejecutar(self._sesion(id_).pedir(clave, valor)).result(TIMEOUT_CORTO)
        except (ComandoInvalido, KeyError) as error:
            return {"ok": False, "error": str(error).strip("'")}
        return {"ok": True}

    def sable_reintentar(self, id_) -> dict:
        try:
            self._bucle.ejecutar(self._sesion(id_).reintentar()).result(TIMEOUT_CORTO)
        except KeyError as error:
            return {"ok": False, "error": str(error).strip("'")}
        return {"ok": True}

    def sable_fuentes(self, id_, refrescar=False) -> dict:
        dispositivo = self._config.buscar(id_)
        if dispositivo is None:
            return {"ok": False, "error": "Dispositivo desconocido"}
        if dispositivo["fuentes"] and not refrescar:
            return {"ok": True, "fuentes": list(dispositivo["fuentes"])}
        nombres = self._bucle.ejecutar(self._sesion(id_).fuentes()).result(TIMEOUT_FUENTES)
        if not nombres:
            return {"ok": False, "error": "No se pudo leer la lista de fuentes"}
        self._config.actualizar_cache(id_, fuentes=nombres)
        self._guardar()
        return {"ok": True, "fuentes": nombres}

    def buscar(self) -> dict:
        try:
            encontrados = self._bucle.ejecutar(self._buscar()).result(TIMEOUT_BUSQUEDA)
        except Exception as error:
            if es_bluetooth_apagado(error):
                return {"ok": False, "error": "sin_bluetooth"}
            log.exception("Error al buscar dispositivos")
            return {"ok": False, "error": "fallo"}
        guardadas = {d["direccion"] for d in self._config.dispositivos}
        return {"ok": True, "encontrados": [{**s, "guardado": s["direccion"] in guardadas} for s in encontrados]}

    def guardar_dispositivo(self, direccion, nombre) -> dict:
        try:
            dispositivo = self._config.agregar_dispositivo("xeno", nombre, direccion)
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        self._guardar()
        return {"ok": True, "dispositivo": self._vista_dispositivo(dispositivo)}

    def renombrar_dispositivo(self, id_, nombre) -> dict:
        try:
            self._config.renombrar(id_, nombre)
        except ValueError as error:
            return {"ok": False, "error": str(error)}
        except KeyError:
            return {"ok": False, "error": "Dispositivo desconocido"}
        self._guardar()
        return {"ok": True}

    def quitar_dispositivo(self, id_) -> dict:
        sesion = self._sesiones.pop(id_, None)
        if sesion is not None:
            self._bucle.ejecutar(sesion.cerrar()).result(TIMEOUT_CIERRE)
        self._config.quitar(id_)
        self._guardar()
        return {"ok": True}

    def ocultar(self) -> dict:
        if self._al_ocultar is not None:
            self._al_ocultar()
        return {"ok": True}

    # ---- interno ----
    async def _cerrar(self) -> None:
        for sesion in list(self._sesiones.values()):
            await sesion.cerrar()

    def _vista_dispositivo(self, d: dict) -> dict:
        sesion = self._sesiones.get(d["id"])
        return {
            "id": d["id"], "tipo": d["tipo"], "nombre": d["nombre"], "direccion": d["direccion"],
            "conexion": sesion.conexion if sesion else ESPERA,
            "estado": dict(sesion.estado) if sesion else dict(d["ultimo_estado"]),
            "fuentes": list(d["fuentes"]),
        }

    def _sesion(self, id_: str) -> SesionSable:
        if id_ not in self._sesiones:
            dispositivo = self._config.buscar(id_)
            if dispositivo is None:
                raise KeyError("Dispositivo desconocido")
            sesion = self._crear_sesion(dispositivo)
            sesion.al_evento = lambda tipo, datos, i=id_: self._al_evento(i, tipo, datos)
            self._sesiones[id_] = sesion
        return self._sesiones[id_]

    def _al_evento(self, id_: str, tipo: str, datos: dict) -> None:
        """Corre en el hilo del Bluetooth."""
        if tipo == "estado":
            self._config.actualizar_cache(id_, estado=datos)
        elif tipo == "conexion" and datos["estado"] == ESPERA:
            self._guardar()
        elif tipo == "conexion" and datos["estado"] == CONECTADO:
            dispositivo = self._config.buscar(id_)
            total = self._sesiones[id_].estado.get("TotalSoundPackage")
            if dispositivo is not None and (not dispositivo["fuentes"] or (total and total != len(dispositivo["fuentes"]))):
                asyncio.ensure_future(self._refrescar_fuentes(id_))
        self._emitir({"id": id_, "tipo": tipo, "datos": datos})

    async def _refrescar_fuentes(self, id_: str) -> None:
        sesion = self._sesiones.get(id_)
        nombres = await sesion.fuentes() if sesion else None
        if nombres:
            self._config.actualizar_cache(id_, fuentes=nombres)
            self._guardar()
            self._emitir({"id": id_, "tipo": "fuentes", "datos": nombres})

    def _emitir(self, evento: dict) -> None:
        if self._ventana is None:
            return
        # json.dumps con ensure_ascii escapa comillas, < > y \u2028: el texto del sable no puede inyectar código.
        script = f"window.deskControl && window.deskControl.recibir({json.dumps(evento)})"
        try:
            self._ventana.run_js(script)
        except Exception:
            log.debug("La ventana no pudo recibir el evento", exc_info=True)

    def _guardar(self) -> None:
        try:
            self._config.guardar()
        except OSError:
            log.exception("No se pudo guardar la configuración")
```

Nota: `json.dumps` con `ensure_ascii=True` (el valor por defecto) escapa `\u2028`, y las comillas y barras quedan como literales JSON válidos. El test `test_emitir_codifica_texto_raro` lo verifica.

- [ ] **Step 5: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python -m pytest tests/ -v`
Expected: PASS (todas).

- [ ] **Step 6: Commit**

```bash
git add widget/bucle.py widget/puente.py tests/test_bucle.py tests/test_puente.py
git commit -m "Puente entre la ventana y el motor Bluetooth en hilo propio" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 7: Integración con Windows (atajo, instancia única, autoarranque, ventana, bandeja)

**Files:**
- Create: `widget/escritorio/atajo.py`, `widget/escritorio/instancia.py`, `widget/escritorio/autoarranque.py`, `widget/escritorio/ventana.py`, `widget/escritorio/bandeja.py`
- Test: `tests/test_escritorio.py`

**Interfaces:**
- Consumes: nada de tareas anteriores.
- Produces:
  - `atajo`: `class AtajoInvalido(ValueError)`, `interpretar(texto) -> tuple[int, int]` (modificadores con `MOD_NOREPEAT`, código de tecla virtual), `class AtajoGlobal(texto, al_pulsar)` con `iniciar() -> bool`, `detener()` y el atributo `registrado: bool`.
  - `instancia`: `adquirir_instancia_unica(nombre) -> handle | None` y `liberar(handle)`.
  - `autoarranque`: `comando() -> str`, `esta_activo(clave=CLAVE_RUN, nombre=NOMBRE) -> bool`, `activar(clave=..., nombre=...)` y `desactivar(clave=..., nombre=...)`.
  - `ventana`: `elegir_posicion(areas, margen=12) -> tuple[int, int]`, `listar_areas_de_trabajo() -> list[tuple[int, int, int, int]]`, `posicion_por_defecto()`, `buscar_ventana(titulo) -> int`, `redondear_esquinas(hwnd)`, `traer_al_frente(hwnd)` y `es_primer_plano(hwnd) -> bool`.
  - `bandeja`: `crear_icono(tamano=64) -> PIL.Image.Image` y `crear_bandeja(*, al_alternar, al_agregar, autoarranque_activo, al_cambiar_autoarranque, al_salir) -> pystray.Icon`.

- [ ] **Step 1: Escribir las pruebas (fallan)**

`tests/test_escritorio.py`:
```python
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
```

- [ ] **Step 2: Correr las pruebas y verificar que fallan**

Run: `.venv/Scripts/python -m pytest tests/test_escritorio.py -v`
Expected: ERROR con `ImportError: cannot import name 'atajo' from 'widget.escritorio'`.

- [ ] **Step 3: Implementar el atajo global**

`widget/escritorio/atajo.py`:
```python
"""Atajo de teclado global con RegisterHotKey: Windows avisa solo esa combinación (no espía el teclado)."""
import ctypes
import logging
import threading
from ctypes import wintypes
from typing import Callable

log = logging.getLogger(__name__)

MODIFICADORES = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
TECLAS = {"space": 0x20, "espacio": 0x20, "enter": 0x0D, "tab": 0x09,
          **{f"f{n}": 0x6F + n for n in range(1, 13)}}
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
_ID_ATAJO = 1


class AtajoInvalido(ValueError):
    """El texto del atajo no se entiende (ej.: 'ctrl+shift+space')."""


def interpretar(texto: str) -> tuple[int, int]:
    partes = [p.strip().lower() for p in str(texto).split("+")]
    if len(partes) < 2 or any(not p for p in partes):
        raise AtajoInvalido(f"Atajo inválido: {texto!r}")
    *mods, tecla = partes
    if any(m not in MODIFICADORES for m in mods) or len(set(mods)) != len(mods):
        raise AtajoInvalido(f"Modificadores inválidos en {texto!r}")
    if tecla in TECLAS:
        vk = TECLAS[tecla]
    elif len(tecla) == 1 and tecla.isascii() and tecla.isalnum():
        vk = ord(tecla.upper())
    else:
        raise AtajoInvalido(f"Tecla inválida en {texto!r}")
    banderas = MOD_NOREPEAT
    for m in mods:
        banderas |= MODIFICADORES[m]
    return banderas, vk


class AtajoGlobal:
    def __init__(self, texto: str, al_pulsar: Callable[[], None]):
        self.modificadores, self.tecla = interpretar(texto)
        self.registrado = False
        self._al_pulsar = al_pulsar
        self._listo = threading.Event()
        self._id_hilo: int | None = None
        self._hilo = threading.Thread(target=self._correr, name="atajo", daemon=True)

    def iniciar(self) -> bool:
        self._hilo.start()
        self._listo.wait(2)
        return self.registrado

    def _correr(self) -> None:
        user32 = ctypes.windll.user32
        self._id_hilo = ctypes.windll.kernel32.GetCurrentThreadId()
        self.registrado = bool(user32.RegisterHotKey(None, _ID_ATAJO, self.modificadores, self.tecla))
        self._listo.set()
        if not self.registrado:
            return
        mensaje = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(mensaje), None, 0, 0) > 0:
            if mensaje.message == WM_HOTKEY:
                try:
                    self._al_pulsar()
                except Exception:
                    log.exception("Error al manejar el atajo")
        user32.UnregisterHotKey(None, _ID_ATAJO)

    def detener(self) -> None:
        if self._id_hilo is not None and self._hilo.is_alive():
            ctypes.windll.user32.PostThreadMessageW(self._id_hilo, WM_QUIT, 0, 0)
            self._hilo.join(2)
```

- [ ] **Step 4: Implementar instancia única, autoarranque y ventana**

`widget/escritorio/instancia.py`:
```python
"""Instancia única con un mutex con nombre: si ya hay un Desk Control abierto, el segundo se cierra."""
import ctypes
from ctypes import wintypes

ERROR_ALREADY_EXISTS = 183
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def adquirir_instancia_unica(nombre: str):
    """Devuelve el handle del mutex (mantenerlo vivo) o None si otra instancia ya lo tiene."""
    handle = _kernel32.CreateMutexW(None, False, nombre)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        _kernel32.CloseHandle(handle)
        return None
    return handle


def liberar(handle) -> None:
    _kernel32.CloseHandle(handle)
```

`widget/escritorio/autoarranque.py`:
```python
"""Arranque con Windows: valor en HKCU\\...\\Run (no requiere permisos de administrador)."""
import sys
import winreg
from pathlib import Path

CLAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
NOMBRE = "DeskControl"
LANZADOR = Path(__file__).resolve().parents[2] / "desk_control.pyw"


def comando() -> str:
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{LANZADOR}" --oculto'


def esta_activo(clave: str = CLAVE_RUN, nombre: str = NOMBRE) -> bool:
    """True solo si el valor existe y apunta a esta copia del proyecto (si se movió la carpeta, es False)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave) as k:
            valor, _ = winreg.QueryValueEx(k, nombre)
    except FileNotFoundError:
        return False
    return valor == comando()


def activar(clave: str = CLAVE_RUN, nombre: str = NOMBRE) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, clave) as k:
        winreg.SetValueEx(k, nombre, 0, winreg.REG_SZ, comando())


def desactivar(clave: str = CLAVE_RUN, nombre: str = NOMBRE) -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, clave, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, nombre)
    except FileNotFoundError:
        pass
```

`widget/escritorio/ventana.py`:
```python
"""Ayudas de Win32 para la ventana: monitor vertical, esquinas redondeadas y primer plano."""
import ctypes
from ctypes import wintypes

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_dwmapi = ctypes.WinDLL("dwmapi")
_user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
_user32.FindWindowW.restype = wintypes.HWND
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]


_ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)


def elegir_posicion(areas: list[tuple[int, int, int, int]], margen: int = 12) -> tuple[int, int]:
    """Esquina superior izquierda del primer monitor vertical (o del primero si no hay vertical)."""
    verticales = [a for a in areas if (a[3] - a[1]) > (a[2] - a[0])]
    candidatas = verticales or areas
    if not candidatas:
        return margen, margen
    izquierda, arriba, _, _ = candidatas[0]
    return izquierda + margen, arriba + margen


def listar_areas_de_trabajo() -> list[tuple[int, int, int, int]]:
    areas = []

    def visitar(hmonitor, _hdc, _rect, _param):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if _user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            r = info.rcWork
            areas.append((r.left, r.top, r.right, r.bottom))
        return True

    _user32.EnumDisplayMonitors(None, None, _ENUM_PROC(visitar), 0)
    return areas


def posicion_por_defecto() -> tuple[int, int]:
    return elegir_posicion(listar_areas_de_trabajo())


def buscar_ventana(titulo: str) -> int:
    return _user32.FindWindowW(None, titulo) or 0


def redondear_esquinas(hwnd: int) -> None:
    valor = ctypes.c_int(DWMWCP_ROUND)
    _dwmapi.DwmSetWindowAttribute(wintypes.HWND(hwnd), DWMWA_WINDOW_CORNER_PREFERENCE,
                                  ctypes.byref(valor), ctypes.sizeof(valor))


def traer_al_frente(hwnd: int) -> None:
    _user32.SetForegroundWindow(hwnd)


def es_primer_plano(hwnd: int) -> bool:
    return (_user32.GetForegroundWindow() or 0) == hwnd
```

- [ ] **Step 5: Implementar la bandeja**

`widget/escritorio/bandeja.py`:
```python
"""Icono de la bandeja del sistema con su menú."""
from typing import Callable

import pystray
from PIL import Image, ImageDraw


def crear_icono(tamano: int = 64) -> Image.Image:
    """Un sable en diagonal: hoja verde y mango gris."""
    img = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = tamano / 64
    d.line([(20 * s, 44 * s), (54 * s, 10 * s)], fill=(60, 255, 140, 255), width=max(2, int(6 * s)))
    d.line([(8 * s, 56 * s), (22 * s, 42 * s)], fill=(175, 175, 185, 255), width=max(3, int(9 * s)))
    return img


def crear_bandeja(*, al_alternar: Callable[[], None], al_agregar: Callable[[], None],
                  autoarranque_activo: Callable[[], bool], al_cambiar_autoarranque: Callable[[], None],
                  al_salir: Callable[[], None]) -> pystray.Icon:
    menu = pystray.Menu(
        pystray.MenuItem("Mostrar / ocultar", lambda: al_alternar(), default=True),
        pystray.MenuItem("Agregar dispositivo", lambda: al_agregar()),
        pystray.MenuItem("Iniciar con Windows", lambda: al_cambiar_autoarranque(),
                         checked=lambda _item: autoarranque_activo()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Salir", lambda: al_salir()),
    )
    return pystray.Icon("DeskControl", crear_icono(), "Desk Control", menu)
```

- [ ] **Step 6: Correr las pruebas y verificar que pasan**

Run: `.venv/Scripts/python -m pytest tests/ -v`
Expected: PASS (todas). Si `test_atajo_ocupado_no_se_registra` falla en `primero.iniciar()`, es porque otro programa usa Ctrl+Alt+Shift+F11: cambiar ambos textos de esa prueba por `"ctrl+alt+shift+f10"`.

- [ ] **Step 7: Commit**

```bash
git add widget/escritorio tests/test_escritorio.py
git commit -m "Integración con Windows: atajo global, instancia única, autoarranque, ventana y bandeja" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 8: Ventana del widget, arranque y pantalla de búsqueda

**Files:**
- Create: `widget/main.py`, `widget/__main__.py`, `desk_control.pyw`
- Create: `widget/ui/index.html`, `widget/ui/estilos.css`, `widget/ui/util.js`, `widget/ui/app.js`, `widget/ui/busqueda.js`

**Interfaces:**
- Consumes: todo lo anterior (`BucleAsync`, `Puente`, `Config`, `SesionSable`, `TransporteBleak`, módulos de `escritorio`).
- Produces:
  - `widget.main.main(argv=None) -> int`, con las opciones `--oculto` y `--debug`.
  - En JS:
    - `window.deskControl` con `recibir(evento)` y `abrirBusqueda()`.
    - Global `util` con `el(tag, clase, texto)`, `limitar(fn, ms)`, `rgb([r, g, b]) -> "r,g,b"` y `aviso(texto, tipo)`.
    - Global `crearVista(d)` y la clase `VistaBusqueda`.
    - La interfaz de vista de dispositivo que debe cumplir `VistaSable` (tarea 9): atributo `raiz`, y métodos `estadoRecibido(cambios)`, `conexion(info)`, `errorRecibido({clave, mensaje})`, `fuentesRecibidas(lista)` e `indicador() -> {texto, clase}`.

- [ ] **Step 1: Verificar la API de pywebview instalada**

Run:
```bash
.venv/Scripts/python -c "import webview, inspect; print(hasattr(webview.Window, 'run_js')); print([p for p in ('frameless','easy_drag','hidden','background_color','js_api','x','y','resizable') if p in inspect.signature(webview.create_window).parameters])"
```
Expected: `True` y la lista completa de los 8 parámetros. Si `run_js` no existe, reemplazar `run_js` por `evaluate_js` en `widget/puente.py`, en `tests/test_puente.py` (la clase `VentanaFalsa`) y en este paso de `main.py`, y volver a correr `pytest`.

- [ ] **Step 2: Escribir el arranque**

`widget/main.py`:
```python
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
from widget.escritorio.ventana import (buscar_ventana, es_primer_plano, posicion_por_defecto,
                                       redondear_esquinas, traer_al_frente)
from widget.puente import Puente

TITULO = "Desk Control"
UI = Path(__file__).resolve().parent / "ui" / "index.html"
ANCHO, ALTO = 380, 600
log = logging.getLogger("widget")


def configurar_registro(debug: bool) -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    manejador = logging.handlers.RotatingFileHandler(CARPETA / "widget.log", maxBytes=1_000_000,
                                                     backupCount=2, encoding="utf-8")
    manejador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, handlers=[manejador])


class ControlVentana:
    """Mostrar/ocultar. El atajo oculta solo si el widget ya está al frente; si está tapado, lo trae."""

    def __init__(self, ventana, visible: bool):
        self.ventana = ventana
        self.visible = visible

    def ajustar_estilo(self) -> None:
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
            self.ocultar()
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
    x, y = posicion.get("x"), posicion.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        x, y = posicion_por_defecto()
    ventana = webview.create_window(TITULO, str(UI), js_api=puente, width=ANCHO, height=ALTO, x=x, y=y,
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

    ventana.events.moved += guardar_posicion
    ventana.events.shown += lambda *_args: control.ajustar_estilo()
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

    def agregar() -> None:
        control.mostrar()
        ventana.run_js("window.deskControl && window.deskControl.abrirBusqueda()")

    bandeja = crear_bandeja(al_alternar=control.alternar, al_agregar=agregar,
                            autoarranque_activo=autoarranque.esta_activo,
                            al_cambiar_autoarranque=cambiar_autoarranque, al_salir=ventana.destroy)
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
```

`widget/__main__.py`:
```python
from widget.main import main

raise SystemExit(main())
```

`desk_control.pyw`:
```python
"""Lanzador sin consola de Desk Control (lo usa el arranque con Windows)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from widget.main import main  # noqa: E402

raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 3: Escribir el HTML y los estilos base**

`widget/ui/index.html`:
```html
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; script-src 'self' file:; style-src 'self' file:; img-src 'self' file: data:">
<title>Desk Control</title>
<link rel="stylesheet" href="estilos.css">
</head>
<body>
<div class="widget">
  <header class="barra">
    <nav id="pestanas" class="pestanas"></nav>
    <button id="btn-agregar" class="btn-icono" title="Agregar dispositivo">＋</button>
    <div class="arrastre pywebview-drag-region" title="Arrastrá para mover"></div>
    <span id="indicador" class="indicador"></span>
    <button id="btn-ocultar" class="btn-icono" title="Ocultar (Ctrl+Shift+Espacio)">–</button>
  </header>
  <main id="vista" class="vista"></main>
  <div id="aviso" class="aviso" role="status"></div>
</div>
<script src="util.js"></script>
<script src="busqueda.js"></script>
<script src="app.js"></script>
</body>
</html>
```

`widget/ui/estilos.css`:
```css
/* Estilos base del widget y de la pantalla de búsqueda. Tema oscuro estilo Windows 11. */
:root {
  --fondo: #1c1c20; --superficie: rgba(255, 255, 255, .04); --superficie-2: rgba(255, 255, 255, .07);
  --borde: rgba(255, 255, 255, .1); --texto: #e8e8ea; --texto-2: #9a9aa2; --texto-3: #77777f;
  --verde: #4ade80; --rojo: #f87171; --ambar: #fbbf24;
  color-scheme: dark;
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; overflow: hidden; background: var(--fondo); color: var(--texto);
  font: 13px "Segoe UI Variable Text", "Segoe UI", sans-serif; user-select: none; }
button { font: inherit; color: inherit; background: none; border: none; cursor: pointer; padding: 0; }
input { font: inherit; }
.widget { display: flex; flex-direction: column; height: 100%; border: 1px solid var(--borde); }

.barra { display: flex; align-items: center; gap: 6px; padding: 10px 10px 8px 12px; }
.pestanas { display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none; max-width: 220px; }
.pestana { padding: 6px 12px; border-radius: 999px; font-size: 12px; color: var(--texto-2); white-space: nowrap;
  transition: background .15s, color .15s; }
.pestana:hover { color: var(--texto); }
.pestana.activa { background: var(--superficie-2); color: #fff; }
.arrastre { flex: 1; align-self: stretch; min-width: 16px; }
.btn-icono { width: 26px; height: 26px; border-radius: 8px; color: var(--texto-2); font-size: 14px; flex: none; }
.btn-icono:hover { background: var(--superficie-2); color: var(--texto); }

.indicador { display: flex; align-items: center; gap: 5px; font-size: 11px; color: var(--texto-2); white-space: nowrap; }
.indicador .punto { width: 7px; height: 7px; border-radius: 50%; background: #777; }
.indicador.bien .punto { background: var(--verde); }
.indicador.bajo { color: var(--ambar); }
.indicador.bajo .punto { background: var(--ambar); }
.indicador.mal { color: #fca5a5; }
.indicador.mal .punto { background: var(--rojo); }
.indicador.conectando .punto, .spinner { width: 12px; height: 12px; border-radius: 50%; background: transparent;
  border: 2px solid rgba(255, 255, 255, .2); border-top-color: #fff; animation: girar .8s linear infinite; flex: none; }
@keyframes girar { to { transform: rotate(360deg); } }

.vista { flex: 1; min-height: 0; position: relative; }
.vista > * { animation: aparecer .2s ease-out; }
@keyframes aparecer { from { opacity: 0; transform: translateY(4px); } }

.tarjeta { background: var(--superficie); border-radius: 12px; padding: 10px 12px; }
.etiqueta { display: flex; justify-content: space-between; margin-bottom: 6px; font-size: 11px; color: var(--texto-3);
  text-transform: uppercase; letter-spacing: .06em; }
.etiqueta .valor { color: var(--texto); font-size: 12px; font-weight: 600; letter-spacing: 0; text-transform: none; }
.btn { padding: 6px 10px; border-radius: 8px; background: var(--superficie-2); font-size: 12px; white-space: nowrap; }
.btn:hover { background: rgba(255, 255, 255, .12); }
.btn.primario { background: rgba(74, 222, 128, .18); color: var(--verde); font-weight: 600; }
.btn.peligro { background: rgba(248, 113, 113, .18); color: #fca5a5; }
.crece { flex: 1; }

.aviso { position: fixed; left: 14px; right: 14px; bottom: 14px; padding: 10px 12px; border-radius: 10px;
  background: #2c2c32; border: 1px solid var(--borde); font-size: 12px; opacity: 0; transform: translateY(8px);
  pointer-events: none; transition: opacity .2s, transform .2s; z-index: 10; }
.aviso.visible { opacity: 1; transform: none; }
.aviso.error { border-color: rgba(248, 113, 113, .4); color: #fca5a5; }

.vacio { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px;
  color: var(--texto-2); text-align: center; padding: 20px; }
.vacio-icono { font-size: 40px; opacity: .6; }

/* Pantalla de búsqueda */
.panel-busqueda { height: 100%; overflow-y: auto; padding-bottom: 14px; }
.cabecera { display: flex; align-items: center; gap: 8px; padding: 0 12px 4px; }
.estado-busqueda { display: flex; align-items: center; gap: 6px; font-size: 11px; color: var(--texto-2); }
.panel-busqueda h2 { margin: 8px 14px 4px; font-size: 16px; font-weight: 600; }
.seccion { margin: 12px 14px 6px; font-size: 11px; color: var(--texto-3); text-transform: uppercase; letter-spacing: .06em; }
.lista { display: flex; flex-direction: column; gap: 6px; padding: 0 10px; }
.dispositivo { display: flex; align-items: center; gap: 10px; padding: 10px; border-radius: 12px; background: var(--superficie); }
.dispositivo.editando { border-radius: 12px 12px 0 0; }
.icono-disp { width: 34px; height: 34px; border-radius: 10px; background: var(--superficie-2); display: flex;
  align-items: center; justify-content: center; font-size: 16px; flex: none; }
.info { flex: 1; min-width: 0; }
.info b { display: block; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.info small { color: var(--texto-2); font-size: 10px; }
.senal { display: inline-flex; gap: 1px; align-items: flex-end; height: 10px; margin-right: 4px; vertical-align: -1px; }
.senal i { width: 2px; background: #555; border-radius: 1px; }
.senal i:nth-child(1) { height: 3px; }
.senal i:nth-child(2) { height: 5px; }
.senal i:nth-child(3) { height: 8px; }
.senal i:nth-child(4) { height: 10px; }
.senal i.llena { background: var(--verde); }
.editor { margin-top: -6px; padding: 10px; border-radius: 0 0 12px 12px; background: rgba(74, 222, 128, .05);
  border: 1px solid rgba(74, 222, 128, .3); display: flex; flex-direction: column; gap: 8px; }
.editor input { background: rgba(0, 0, 0, .3); border: 1px solid var(--borde); border-radius: 8px; padding: 7px 9px;
  color: var(--texto); outline: none; user-select: text; }
.editor input:focus { border-color: rgba(74, 222, 128, .6); }
.botones { display: flex; justify-content: flex-end; gap: 6px; }
.mensaje { padding: 10px 4px; color: var(--texto-2); font-size: 12px; }
```

- [ ] **Step 4: Escribir `util.js` y `busqueda.js`**

`widget/ui/util.js`:
```js
"use strict";
// Ayudas comunes. Regla de seguridad: el texto se pone siempre con textContent (nunca innerHTML).
const util = {
  el(tag, clase, texto) {
    const e = document.createElement(tag);
    if (clase) e.className = clase;
    if (texto != null) e.textContent = texto;
    return e;
  },
  // Ejecuta fn como máximo cada `ms`; la última llamada siempre se ejecuta.
  limitar(fn, ms) {
    let ultimo = 0, pendiente = null;
    return (...args) => {
      const ahora = Date.now();
      clearTimeout(pendiente);
      if (ahora - ultimo >= ms) { ultimo = ahora; fn(...args); return; }
      pendiente = setTimeout(() => { ultimo = Date.now(); fn(...args); }, ms - (ahora - ultimo));
    };
  },
  rgb(c) { return `${c[0]},${c[1]},${c[2]}`; },
  aviso(texto, tipo = "info") {
    const a = document.getElementById("aviso");
    a.textContent = texto;
    a.className = `aviso visible ${tipo}`;
    clearTimeout(util._temporizador);
    util._temporizador = setTimeout(() => { a.className = "aviso"; }, 3500);
  },
};
```

`widget/ui/busqueda.js`:
```js
"use strict";
// Pantalla "Agregar dispositivo" (diseño: docs/superpowers/specs/maquetas/estados-y-busqueda.html).
function nivelSenal(rssi) { return rssi >= -70 ? 4 : rssi >= -80 ? 3 : rssi >= -90 ? 2 : 1; }

function barrasSenal(rssi) {
  const s = util.el("span", "senal");
  const nivel = nivelSenal(rssi);
  for (let i = 1; i <= 4; i++) s.append(util.el("i", i <= nivel ? "llena" : null));
  s.title = `${rssi} dBm`;
  return s;
}

class VistaBusqueda {
  constructor({ obtenerDispositivos, alVolver, alGuardado, alCambiar }) {
    Object.assign(this, { obtenerDispositivos, alVolver, alGuardado, alCambiar });
    this.buscando = false;
    this.raiz = util.el("section", "panel-busqueda");
    const cabecera = util.el("div", "cabecera");
    const volver = util.el("button", "btn", "← Volver");
    volver.addEventListener("click", () => this.alVolver());
    this.estado = util.el("span", "estado-busqueda");
    const otraVez = util.el("button", "btn", "Buscar de nuevo");
    otraVez.addEventListener("click", () => this.buscar());
    cabecera.append(volver, util.el("span", "crece"), this.estado, otraVez);
    this.guardados = util.el("div", "lista");
    this.encontrados = util.el("div", "lista");
    this.raiz.append(cabecera, util.el("h2", null, "Agregar dispositivo"),
      util.el("div", "seccion", "Guardados"), this.guardados,
      util.el("div", "seccion", "Encontrados cerca"), this.encontrados);
    this.pintarGuardados();
  }

  async buscar() {
    if (this.buscando) return;
    this.buscando = true;
    this.estado.replaceChildren(util.el("span", "spinner"), util.el("span", null, "buscando…"));
    this.encontrados.replaceChildren();
    let r;
    try { r = await pywebview.api.buscar(); } catch (e) { r = { ok: false, error: "fallo" }; }
    this.buscando = false;
    this.estado.replaceChildren();
    if (!r.ok) {
      this.mensaje(this.encontrados, r.error === "sin_bluetooth"
        ? "Activá el Bluetooth de Windows y buscá de nuevo." : "No se pudo buscar. Probá de nuevo.");
      return;
    }
    const nuevos = r.encontrados.filter((s) => !s.guardado);
    if (!nuevos.length) {
      this.mensaje(this.encontrados, "No encontré sables nuevos. ¿Está encendido, cerca y sin el teléfono conectado?");
      return;
    }
    this.encontrados.replaceChildren(...nuevos.map((s) => this.filaEncontrado(s)));
  }

  mensaje(lista, texto) { lista.replaceChildren(util.el("div", "mensaje", texto)); }

  fila(icono, titulo, detalle) {
    const f = util.el("div", "dispositivo");
    const info = util.el("div", "info");
    const small = util.el("small");
    if (detalle instanceof Node) small.append(detalle); else small.textContent = detalle;
    info.append(util.el("b", null, titulo), small);
    f.append(util.el("div", "icono-disp", icono), info);
    return f;
  }

  filaEncontrado(s) {
    const detalle = util.el("span");
    detalle.append(barrasSenal(s.rssi), document.createTextNode(` Xeno3 · Bluetooth · ${s.direccion}`));
    const f = this.fila("⚔", s.nombre, detalle);
    const agregar = util.el("button", "btn primario", "＋ Agregar");
    agregar.addEventListener("click", () => this.editar(f, "Mi sable", async (nombre) => {
      const r = await pywebview.api.guardar_dispositivo(s.direccion, nombre);
      if (!r.ok) { util.aviso(r.error, "error"); return false; }
      await this.alGuardado(r.dispositivo.id);
      return true;
    }));
    f.append(agregar);
    return f;
  }

  pintarGuardados() {
    const lista = this.obtenerDispositivos();
    if (!lista.length) { this.mensaje(this.guardados, "Ninguno todavía."); return; }
    this.guardados.replaceChildren(...lista.map((d) => {
      const f = this.fila("⚔", d.nombre, `Xeno3 · ${d.direccion}`);
      const renombrar = util.el("button", "btn-icono", "✎");
      renombrar.title = "Renombrar";
      renombrar.addEventListener("click", () => this.editar(f, d.nombre, async (nombre) => {
        const r = await pywebview.api.renombrar_dispositivo(d.id, nombre);
        if (!r.ok) { util.aviso(r.error, "error"); return false; }
        await this.alCambiar();
        this.pintarGuardados();
        return true;
      }));
      const quitar = util.el("button", "btn-icono", "✕");
      quitar.title = "Quitar";
      quitar.addEventListener("click", () => this.confirmarQuitar(f, d));
      f.append(renombrar, quitar);
      return f;
    }));
  }

  editar(fila, nombreInicial, alGuardar) {
    if (fila.classList.contains("editando")) return;
    const editor = util.el("div", "editor");
    const input = util.el("input");
    input.value = nombreInicial;
    input.maxLength = 40;
    input.placeholder = "Nombre";
    const cancelar = util.el("button", "btn", "Cancelar");
    const guardar = util.el("button", "btn primario", "Guardar");
    const botones = util.el("div", "botones");
    botones.append(cancelar, guardar);
    editor.append(input, botones);
    fila.after(editor);
    fila.classList.add("editando");
    input.focus();
    input.select();
    const cerrar = () => { editor.remove(); fila.classList.remove("editando"); };
    const confirmar = async () => { if (await alGuardar(input.value)) cerrar(); };
    cancelar.addEventListener("click", cerrar);
    guardar.addEventListener("click", confirmar);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") confirmar();
      if (e.key === "Escape") { e.stopPropagation(); cerrar(); }
    });
  }

  confirmarQuitar(fila, d) {
    if (fila.classList.contains("editando")) return;
    const caja = util.el("div", "editor");
    caja.append(util.el("span", null, `¿Quitar "${d.nombre}"?`));
    const no = util.el("button", "btn", "No");
    const si = util.el("button", "btn peligro", "Quitar");
    const botones = util.el("div", "botones");
    botones.append(no, si);
    caja.append(botones);
    fila.after(caja);
    fila.classList.add("editando");
    no.addEventListener("click", () => { caja.remove(); fila.classList.remove("editando"); });
    si.addEventListener("click", async () => {
      await pywebview.api.quitar_dispositivo(d.id);
      await this.alCambiar();
      this.pintarGuardados();
    });
  }
}
```

- [ ] **Step 5: Escribir `app.js` (con una vista básica que la tarea 9 reemplaza)**

`widget/ui/app.js`:
```js
"use strict";
// Estado global de la ventana, pestañas, indicador y eventos que llegan desde Python.
const app = { dispositivos: [], activo: null, vistas: new Map(), modo: "dispositivo", listo: false };

// Vista mínima de un dispositivo. La tarea 9 la reemplaza por VistaSable (misma interfaz).
class VistaBasica {
  constructor(d) {
    this.d = d;
    this.estadoConexion = d.conexion;
    this.raiz = util.el("section", "vacio");
    this.texto = util.el("p");
    this.raiz.append(util.el("div", "vacio-icono", "⚔"), util.el("b", null, d.nombre), this.texto);
    this.conexion({ estado: d.conexion });
  }
  estadoRecibido() {}
  errorRecibido() {}
  fuentesRecibidas() {}
  conexion(info) { this.estadoConexion = info.estado; this.texto.textContent = `Conexión: ${info.estado}`; }
  indicador() { return { texto: this.estadoConexion, clase: this.estadoConexion === "conectado" ? "bien" : "espera" }; }
}

function crearVista(d) { return new VistaBasica(d); }

async function recargarDatos() {
  const datos = await pywebview.api.inicial();
  app.dispositivos = datos.dispositivos;
  app.vistas = new Map(app.dispositivos.map((d) => [d.id, crearVista(d)]));
  if (!app.dispositivos.some((d) => d.id === app.activo)) app.activo = app.dispositivos[0]?.id ?? null;
}

function pintarPestanas() {
  const nav = document.getElementById("pestanas");
  nav.replaceChildren(...app.dispositivos.map((d) => {
    const activa = app.modo === "dispositivo" && d.id === app.activo;
    const b = util.el("button", "pestana" + (activa ? " activa" : ""), `⚔ ${d.nombre}`);
    b.addEventListener("click", () => mostrarDispositivo(d.id));
    return b;
  }));
}

function pintarIndicador() {
  const ind = document.getElementById("indicador");
  const vista = app.modo === "dispositivo" && app.activo ? app.vistas.get(app.activo) : null;
  if (!vista) { ind.className = "indicador"; ind.replaceChildren(); return; }
  const { texto, clase } = vista.indicador();
  ind.className = `indicador ${clase}`;
  ind.replaceChildren(util.el("span", "punto"), util.el("span", null, texto));
}

function vistaVacia() {
  const c = util.el("div", "vacio");
  const b = util.el("button", "btn primario", "Buscar dispositivos");
  b.addEventListener("click", mostrarBusqueda);
  c.append(util.el("div", "vacio-icono", "⚔"), util.el("p", null, "Todavía no agregaste dispositivos."), b);
  return c;
}

function mostrarDispositivo(id) {
  app.modo = "dispositivo";
  app.activo = id;
  const vista = id ? app.vistas.get(id) : null;
  document.getElementById("vista").replaceChildren(vista ? vista.raiz : vistaVacia());
  pintarPestanas();
  pintarIndicador();
}

function mostrarBusqueda() {
  app.modo = "busqueda";
  const busqueda = new VistaBusqueda({
    obtenerDispositivos: () => app.dispositivos,
    alVolver: () => mostrarDispositivo(app.activo),
    alGuardado: async (id) => { await recargarDatos(); mostrarDispositivo(id); },
    alCambiar: recargarDatos,
  });
  document.getElementById("vista").replaceChildren(busqueda.raiz);
  pintarPestanas();
  pintarIndicador();
  busqueda.buscar();
}

window.deskControl = {
  recibir(evento) {
    const vista = app.vistas.get(evento.id);
    if (!vista) return;
    if (evento.tipo === "estado") vista.estadoRecibido(evento.datos);
    else if (evento.tipo === "conexion") vista.conexion(evento.datos);
    else if (evento.tipo === "error") vista.errorRecibido(evento.datos);
    else if (evento.tipo === "fuentes") vista.fuentesRecibidas(evento.datos);
    pintarIndicador();
  },
  abrirBusqueda() { if (app.listo) mostrarBusqueda(); },
};

window.addEventListener("pywebviewready", async () => {
  document.getElementById("btn-ocultar").addEventListener("click", () => pywebview.api.ocultar());
  document.getElementById("btn-agregar").addEventListener("click", mostrarBusqueda);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !document.querySelector(".popover.abierto, .editor")) pywebview.api.ocultar();
  });
  await recargarDatos();
  app.listo = true;
  mostrarDispositivo(app.activo);
});
```

- [ ] **Step 6: Correr las pruebas automáticas (no deben romperse)**

Run: `.venv/Scripts/python -m pytest tests/ -v`
Expected: PASS (todas).

- [ ] **Step 7: Verificación manual del widget**

Run: `.venv/Scripts/python -m widget --debug`

Comprobar, con el iPhone sin Bluetooth y el sable encendido:
1. Aparece una ventana oscura de 380×600 **sin bordes y con esquinas redondeadas**, arriba a la izquierda del monitor vertical. Si aparece en otro lugar o con otro tamaño (por escalado DPI), moverla a mano: debe recordar la posición al reabrir.
2. Se arrastra desde la zona vacía de la barra superior.
3. Sin dispositivos se ve "Todavía no agregaste dispositivos". **Buscar dispositivos** muestra "buscando…" y luego el `Saber` con barras de señal.
4. **＋ Agregar** → nombre "Mi sable" → **Guardar**: aparece la pestaña "⚔ Mi sable" con "Conexión: espera".
5. En la búsqueda, renombrar a `<b>prueba</b>`: debe verse el texto literal (no en negrita). Luego volver a "Mi sable".
6. **Ctrl+Shift+Espacio** oculta el widget; otra vez lo muestra. Con otra ventana encima, el atajo lo **trae al frente** en vez de ocultarlo.
7. El icono de la bandeja (sable verde): "Mostrar / ocultar", "Agregar dispositivo" (abre la búsqueda) e "Iniciar con Windows" (marcado). **Salir** cierra todo.
8. Abrir dos veces `.venv/Scripts/python -m widget`: la segunda no abre nada.
9. En `regedit`, `HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run\DeskControl` contiene `pythonw.exe … desk_control.pyw" --oculto`.
10. Con `--debug`, clic derecho → Inspeccionar → Consola: sin errores de CSP ni de JavaScript.

Si bleak falla con un error sobre "STA" o "apartment" al buscar, agregar al principio de `main()` en `widget/main.py`:
```python
    from bleak.backends.winrt.util import uninitialize_sta
    uninitialize_sta()
```
y repetir la verificación.

- [ ] **Step 8: Commit**

```bash
git add widget/main.py widget/__main__.py desk_control.pyw widget/ui
git commit -m "Ventana del widget con bandeja, atajo, autoarranque y pantalla de búsqueda" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 9: Panel del sable

**Files:**
- Create: `widget/ui/sable.css`, `widget/ui/rueda.js`, `widget/ui/sable.js`
- Modify: `widget/ui/index.html` (enlazar `sable.css`, `rueda.js` y `sable.js`)
- Modify: `widget/ui/app.js` (quitar `VistaBasica`; `crearVista` devuelve `new VistaSable(d)`)

**Interfaces:**
- Consumes:
  - `util` y `pintarIndicador()` (tarea 8).
  - `pywebview.api.sable_enviar`, `sable_fuentes` y `sable_reintentar` (tarea 6).
  - Forma del dispositivo `{id, nombre, conexion, estado, fuentes}` (tarea 6).
- Produces:
  - `colorEnRueda(dx, dy, radio) -> [r, g, b]` y `crearRueda({alCambiar, alConfirmar}) -> HTMLElement`.
  - `class VistaSable(dispositivo)`, con la interfaz de vista de la tarea 8.

- [ ] **Step 1: Escribir los estilos del panel**

`widget/ui/sable.css`:
```css
/* Panel del sable (diseño aprobado: docs/superpowers/specs/maquetas/pestana-sable.html). --c = color de la hoja. */
.panel-sable { --c: 0, 255, 0; display: flex; flex-direction: column; height: 100%; position: relative; }

.banner { display: none; margin: 0 14px 8px; padding: 8px 10px; border-radius: 10px; font-size: 12px;
  background: var(--superficie); align-items: center; gap: 8px; justify-content: space-between; }
.banner.visible { display: flex; }
.banner.mal { background: rgba(248, 113, 113, .12); color: #fca5a5; }
.banner.mal small { color: var(--texto-2); display: block; }
.banner.bajo { background: rgba(251, 191, 36, .12); color: #fcd34d; }

.escenario { display: flex; gap: 14px; padding: 4px 14px 14px; flex: 1; min-height: 0; }
.sable { width: 64px; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; }
.hoja { width: 9px; flex: 1; max-height: 380px; border-radius: 999px; background: #fff; transform-origin: bottom;
  transform: scaleY(0); opacity: 0; transition: transform .35s cubic-bezier(.2, .8, .2, 1), opacity .2s, box-shadow .3s;
  box-shadow: 0 0 6px 2px rgba(var(--c), .9), 0 0 22px 6px rgba(var(--c), .55), 0 0 60px 14px rgba(var(--c), .25); }
.encendido .hoja { transform: scaleY(1); opacity: 1; animation: zumbido 2.4s ease-in-out infinite; }
@keyframes zumbido {
  50% { box-shadow: 0 0 7px 2px rgba(var(--c), 1), 0 0 26px 8px rgba(var(--c), .6), 0 0 70px 18px rgba(var(--c), .3); }
}
[data-conexion="conectando"] .hoja { transform: scaleY(1); opacity: 1; background: transparent; box-shadow: none;
  border: 1px solid rgba(var(--c), .5); animation: respirar 1.4s ease-in-out infinite; }
@keyframes respirar { 50% { border-color: rgba(var(--c), .1); box-shadow: 0 0 14px rgba(var(--c), .25); } }
.mango { display: flex; flex-direction: column; align-items: center; }
.emisor { width: 22px; height: 16px; border-radius: 3px 3px 2px 2px; background: linear-gradient(90deg, #4a4a50, #b8b8c0 45%, #55555b); }
.grip { width: 18px; height: 70px; background: repeating-linear-gradient(180deg, #2b2b30 0 5px, #16161a 5px 8px);
  border-left: 1px solid #44444a; border-right: 1px solid #111; }
.pomo { width: 20px; height: 22px; border-radius: 2px 2px 6px 6px; background: linear-gradient(90deg, #3a3a3f, #8d8d95 45%, #4a4a50); }

.controles { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 0; transition: opacity .2s; }
[data-conexion="conectando"] .controles { opacity: .55; }
.fila-centro { display: flex; justify-content: center; padding: 4px 0; }
.pwr { width: 58px; height: 58px; border-radius: 50%; font-size: 24px; background: var(--superficie-2); color: var(--texto-2); transition: all .3s; }
.encendido .pwr { background: rgba(var(--c), .18); color: rgb(var(--c)); box-shadow: 0 0 18px rgba(var(--c), .45); }

.muestras { display: flex; gap: 9px; flex-wrap: wrap; }
.muestra { width: 24px; height: 24px; border-radius: 50%; transition: transform .15s, box-shadow .15s; }
.muestra:hover { transform: scale(1.15); }
.muestra.elegida { box-shadow: 0 0 0 2px var(--fondo), 0 0 0 4px #fff; }
.arcoiris { background: conic-gradient(red, yellow, lime, cyan, blue, magenta, red); }
input[type=range] { width: 100%; accent-color: rgb(var(--c)); }

.fuente { display: flex; align-items: center; gap: 6px; }
.flecha { width: 28px; height: 28px; border-radius: 8px; background: var(--superficie-2); flex: none; }
.nombre-fuente { flex: 1; min-width: 0; text-align: center; border-radius: 8px; padding: 2px 0; line-height: 1.3; }
.nombre-fuente:hover { background: var(--superficie); }
.nombre-fuente b { font-size: 14px; font-weight: 600; }
.nombre-fuente small { color: var(--texto-2); font-size: 11px; }
.flechita { color: var(--texto-2); font-size: 11px; }

.popover { position: absolute; left: 92px; right: 14px; background: #26262b; border: 1px solid var(--borde);
  border-radius: 14px; box-shadow: 0 16px 40px rgba(0, 0, 0, .6); padding: 12px; z-index: 5; opacity: 0;
  transform: translateY(-6px) scale(.98); pointer-events: none; transition: opacity .18s ease-out, transform .18s ease-out; }
.popover.abierto { opacity: 1; transform: none; pointer-events: auto; }
.rueda-pop { top: 150px; }
.rueda { width: 190px; height: 190px; border-radius: 50%; margin: 4px auto 10px; cursor: crosshair; position: relative;
  touch-action: none; background: radial-gradient(circle, #fff 0%, rgba(255, 255, 255, 0) 70%),
  conic-gradient(from 90deg, red, yellow, lime, cyan, blue, magenta, red); }
.perilla { position: absolute; left: 50%; top: 50%; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #fff;
  box-shadow: 0 0 4px #000; transform: translate(-50%, -50%); pointer-events: none; }
.rueda-pie { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--texto-2); }
.rueda-pie .previa { width: 18px; height: 18px; border-radius: 50%; background: #fff; }
.lista-fuentes { bottom: 72px; max-height: 340px; overflow-y: auto; }
.item-fuente { display: flex; gap: 10px; width: 100%; padding: 7px 10px; border-radius: 8px; font-size: 13px; text-align: left; }
.item-fuente:hover { background: var(--superficie-2); }
.item-fuente.actual { background: rgba(var(--c), .15); color: #fff; }
.item-fuente small { color: var(--texto-3); width: 18px; text-align: right; flex: none; }
.item-fuente.refrescar { color: var(--texto-2); margin-top: 4px; }
.cargando { padding: 10px; color: var(--texto-2); font-size: 12px; }
```

- [ ] **Step 2: Escribir la rueda de color**

`widget/ui/rueda.js`:
```js
"use strict";
// Rueda de color: el ángulo es el tono (rojo a la derecha, sentido horario) y la distancia al centro la saturación.
function colorEnRueda(dx, dy, radio) {
  const d = Math.min(1, Math.hypot(dx, dy) / radio);
  const h = ((((Math.atan2(dy, dx) * 180) / Math.PI) + 360) % 360) / 60;
  const x = 1 - Math.abs((h % 2) - 1);
  const base = [[1, x, 0], [x, 1, 0], [0, 1, x], [0, x, 1], [x, 0, 1], [1, 0, x]][Math.floor(h) % 6];
  return base.map((v) => Math.round(255 * (v * d + (1 - d))));
}

// alCambiar(color) se llama mientras se arrastra (vista previa); alConfirmar(color, cerrar) al soltar o con "Listo".
function crearRueda({ alCambiar, alConfirmar }) {
  const caja = util.el("div", "popover rueda-pop");
  const rueda = util.el("div", "rueda");
  const perilla = util.el("div", "perilla");
  rueda.append(perilla);
  const previa = util.el("span", "previa");
  const texto = util.el("span", null, "Tocá o arrastrá");
  const listo = util.el("button", "btn", "Listo");
  const pie = util.el("div", "rueda-pie");
  pie.append(previa, texto, util.el("span", "crece"), listo);
  caja.append(util.el("div", "etiqueta", "Elegí cualquier color"), rueda, pie);

  let color = null;
  let arrastrando = false;
  const mover = (e) => {
    const r = rueda.getBoundingClientRect();
    const radio = r.width / 2;
    let dx = e.clientX - r.left - radio;
    let dy = e.clientY - r.top - radio;
    const distancia = Math.hypot(dx, dy);
    if (distancia > radio) { dx *= radio / distancia; dy *= radio / distancia; }
    perilla.style.left = `${50 + (dx / r.width) * 100}%`;
    perilla.style.top = `${50 + (dy / r.height) * 100}%`;
    color = colorEnRueda(dx, dy, radio);
    previa.style.background = `rgb(${util.rgb(color)})`;
    texto.textContent = `RGB ${color.join(", ")}`;
    alCambiar(color);
  };
  rueda.addEventListener("pointerdown", (e) => { arrastrando = true; rueda.setPointerCapture(e.pointerId); mover(e); });
  rueda.addEventListener("pointermove", (e) => { if (arrastrando) mover(e); });
  rueda.addEventListener("pointerup", () => { arrastrando = false; if (color) alConfirmar(color, false); });
  listo.addEventListener("click", () => alConfirmar(color, true));
  return caja;
}
```

- [ ] **Step 3: Escribir `VistaSable`**

`widget/ui/sable.js`:
```js
"use strict";
// Panel de un sable Xeno3: dibujo animado + controles. Cumple la interfaz de vista de app.js.
const COLORES_COMUNES = [
  [255, 0, 0], [0, 80, 255], [0, 255, 0], [160, 0, 255],
  [255, 230, 0], [255, 120, 0], [0, 220, 255], [255, 255, 255],
];
const INTENTOS_CONEXION = 3;
const BATERIA_BAJA = 20;

class VistaSable {
  constructor(dispositivo) {
    this.d = dispositivo;
    this.d.estado = this.d.estado || {};
    this.d.fuentes = this.d.fuentes || [];
    this.confirmado = { ...this.d.estado };  // último estado que confirmó el sable
    this.conexionActual = { estado: dispositivo.conexion || "espera" };
    this.arrastrando = null;
    this.ui = {};
    this.raiz = util.el("section", "panel-sable");
    this.construir();
    this.raiz.addEventListener("click", (e) => {
      if (!e.target.closest(".popover, .arcoiris, .nombre-fuente")) this.cerrarPopovers();
    });
    this.pintar();
    this.pintarConexion();
  }

  // ---- construcción ----
  construir() {
    this.ui.banner = util.el("div", "banner");
    const escenario = util.el("div", "escenario");

    const sable = util.el("div", "sable");
    const mango = util.el("div", "mango");
    mango.append(util.el("div", "emisor"), util.el("div", "grip"), util.el("div", "pomo"));
    sable.append(util.el("div", "hoja"), mango);

    const controles = util.el("div", "controles");
    const filaPwr = util.el("div", "fila-centro");
    this.ui.pwr = util.el("button", "pwr", "⏻");
    this.ui.pwr.title = "Encender / apagar la hoja";
    this.ui.pwr.addEventListener("click", () => this.enviar("PowerOn", !this.d.estado.PowerOn));
    filaPwr.append(this.ui.pwr);
    controles.append(filaPwr, this.tarjetaColor(), this.deslizador("Volume", "Volumen"),
      this.deslizador("Brightness", "Brillo"), this.tarjetaFuente());
    escenario.append(sable, controles);

    this.ui.rueda = crearRueda({
      alCambiar: (c) => this.raiz.style.setProperty("--c", util.rgb(c)),
      alConfirmar: (c, cerrar) => {
        if (c) this.enviar("BackgroundColor", c);
        if (cerrar) this.cerrarPopovers();
      },
    });
    this.ui.lista = util.el("div", "popover lista-fuentes");
    this.raiz.append(this.ui.banner, escenario, this.ui.rueda, this.ui.lista);
  }

  tarjetaColor() {
    const t = util.el("div", "tarjeta");
    const muestras = util.el("div", "muestras");
    this.ui.muestras = COLORES_COMUNES.map((c) => {
      const m = util.el("button", "muestra");
      m.style.background = `rgb(${util.rgb(c)})`;
      m.title = `RGB ${c.join(", ")}`;
      m.addEventListener("click", () => this.enviar("BackgroundColor", c));
      muestras.append(m);
      return { el: m, color: c };
    });
    const arcoiris = util.el("button", "muestra arcoiris");
    arcoiris.title = "Cualquier color";
    arcoiris.addEventListener("click", () => this.alternarPopover(this.ui.rueda));
    muestras.append(arcoiris);
    t.append(util.el("div", "etiqueta", "Color"), muestras);
    return t;
  }

  deslizador(clave, titulo) {
    const t = util.el("div", "tarjeta");
    const etiqueta = util.el("div", "etiqueta");
    const valor = util.el("b", "valor");
    etiqueta.append(util.el("span", null, titulo), valor);
    const input = util.el("input");
    input.type = "range";
    input.min = "0";
    input.max = "100";
    const enviarLimitado = util.limitar((v) => this.enviar(clave, v), 150);
    input.addEventListener("input", () => {
      this.arrastrando = clave;
      valor.textContent = `${input.value}%`;
      enviarLimitado(Number(input.value));
    });
    input.addEventListener("change", () => {
      this.arrastrando = null;
      this.enviar(clave, Number(input.value));
    });
    t.append(etiqueta, input);
    this.ui[clave] = { input, valor };
    return t;
  }

  tarjetaFuente() {
    const t = util.el("div", "tarjeta fuente");
    const anterior = util.el("button", "flecha", "‹");
    const siguiente = util.el("button", "flecha", "›");
    const nombre = util.el("button", "nombre-fuente");
    nombre.title = "Ver todas las fuentes";
    this.ui.fuenteNombre = util.el("b");
    this.ui.fuenteNumero = util.el("small");
    nombre.append(this.ui.fuenteNombre, util.el("span", "flechita", " ▾"), util.el("br"), this.ui.fuenteNumero);
    anterior.addEventListener("click", () => this.moverFuente(-1));
    siguiente.addEventListener("click", () => this.moverFuente(1));
    nombre.addEventListener("click", () => this.abrirListaFuentes());
    t.append(anterior, nombre, siguiente);
    return t;
  }

  // ---- acciones ----
  async enviar(clave, valor) {
    this.d.estado[clave] = valor;  // vista optimista: se ve el cambio al instante
    this.pintar();
    let r;
    try { r = await pywebview.api.sable_enviar(this.d.id, clave, valor); } catch (e) { r = { ok: false, error: String(e) }; }
    if (!r.ok) {
      util.aviso(r.error || "No se pudo enviar", "error");
      this.revertir(clave);
    }
  }

  revertir(clave) {
    if (clave in this.confirmado) this.d.estado[clave] = this.confirmado[clave];
    else delete this.d.estado[clave];
    this.pintar();
  }

  totalFuentes() { return this.d.estado.TotalSoundPackage || this.d.fuentes.length || 0; }

  moverFuente(paso) {
    const total = this.totalFuentes();
    if (!total) return;
    const actual = this.d.estado.CurrentSoundPackageNo ?? 0;
    this.elegirFuente((actual + paso + total) % total);
  }

  elegirFuente(indice) {
    this.cerrarPopovers();
    if (this.d.fuentes[indice]) this.d.estado.fontname = this.d.fuentes[indice];
    this.enviar("CurrentSoundPackageNo", indice);
  }

  async abrirListaFuentes() {
    const abierta = this.alternarPopover(this.ui.lista);
    if (abierta && !this.d.fuentes.length) await this.cargarFuentes(false);
  }

  async cargarFuentes(refrescar) {
    this.ui.lista.replaceChildren(util.el("div", "cargando", "Leyendo fuentes del sable…"));
    let r;
    try { r = await pywebview.api.sable_fuentes(this.d.id, refrescar); } catch (e) { r = { ok: false }; }
    if (r.ok) this.fuentesRecibidas(r.fuentes);
    else this.ui.lista.replaceChildren(util.el("div", "cargando", r.error || "No se pudo leer la lista"));
  }

  pintarListaFuentes() {
    const actual = this.d.estado.CurrentSoundPackageNo;
    const items = this.d.fuentes.map((nombre, i) => {
      const item = util.el("button", "item-fuente" + (i === actual ? " actual" : ""));
      item.append(util.el("small", null, String(i + 1)), util.el("span", null, nombre));
      item.addEventListener("click", () => this.elegirFuente(i));
      return item;
    });
    const refrescar = util.el("button", "item-fuente refrescar", "↻ Volver a leer la lista");
    refrescar.addEventListener("click", () => this.cargarFuentes(true));
    this.ui.lista.replaceChildren(util.el("div", "etiqueta", "Fuentes en el sable"), ...items, refrescar);
  }

  alternarPopover(popover) {
    const abrir = !popover.classList.contains("abierto");
    this.cerrarPopovers();
    if (abrir) {
      popover.classList.add("abierto");
      if (popover === this.ui.lista && this.d.fuentes.length) this.pintarListaFuentes();
    }
    return abrir;
  }

  cerrarPopovers() {
    this.raiz.querySelectorAll(".popover.abierto").forEach((p) => p.classList.remove("abierto"));
    this.pintar();  // si se previsualizó un color sin confirmar, vuelve al real
  }

  // ---- eventos desde Python ----
  estadoRecibido(cambios) {
    Object.assign(this.confirmado, cambios);
    for (const [clave, valor] of Object.entries(cambios)) {
      if (clave !== this.arrastrando) this.d.estado[clave] = valor;
    }
    this.pintar();
    if ("Power" in cambios || "PowerOn" in cambios) this.pintarConexion();
  }

  errorRecibido({ clave, mensaje }) {
    util.aviso(clave ? `El sable rechazó ${clave}: ${mensaje}` : mensaje, "error");
    this.revertir(clave);
  }

  conexion(info) {
    this.conexionActual = info;
    this.d.conexion = info.estado;
    this.pintarConexion();
  }

  fuentesRecibidas(lista) {
    this.d.fuentes = lista;
    if (this.ui.lista.classList.contains("abierto")) this.pintarListaFuentes();
    this.pintar();
  }

  indicador() {
    const estado = this.conexionActual.estado;
    const bateria = this.d.estado.Power;
    if (estado === "conectando") return { texto: "conectando", clase: "conectando" };
    if (estado === "no_encontrado") return { texto: "sin señal", clase: "mal" };
    if (estado === "sin_bluetooth") return { texto: "sin Bluetooth", clase: "mal" };
    const texto = bateria == null ? (estado === "conectado" ? "conectado" : "en espera") : `🔋 ${bateria}%`;
    if (estado !== "conectado") return { texto, clase: "espera" };
    return { texto, clase: this.bateriaBaja() ? "bajo" : "bien" };
  }

  // Con la hoja encendida el voltaje cae y la lectura baja: solo se considera fiable con la hoja apagada.
  bateriaBaja() {
    const e = this.d.estado;
    return e.Power != null && e.Power < BATERIA_BAJA && !e.PowerOn;
  }

  // ---- pintado ----
  pintar() {
    const e = this.d.estado;
    const color = Array.isArray(e.BackgroundColor) ? e.BackgroundColor : [0, 255, 0];
    this.raiz.style.setProperty("--c", util.rgb(color));
    this.raiz.classList.toggle("encendido", !!e.PowerOn);
    for (const m of this.ui.muestras) m.el.classList.toggle("elegida", m.color.join() === color.join());
    for (const clave of ["Volume", "Brightness"]) {
      const { input, valor } = this.ui[clave];
      if (clave === this.arrastrando) continue;
      if (e[clave] != null) input.value = e[clave];
      valor.textContent = e[clave] == null ? "–" : `${e[clave]}%`;
    }
    const n = e.CurrentSoundPackageNo;
    const total = this.totalFuentes();
    this.ui.fuenteNombre.textContent = (n != null && this.d.fuentes[n]) || e.fontname || "Fuente";
    this.ui.fuenteNumero.textContent = n == null ? "" : `Fuente ${n + 1}${total ? ` de ${total}` : ""}`;
  }

  pintarConexion() {
    const { estado, intento } = this.conexionActual;
    this.raiz.dataset.conexion = estado;
    const b = this.ui.banner;
    b.className = "banner";
    b.replaceChildren();
    if (estado === "conectando") {
      b.classList.add("visible");
      b.append(util.el("span", "spinner"), util.el("span", "crece", `Conectando… intento ${intento || 1} de ${INTENTOS_CONEXION}`));
    } else if (estado === "no_encontrado") {
      b.classList.add("visible", "mal");
      const texto = util.el("div");
      texto.append(util.el("div", null, "No encontré el sable."),
        util.el("small", null, "¿Está encendido y cerca? ¿Conectado al iPhone?"));
      const reintentar = util.el("button", "btn", "Reintentar");
      reintentar.addEventListener("click", () => pywebview.api.sable_reintentar(this.d.id));
      b.append(texto, reintentar);
    } else if (estado === "sin_bluetooth") {
      b.classList.add("visible", "mal");
      b.append(util.el("span", null, "Activá el Bluetooth de Windows y volvé a intentar."));
    } else if (estado === "conectado" && this.bateriaBaja()) {
      b.classList.add("visible", "bajo");
      b.append(util.el("span", null, "🔋 Batería baja: cargá el sable pronto"));
    }
    if (typeof pintarIndicador === "function") pintarIndicador();
  }
}
```

- [ ] **Step 4: Conectar el panel en `index.html` y `app.js`**

En `widget/ui/index.html`, agregar después de `<link rel="stylesheet" href="estilos.css">`:
```html
<link rel="stylesheet" href="sable.css">
```
y reemplazar el bloque de scripts por:
```html
<script src="util.js"></script>
<script src="rueda.js"></script>
<script src="sable.js"></script>
<script src="busqueda.js"></script>
<script src="app.js"></script>
```

En `widget/ui/app.js`, borrar toda la clase `VistaBasica` (incluido su comentario) y reemplazar
```js
function crearVista(d) { return new VistaBasica(d); }
```
por
```js
function crearVista(d) { return new VistaSable(d); }
```

- [ ] **Step 5: Correr las pruebas automáticas (no deben romperse)**

Run: `.venv/Scripts/python -m pytest tests/ -v`
Expected: PASS (todas).

- [ ] **Step 6: Verificación manual con el sable real**

Run: `.venv/Scripts/python -m widget --debug` (sable encendido, iPhone sin Bluetooth, con "Mi sable" guardado de la tarea 8).

1. **En espera:** sin conectar, muestra los últimos valores (color, volumen y brillo con %, fuente) e indicador gris `🔋 NN%` o "en espera".
2. **⏻:** banner "Conectando… intento 1 de 3", la silueta de la hoja respira y los controles se atenúan. Al conectar, la hoja **crece con animación** y **el sable real se enciende**. Otro ⏻ la apaga (y el sable anuncia la desconexión del controlador).
3. **Colores comunes:** cada uno cambia la hoja dibujada y la real. El color elegido queda marcado con un anillo.
4. **🌈:** se abre la rueda. Al arrastrar, la hoja dibujada cambia en vivo; al soltar, cambia el sable real. "Listo" cierra la rueda. Clic fuera la cierra sin cambiar nada si no se soltó sobre la rueda.
5. **Volumen y brillo:** el % se actualiza al arrastrar; el sable cambia de volumen y brillo sin retrasos acumulados.
6. **Fuentes:** ‹ › cambian de fuente (el sable suena distinto y la hoja toma el color de esa fuente). El nombre con ▾ abre la lista de 16 con la actual resaltada; un clic cambia. "↻ Volver a leer la lista" la vuelve a pedir.
7. **Inactividad:** sin tocar nada 60 s, el indicador pasa a "en espera" (y el iPhone vuelve a poder conectarse).
8. **No encontrado:** con el sable apagado, tocar ⏻ → tras 3 intentos aparece "No encontré el sable" con **Reintentar**.
9. **Sin Bluetooth:** con el Bluetooth de Windows apagado, tocar algo → "Activá el Bluetooth de Windows…".
10. Consola de DevTools sin errores.

- [ ] **Step 7: Commit**

```bash
git add widget/ui
git commit -m "Panel del sable: hoja animada, colores con rueda, volumen, brillo y fuentes" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```

---

### Task 10: Medición de consumo, documentación y cierre de la etapa 1

**Files:**
- Create: `scripts/medir_consumo.ps1`
- Modify: `README.md` (sección "Usar el widget")
- Modify: `NOTAS.md` (pendientes de la etapa 1)

**Interfaces:**
- Consumes: el widget completo (tareas 1–9).
- Produces: medición de RAM y CPU documentada en `NOTAS.md`.

- [ ] **Step 1: Escribir el script de medición**

`scripts/medir_consumo.ps1`:
```powershell
# Suma la memoria (Working Set) y la CPU de Desk Control y de sus procesos WebView2 hijos.
# Uso: powershell -ExecutionPolicy Bypass -File scripts/medir_consumo.ps1
$todos = Get-CimInstance Win32_Process
$raiz = $todos | Where-Object { $_.CommandLine -like "*desk_control.pyw*" -or $_.CommandLine -like "*-m widget*" } | Select-Object -First 1
if (-not $raiz) { Write-Output "Desk Control no está corriendo."; exit 1 }
$ids = [System.Collections.Generic.List[int]]::new()
$ids.Add([int]$raiz.ProcessId)
for ($i = 0; $i -lt $ids.Count; $i++) {
    $todos | Where-Object { $_.ParentProcessId -eq $ids[$i] } | ForEach-Object { $ids.Add([int]$_.ProcessId) }
}
$antes = Get-Process -Id $ids -ErrorAction SilentlyContinue
$cpuAntes = ($antes | Measure-Object -Property CPU -Sum).Sum
Start-Sleep -Seconds 10
$despues = Get-Process -Id $ids -ErrorAction SilentlyContinue
$cpuDespues = ($despues | Measure-Object -Property CPU -Sum).Sum
$ramMB = ($despues | Measure-Object -Property WorkingSet64 -Sum).Sum / 1MB
$cpuPorc = ($cpuDespues - $cpuAntes) / 10 / [Environment]::ProcessorCount * 100
"Procesos: {0}   RAM: {1:N0} MB   CPU promedio (10 s): {2:N2} %" -f $despues.Count, $ramMB, $cpuPorc
```

- [ ] **Step 2: Medir**

Con el widget abierto (`.venv/Scripts/pythonw desk_control.pyw`), el sable guardado y sin tocar nada:

Run: `powershell -ExecutionPolicy Bypass -File scripts/medir_consumo.ps1`
Expected: `RAM:` menor que 200 MB y `CPU promedio` cerca de 0 % (menos de 0,5 %). Medir dos veces: con el widget **visible** y **oculto** (Ctrl+Shift+Espacio). Si la RAM supera 200 MB, anotarlo en NOTAS.md como pendiente con el valor medido (no bloquea el cierre).

- [ ] **Step 3: Actualizar README.md**

En `README.md`, reemplazar la línea `- 🛠️ Widget en desarrollo. Diseño: [docs/superpowers/specs/](docs/superpowers/specs/)` por `- ✅ Widget de escritorio para el sable (etapa 1). Diseño: [docs/superpowers/specs/](docs/superpowers/specs/)` y agregar al final:

````markdown
## Usar el widget

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/pythonw desk_control.pyw
```

- **Ctrl + Shift + Espacio** muestra u oculta el widget (se cambia en `%APPDATA%\DeskControl\config.json`).
- El icono de la bandeja permite agregar dispositivos, activar o desactivar el arranque con Windows y salir.
- La primera vez, tocá **Buscar dispositivos** con el sable encendido y sin el teléfono conectado.
- Registro de errores: `%APPDATA%\DeskControl\widget.log`.

Pruebas: `.venv/Scripts/python -m pip install -r requirements-dev.txt` y luego `.venv/Scripts/python -m pytest`.
````

- [ ] **Step 4: Actualizar NOTAS.md**

En `NOTAS.md`, reemplazar la línea `- [ ] Diseñar la app de control` por:
```markdown
- [x] Diseñar e implementar la etapa 1 del widget (sable). Consumo medido: RAM ___ MB visible / ___ MB oculto, CPU ___ %
- [ ] Etapa 2: focos Wiz (controles básicos, escenas, grupo "Cuarto")
- [ ] Mango de Obi-Wan detallado (a partir de fotos del sable real)
```
completando los `___` con los valores medidos en el paso 2.

- [ ] **Step 5: Correr todas las pruebas una última vez**

Run: `.venv/Scripts/python -m pytest tests/ -v`
Expected: PASS (todas).

- [ ] **Step 6: Commit**

```bash
git add scripts/medir_consumo.ps1 README.md NOTAS.md
git commit -m "Medición de consumo y documentación de la etapa 1" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
```
