# Widget de escritorio: etapa 1, sable Xeno3

**Fecha:** 2026-10-12 · **Estado:** diseño aprobado en conversación, pendiente de revisión escrita
**Referencias:** [PROTOCOLO.md](../../../PROTOCOLO.md) · maquetas aprobadas en [maquetas/](maquetas/)

## 1. Objetivo

Reemplazar la app oficial Xeno Configurator, que el usuario considera fea, poco práctica y vieja, por un
**widget de escritorio para Windows** lindo, fluido y con animaciones. Controla el sable Xeno3 por Bluetooth
y más adelante los focos Wiz del cuarto.

**Para quién:** un solo usuario, en su PC personal (Windows 11, 32 GB de RAM, monitor secundario vertical,
tema oscuro en todo el sistema). No se distribuye.

**Criterios de éxito:**
- Controla desde la PC el encendido, el color, el volumen, el brillo y la fuente del sable, sin abrir la app del teléfono.
- Se ve coherente con Windows 11 en tema oscuro, y el sable dibujado reacciona a cada cambio con animación.
- Consume menos de 200 MB de RAM y alrededor de 0 % de CPU en reposo.
- No abre puertos ni carga nada de internet.

## 2. Alcance

**Etapa 1 (este documento):**
- El widget, el icono en la bandeja del sistema, el atajo global, el arranque con Windows y el guardado de dispositivos.
- Pestaña del sable: encender y apagar la hoja, colores (comunes y rueda RGB), volumen y brillo con %,
  fuente (flechas y lista desplegable) y batería.
- Pantalla de búsqueda: encuentra sables, permite ponerles nombre, guardarlos y quitarlos.

**Fuera de alcance:**
- Etapa 2: focos Wiz (controles básicos, escenas y grupo "Cuarto").
- Más adelante: mango de Obi-Wan detallado (a partir de fotos del usuario), disparar efectos, ajustes avanzados,
  sincronizar los focos con el sable y acceso desde el teléfono.
- **Nunca:** `Reset`, `HardwareType`, `SoftwareType`, `ButtonNum`, firmware (`FileTransfer` de `update*.bin`) ni `rm`.
  Estos comandos no se programan.

## 3. Arquitectura

Un solo proceso, organizado en tres capas:

```
Ventana (HTML/CSS/JS en WebView2 vía pywebview)
   ↕  puente js_api de pywebview (dentro del proceso, sin red)
Motor Python
   ├─ dispositivos/xeno.py      controlador del sable (protocolo de PROTOCOLO.md)
   ├─ dispositivos/sesion.py    conexión a demanda: cola, reintentos, desconexión por inactividad
   ├─ config.py                 dispositivos guardados y caché (JSON en %APPDATA%)
   └─ escritorio/               bandeja (pystray), atajo global (RegisterHotKey vía ctypes), autoarranque
```

- **Tecnología:** Python 3.12, `bleak` (BLE), `pywebview` (WebView2), `pystray` y `Pillow` (bandeja).
  La interfaz se escribe en HTML, CSS y JS sin frameworks, y todos los recursos van incluidos en el programa (nada de CDN).
- **Hilos:** la ventana corre en el hilo principal (lo exige pywebview). Un hilo aparte ejecuta un bucle `asyncio`
  donde vive todo el Bluetooth. El puente le pasa órdenes a ese bucle (`run_coroutine_threadsafe`), y los cambios
  de estado se envían a la ventana con `window.run_js` como eventos.
- **Extensible:** cada tipo de dispositivo es un módulo con la misma interfaz:
  `conectar`, `enviar`, `estado` y `buscar`. Los focos Wiz se agregan en la etapa 2 sin tocar el código del sable.
- **Seguridad:** no hay servidor HTTP ni puertos abiertos. La ventana solo carga archivos locales del programa.
  En disco solo se guarda la configuración (`%APPDATA%\DeskControl\config.json`) y el registro de errores
  (`%APPDATA%\DeskControl\widget.log`). Las claves `HelloDamien` y `SaberOfDamien` son fijas del protocolo,
  no son credenciales del usuario.

