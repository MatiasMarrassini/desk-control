# Proyecto Xeno Configurator: notas de ingeniería inversa

## APK analizado
- Archivo: `Xeno.apk` (extraído con APK Extractor desde un Android)
- SHA-256: `6e0561c416c3781bc0f637cb5190a221e48c8e234c2fa957d951c9ea2971344e`
- Paquete Play: `com.xeno.configurator`, código interno `com.damien.damiensaber`
- App nativa Java/Kotlin (2 dex). Librería BLE: **FastBle** (`com.clj.fastble`)
- Otras librerías: Bugly (crash reports de Tencent), MMKV (almacenamiento), Glide, Lottie, RxJava3

## UUIDs BLE encontrados (pendiente de confirmar cuál es cuál)
| UUID | Hipótesis |
|---|---|
| `0000dae0-0000-1000-8000-00805f9b34fb` | Servicio (par dae0 / dae1) |
| `0000dae1-0000-1000-8000-00805f9b34fb` | Característica de datos |
| `00003ab0-0000-1000-8000-00805f9b34fb` | Servicio alternativo (¿otra versión de placa?) |
| `00003ab1-0000-1000-8000-00805f9b34fb` | Característica alternativa |
| `0000f00d-0000-1000-8000-00805f9b34fb` | ¿OTA / firmware? |
| `0000baad-0000-1000-8000-00805f9b34fb` | ¿OTA / firmware? |
| `00002902-0000-1000-8000-00805f9b34fb` | CCCD estándar (activar notificaciones) |

## Modelo de "efectos" (de un JSON por defecto embebido)
Los eventos de la placa se asignan a acciones de botón y movimiento:
- Eventos: ON, OFF, BATTERY, BGM, BLAST, BATTLE_ON/OFF, BLOCK_ON/OFF, CLASH,
  CC_END/SMOOTH/STEP/ZOOM, DRAG, FORCE, LAST_FONT, NEXT_FONT, LOCK_UP, LB, MELT,
  NEXT_LE, NEXT_MODE, THRUST, VOLUME
- Acciones: CLICK(count), PRESS(interval ms), HOLD(interval), MOTION
  (PUSHPULL push/pull, WAVE, ROTATE RL/LF, STRIKE), condiciones UP/DOWN/HORIZONTAL

## Estructura del proyecto
- `Xeno.apk`: APK original
- `herramientas/jadx/`: jadx 1.5.6 con Java incluido (GUI: `jadx-gui-1.5.6.exe`)
- `analisis/extraido/`: dex, manifiesto y textos extraídos
- `analisis/decompilado/`: código Java decompilado
- `PROTOCOLO.md`: **protocolo documentado**

## Pendiente
- [x] Decompilar con jadx y ubicar la clase que arma los mensajes
- [x] Documentar el formato de los comandos (ver PROTOCOLO.md)
- [x] Verificar UUIDs, handshake y autorización (desde la PC con bleak, 2026-10-12)
- [x] Probar comandos inofensivos: Volume, BackgroundColor y PowerOn funcionan
- [x] Ver si los cambios persisten sin `SaveCfg`: sí, se guardan solos
- [x] PowerOn=false y CurrentSoundPackageNo funcionan (el color es por fuente)
- [ ] Probar Brightness y disparar efectos (Clash, Blaster…)
- [x] Diseñar e implementar la etapa 1 del widget (sable). Consumo medido (2026-10-12): RAM 432 MB visible / 432 MB oculto (Working Set; privada ≈225 MB), CPU 0,01–0,02 %
- [ ] Consumo: la RAM privada (≈225 MB) supera el objetivo de 200 MB; casi todo es WebView2 (6 procesos). Investigar opciones de WebView2 para reducirlo sin perder las animaciones
- [ ] Etapa 2: focos Wiz (controles básicos, escenas, grupo "Cuarto")
- [ ] Mango de Obi-Wan detallado (a partir de fotos del sable real)
- [ ] Ver el sentido real de FileTransfer download/upload
