# Protocolo BLE de las placas Xeno3 (Damien Technology)

Obtenido decompilando Xeno Configurator para Android (`com.xeno.configurator`, código interno
`com.damien.damiensaber`). El protocolo lo implementa la placa, así que vale igual para iOS, PC o ESP32.

> Estado: conexión, handshake y autorización **verificados con el sable real** el 2026-10-12
> (placa Xeno3 con firmware `DMN_XENO_B_SV1.4.0`, RGB/Pixel, desde la PC con `pruebas/xeno.py`).
> Comandos de escritura **probados y confirmados por el usuario a la vista y al oído**:
> `Volume` (0–100), `PowerOn` (true enciende la hoja) y `BackgroundColor` ([r,g,b]).
> El resto todavía no está probado.
>
> **Importante:** el sable responde a cada comando con `[3,{"Clave":valor}]` en menos de 300 ms, y la respuesta
> llega **por notify en `dae1`**, no en `3ab1`, aunque el comando se escriba en `3ab1`.
> **Persistencia:** los cambios **se guardan solos**, sin `SaveCfg`. Volumen y color sobrevivieron a un apagado
> completo (por inactividad, a los `IdleSleepTime` = 10 min).
> `PowerOn: false` apaga la hoja y el sable anuncia por voz que se desconectó del controlador.
>
> **Configuración por fuente:** `BackgroundColor`, efectos (`CurrentClash`, `CurrentBlaster`…), `CurrentLightEffect`,
> `PreonTime`, `OnTime` y `OffTime` son **propios de cada fuente de sonido**. Al enviar `CurrentSoundPackageNo` el sable
> responde con todos esos valores de la fuente elegida (en un solo `[3,{...}]` en `dae1`).
> `Volume` y `Brightness` son globales. La numeración de las fuentes empieza en 0 o en 1 (ver `TotalSoundPackage`).
>
> **Batería (`Power`):** parece calcularse a partir del voltaje. Con la hoja encendida marcó 70 %; en reposo,
> unos minutos después, 77 %. La carga hace caer el voltaje, así que la lectura fiable es con la hoja apagada.
>
> Verificado en la práctica:
> - El sable se anuncia con el nombre `Saber` y los servicios `dae0` y `3ab0`.
> - `dae1` tiene read/write/notify y `3ab1` tiene read/**write-without-response**/notify.
> - Al recibir el handshake, el sable manda **todo su estado** por `dae1` en 3 notificaciones `[3,{...}]` y termina con `"HandShake":"OK"`.
> - La autorización responde `[3,{"Authorize":"AccessAllowed"}]` por notify y también al leer `3ab1`.
> - La señal es muy débil: -96 dBm a menos de 40 cm. Para que conecte hace falta un timeout largo (40 s).

## 1. Servicios y características
| Servicio | Característica | Uso |
|---|---|---|
| `0000dae0-0000-1000-8000-00805f9b34fb` | `0000dae1-0000-1000-8000-00805f9b34fb` | Canal de **handshake** (write + notify) |
| `00003ab0-0000-1000-8000-00805f9b34fb` | `00003ab1-0000-1000-8000-00805f9b34fb` | Canal de **datos/comandos** (write + notify + read) |

Las notificaciones se activan escribiendo en el descriptor CCCD `0x2902`; las librerías BLE lo hacen solas.
La app busca dispositivos que anuncien `dae0` o `3ab0` y solo conecta si la señal (RSSI) es mayor que -90 dBm.

## 2. Formato de los mensajes
Todo es **texto JSON en UTF-8**, con la forma `[tipo, {clave: valor}]`:

| Tipo | Dirección | Significado |
|---|---|---|
| `2` | App → Sable | Escribir o ejecutar (comando) |
| `3` | Sable → App | Respuesta o reporte de estado |
| `4` | Sable → App | Error: `[4,{"clave":"mensaje de error"}]` |

Ejemplo: `[2,{"Volume":3}]`

- Números: sin comillas, por ejemplo `[2,{"Brightness":80}]`
- Texto: con comillas, por ejemplo `[2,{"HardwareType":"..."}]`
- Booleanos: `true`/`false`
- Colores: arreglo RGB, por ejemplo `[2,{"BackgroundColor":[255,0,0]}]`

## 3. Secuencia de conexión (la que usa la app)
1. Conectar y pedir **MTU de 512** bytes.
2. Activar notify en `dae0/dae1`.
3. Escribir en `dae1`: `[2,{"HandShake":"HelloDamien"}]`
4. El sable responde por notify: `[3,{"HandShake":...}]`. Puede incluir `Power` (batería).
5. Activar notify en `3ab0/3ab1`.
6. **Autorizar**: escribir en `3ab1` `[2,{"Authorize":"SaberOfDamien"}]` y luego **leer** `3ab1`.
   La respuesta esperada es `[3,{"Authorize":"AccessAllowed"}]`. Sin esto la app no manda otros comandos.