## 4. Comportamiento en Windows

- **Ventana:** sin bordes, con esquinas redondeadas al estilo de Windows 11 y fondo oscuro sólido (`#1C1C20`; pywebview no soporta ventanas transparentes en Windows), de 380×600 px.
  Por defecto se ubica en la esquina superior izquierda del monitor vertical y recuerda la posición si el usuario la mueve.
  Se comporta como una ventana normal: otras ventanas pueden taparla.
- **Atajo global:** **Ctrl + Shift + Espacio** la muestra (y la trae al frente) o la oculta.
  Si otro programa ya lo usa, se avisa con una notificación y se puede cambiar en `config.json`.
- **Bandeja:** icono con las opciones Mostrar/Ocultar, Agregar dispositivo, "Iniciar con Windows" (activable) y Salir.
  Cerrar la ventana la oculta; no sale del programa.
- **Arranque con Windows:** activado por defecto. Arranca **oculto en la bandeja** (con una entrada en la clave `Run` de HKCU,
  que no requiere permisos de administrador).

## 5. Interfaz

Maquetas aprobadas: [`maquetas/pestana-sable.html`](maquetas/pestana-sable.html) y
[`maquetas/estados-y-busqueda.html`](maquetas/estados-y-busqueda.html).

**Barra superior:** una pestaña por dispositivo guardado, con el nombre que le puso el usuario (por ejemplo "Mi sable"),
el botón ＋ (búsqueda) y el indicador de estado y batería. La pestaña "Luces" **no aparece en la etapa 1**
(se agrega en la etapa 2).

**Pestaña del sable (disposición A):**
- A la izquierda, el sable vertical a todo el alto. La hoja se enciende o apaga con animación de crecimiento
  (unos 350 ms), toma el color elegido con un resplandor, y tiene un "zumbido" de brillo sutil mientras está encendida.
  El mango es genérico en la etapa 1 (el de Obi-Wan queda para después).
- A la derecha, en columna:
  - Botón ⏻, que brilla con el color de la hoja cuando está encendida.
  - **Color:** 8 colores comunes (rojo, azul, verde, violeta, amarillo, naranja, celeste y blanco) y el botón 🌈,
    que abre una ventanita con una **rueda RGB** (tono en el ángulo, saturación hacia el centro).
    La hoja muestra el color mientras se elige y se envía al soltar o al pulsar "Listo".
  - **Volumen** y **brillo:** deslizadores de 0 a 100 con el **valor en %** visible. Mientras se arrastra,
    se envía como máximo un valor cada 150 ms, y al soltar siempre se envía el valor final.
  - **Fuente:** flechas ‹ ›, más el nombre con ▾, que despliega la **lista completa** numerada con la fuente actual resaltada.

**Estados:**
1. **En espera** (sin conexión abierta): muestra los últimos valores conocidos, guardados en `config.json`.
   Todo se puede usar, y al tocar un control se conecta.
2. **Conectando:** la silueta de la hoja "respira", aparece "Conectando… intento n de 3" y los controles se atenúan.
   La orden pendiente se envía al conectar.
3. **No encontrado:** tras 3 intentos fallidos, un aviso con las causas típicas
   (apagado, lejos, conectado al teléfono) y el botón **Reintentar**.
4. **Conectado:** punto verde. Con **batería por debajo del 20 %**, indicador amarillo y aviso.
   La batería se toma como fiable solo con la hoja apagada.

**Pantalla "Agregar dispositivo":** una sección de guardados (con renombrar y quitar) y otra de encontrados cerca,
con barras de señal. Solo lista dispositivos compatibles (los que anuncian los servicios `dae0`/`3ab0`).
Al elegir uno se le pone nombre y se guarda.

## 6. Conexión con el sable (a demanda)

- La primera orden dispara la conexión: `connect` con timeout de 40 s, hasta 3 intentos y 2 s entre intentos.
  Luego el handshake por `dae1`, la autorización por `3ab1` y la lectura del estado completo.
  La secuencia está verificada en PROTOCOLO.md §3.
- Las órdenes van a una **cola** y se envían en orden. Las que llegan mientras se conecta esperan en ella.
- Si se pide varias veces el mismo valor seguido (por ejemplo, al arrastrar el volumen), solo se envía el último.
- **Desconexión automática a los 60 s** sin órdenes. No bloquea al iPhone y no impide que el sable se duerma.
- Las respuestas `[3,{...}]` (llegan por `dae1`) actualizan el estado y la interfaz.
  Un `[4,{...}]` muestra un aviso y vuelve el control al último valor confirmado.
- Si la conexión se corta de forma inesperada, el widget pasa a "en espera" sin perder los valores mostrados.

**Lista de fuentes (verificado):** `ls "/"` devuelve el rango de carpetas (`[1,16]`) y `fontname "/N"` el nombre
de cada una. Es solo lectura y tarda unos 3 s para 16 fuentes (ver `pruebas/listar_fuentes.py` y PROTOCOLO.md).
Se pide la primera vez que se conecta a un sable y se guarda en caché en `config.json`. Se puede refrescar a mano
y también se vuelve a pedir si `TotalSoundPackage` no coincide con la caché.
**Numeración:** `CurrentSoundPackageNo` cuenta desde 0 y las carpetas desde 1 (carpeta = n + 1).
La interfaz muestra la numeración desde 1, como las carpetas.

## 7. Errores

| Situación | Comportamiento |
|---|---|
| Bluetooth de Windows apagado o sin adaptador | Aviso "Activá el Bluetooth de Windows"; la búsqueda y el sable se desactivan |
| Sable no encontrado | Estado 3 (Reintentar) |
| Corte durante el uso | Vuelve a "en espera"; la próxima orden reconecta |
| Respuesta `4` (error) del sable | Aviso breve y el control vuelve al valor confirmado |
| Excepción inesperada | Se escribe en `widget.log`; la interfaz sigue funcionando |
| Atajo ocupado | Notificación; se puede cambiar en `config.json` |

El hilo de Bluetooth nunca bloquea la interfaz.

## 8. Pruebas

- **Automáticas (pytest), sin hardware:** un `SableSimulado` reproduce las respuestas reales capturadas en
  `logs/` (handshake en 3 partes, `AccessAllowed`, eco `[3,{clave:valor}]` y errores `4`).
  Cubren el armado de mensajes, la cola y la coalescencia, los reintentos, la desconexión por inactividad,
  la actualización de estado y que los comandos prohibidos no sean enviables.
- **Manual con el sable real:** una lista de pasos con encendido, colores comunes, rueda, volumen, brillo,
  fuentes (flechas y lista), desconexión por inactividad, el estado "no encontrado" (sable apagado) y la batería.
- **Consumo:** medir la RAM total (proceso más WebView2) y la CPU en reposo con el widget visible y oculto.
  El objetivo es menos de 200 MB y alrededor de 0 % de CPU.

## 9. Estructura de archivos

La estructura detallada está en el plan de implementación
(`docs/superpowers/plans/2026-10-12-widget-sable.md`). En resumen:

```
desk_control.pyw          lanzador (lo usa el arranque con Windows)
widget/
  main.py  bucle.py  puente.py  config.py  diagnostico.py
  dispositivos/  protocolo.py  transporte.py  xeno.py  sesion.py  busqueda.py
  escritorio/    atajo.py  instancia.py  autoarranque.py  ventana.py  bandeja.py
  ui/            index.html  estilos.css  sable.css  util.js  app.js  sable.js  rueda.js  busqueda.js
tests/           sable_simulado.py  ayudas.py  test_*.py
scripts/         medir_consumo.ps1
```

La "interfaz común de dispositivos" se materializa en la etapa 1 como `Transporte` (transporte.py) más
`SesionSable` (sesion.py). La interfaz genérica para varios tipos de dispositivo se extrae en la etapa 2,
cuando exista el segundo tipo (Wiz). Los dispositivos guardados viven en `config.py`.