7. Desde ahí, el sable envía su estado por notify en `3ab1` como `[3,{clave:valor,...}]`.
   La app guarda cada clave tal cual en su modelo `BleData`.

## 4. Comandos y estado (`Type.java`, `BleData.java`)
Todos se envían a `3ab1` con el formato `[2,{"Clave":valor}]`.

**Encendido y estado**
- `PowerOn` (bool): enciende o apaga la hoja *(a verificar)*
- `Power` (int): batería, solo lectura
- `HardwareVersion`, `SoftwareVersion`, `HardwareType`, `SoftwareType` (string)

**Sonido**
- `Volume` (int)
- `CurrentSoundPackageNo` / `TotalSoundPackage` (int): fuente de sonido actual / total
- `fontname` (string)
- `BGMOn` (bool): música de fondo
- `SwingSoundSensitivity` (int)

**Hoja / luz**
- `BackgroundColor` ([r,g,b]): color principal
- `Brightness` (int)
- `CurrentMode` / `TotalMode` (int)
- `CurrentLightEffect` / `TotalLightEffect` (int)
- `MainBlade` (bool), `MainBladeLength` (int)
- `SideBlade` (bool), `SideBladeLength`, `SideBladeDelay` (int)
- `PreonTime`, `OnTime`, `OffTime` (int): tiempos de ignición y retracción
- `FastColorChanging`, `SmoothColorChanging` (bool)

**Efectos (disparar o elegir variante)**
- `Clash`, `Blaster`, `Lockup`, `Drag`, `Force` (bool): disparar el efecto *(a verificar)*
- `CurrentClash`/`TotalClash`, `CurrentBlaster`/`TotalBlaster`, `CurrentLockup`/`TotalLockup`,
  `CurrentDrag`/`TotalDrag`, `CurrentForce`/`TotalForce`, `CurrentPostOff`/`TotalPostOff` (int)

**Modos especiales** (bool): `BattleMode`, `BlasterMode`, `BlockMode`, `TorchMode`, `GhostMode`,
`LightningMode`, `VelocityMode`, `Matrix`, `Countdown`

**Movimiento**
- `MotionControl`, `ClashOn`, `SwingSwitchOn` (bool)
- `ClashSensitivity`, `SwingSensitivity` (int)
- `PullPushSwitchOn`, `PushPullSwitchOn` (bool), `PullSensitivity`, `PushSensitivity` (int)
- `TwistOnSwitchOn`, `TwistOffSwitchOn` (bool), `TwistSensitivity` (int)
- `MotorSpeed` (int)

**Sistema**
- `ButtonNum`, `AwakenTime`, `SleepTime`, `IdleSleepTime` (int)
- `SaveCfg` (bool): guardar la configuración
- `Reset` (bool): **reset de fábrica**

## 5. Archivos (sistema de archivos del sable)
Comandos estilo shell (`LSFileCommondType.java`), con el mismo formato `[2,{...}]`:
- `df` (espacio libre), `ls` (listar), `fontname`, `setname` (renombrar fuente), `play` (reproducir sonido),
  `cp`, `rm`

Transferencia de archivos con **YMODEM** sobre BLE:
- `[2,{"FileTransfer":["download","config.ini"]}]` y `[2,{"FileTransfer":["upload","config.ini"]}]`
  (el sentido de *download*/*upload* todavía no está confirmado)
- Firmware: `update.bin`, `update_factory.bin` / `.ini`
- Funciones personalizadas: `/setting/customfunction.diy` (JSON de eventos y gestos, ver NOTAS.md)

## ⚠️ Comandos peligrosos (no probar sin entenderlos bien)
- `Reset`: borra la configuración.
- `HardwareType`, `SoftwareType`, `ButtonNum`: cambian cómo la placa interpreta el hardware.
- `FileTransfer` con `update*.bin`: **flashea firmware**. Un error puede dejar la placa inservible.
- `rm`: borra archivos de sonido o configuración.

## Archivos fuente de referencia (en `analisis/decompilado/sources/`)
- `com/damien/damiensaber/utils/C1836f.java`: UUIDs, handshake y autorización
- `p368w5/C7260d.java`: conexión, MTU y procesamiento de notificaciones
- `com/damien/damiensaber/p046vo/Type.java`: lista de comandos
- `com/damien/damiensaber/p046vo/BleData.java`: estado y tipos de cada clave
- `com/damien/damiensaber/command/LSFileCommondType.java`: comandos de archivos
- `com/damien/damiensaber/p045ui/activity/DeviceSettingActivity.java`: config.ini, firmware y YMODEM
