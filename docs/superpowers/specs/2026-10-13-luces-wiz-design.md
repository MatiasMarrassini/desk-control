# Desk Control — etapa 2: pestaña "Cuarto" (focos WiZ)

**Fecha:** 2026-10-13 · **Estado:** diseño aprobado en conversación, pendiente de revisión escrita
**Referencias:** etapa 1: [2026-10-12-widget-sable-design.md](2026-10-12-widget-sable-design.md) ·
hallazgos WiZ en [NOTAS.md](../../../NOTAS.md) · maqueta aprobada: [maquetas/luces-cuarto.html](maquetas/luces-cuarto.html)

## 1. Objetivo

Sumar al widget una pestaña para controlar los **dos focos WiZ del cuarto**, **sincronizados por defecto**, sin perder
el control desde la app WiZ del celular.

**Criterios de éxito:**
- Encender/apagar, brillo, blanco regulable, color y escenas actúan sobre los dos focos a la vez y en sincronía.
- Se puede controlar un foco por separado y volver a sincronizarlos con un toque.
- La app WiZ del celular sigue funcionando igual. Los cambios hechos desde el celular aparecen en el widget en
  pocos segundos mientras la pestaña está visible.
- Se mantienen las reglas de la etapa 1: sin puertos en escucha, lista blanca de comandos, texto ajeno solo con
  `textContent`, y consumo de CPU ≈ 0 % en reposo.

## 2. Alcance

**Incluye:**
- Búsqueda de focos WiZ en la pantalla "Agregar dispositivo", junto a los sables.
- Creación de un **grupo**, nombre por defecto "Cuarto", con los focos encontrados; el grupo y cada foco se pueden
  renombrar.
- Pestaña del grupo con:
  - encendido;
  - Blanco (2200–6500 K) / Color (8 colores comunes + rueda);
  - brillo (10–100 %);
  - escenas: 7 favoritas más "Todas", con favoritas elegibles;
  - sección plegable "Focos": interruptor por foco y "Sincronizar los dos".
- Estado por foco y del grupo: chip en el panel y punto en la pestaña.

**No incluye:**
- Ritmos, horarios y automatizaciones.
- Velocidad de escenas animadas en la interfaz: se manda la velocidad por defecto del foco.
- Más de un grupo de luces en la interfaz. El modelo de datos lo admite, pero no se diseña la experiencia.
- Integración con la nube de WiZ.
- Notificaciones push de los focos (`registration`/`syncPilot`): requieren abrir un puerto en la PC.

## 3. Protocolo WiZ local (verificado con los focos reales)

- JSON por **UDP al puerto 38899**, pedido y respuesta: `{"method": ..., "params": {...}}`.
- **Lectura:**
  - `getPilot` → `{"result":{"mac","rssi","state","sceneId","temp","dimming","r","g","b",...}}`
  - `getSystemConfig` → `{"result":{"mac","homeId","roomId","groupId","moduleName","fwVersion",...}}`
- **Escritura:** `setPilot` con `params` → `{"result":{"success":true}}`.
- **Búsqueda:** difusión de `getSystemConfig` y `getPilot` a la dirección de broadcast de la red de la PC (/24).
  Responde cada foco desde su IP.
- Modelo instalado: `ESP24_SHRGBC_01` (color + blanco regulable), firmware 1.38.0.

**Lista blanca:**
- Métodos: `getPilot`, `getSystemConfig`, `setPilot`. Cualquier otro método (`setSystemConfig`, `reboot`, `reset`,
  `setWifiConfig`, `upgrade`…) no se puede enviar.
- Parámetros de `setPilot`:
  - `state` (bool)
  - `dimming` (10–100)
  - `r`, `g`, `b` (0–255; van los tres juntos)
  - `temp` (2200–6500)
  - `sceneId` (de la tabla de §6)
  - `speed` (10–200)
- Combinaciones válidas: color **o** temperatura **o** escena, más brillo y estado. Mandar dos de esas a la vez es inválido.

## 4. Arquitectura

Encaja en la arquitectura de la etapa 1 sin cambios de estructura:

```
widget/dispositivos/
  wiz_protocolo.py   mensajes, validación (lista blanca), tabla de escenas
  wiz_transporte.py  UDP con asyncio (pedido/respuesta con reintentos, difusión para búsqueda)
  wiz.py             GrupoWiz: estado del grupo y de cada foco, envío, consulta periódica, re-ubicación por MAC
  busqueda.py        + buscar_focos(); la pantalla junta sables y focos
```

- **Hilo:** el mismo bucle asyncio que el Bluetooth (`BucleAsync`). Los sockets UDP son "clientes":
  envían y leen la respuesta en el mismo socket efímero. **No hay sockets en escucha en un puerto fijo.**
- **Puente:**
  - Se generaliza para dos tipos de dispositivo, `xeno` y `wiz_grupo`. Cada tipo crea su controlador
    (`SesionSable` o `GrupoWiz`) con la misma idea: `al_evento`, estado y comandos.
  - Métodos nuevos para JS:
    - `luces_enviar(id_grupo, params, mac=None)`
    - `luces_sincronizar(id_grupo)`
    - `luces_favoritas(id_grupo, ids)`
    - `luces_visible(id_grupo, visible)`
  - Eventos hacia JS con el mismo formato `{id, tipo, datos}`. `tipo` es `estado` (del grupo y por foco) o `conexion`.
- **Interfaz:** `widget/ui/luces.js` + `luces.css` (`VistaLuces`, con la misma interfaz de vista que `VistaSable`),
  y `focos.svg` (el foco dibujado). `app.js` elige la vista según el tipo.

## 5. Comportamiento

**Identidad y dirección.** Cada foco se identifica por su **MAC** y se guarda su última IP conocida. Si un foco no
responde en su IP tras los reintentos, se hace una difusión para encontrar su IP nueva por MAC, una vez por
comando y como máximo cada 30 s.

**Comandos.**
- Al grupo: se envía el mismo `setPilot` a todos los focos **en paralelo**.
- A un foco: solo a ese.
- Cada envío espera la respuesta `success` hasta 0,6 s, con **3 intentos**.
- Si un foco no responde, se marca "sin respuesta" y los demás siguen.
- Deslizadores de brillo y temperatura: como máximo un envío cada 150 ms mientras se arrastra, y el valor final al
  soltar (igual que el brillo del sable).

**Estado sincronizado vs. individual.**
- La interfaz muestra el **estado del grupo**: el último comando de grupo o, al leer, el del primer foco que responde.
- Si los focos difieren (porque se tocó uno por separado o desde el celular), la sección "Focos" muestra cada uno
  con su color/estado y el botón **"Sincronizar los dos"** está resaltado.
- Sincronizar envía a todos el estado del grupo.

**Consulta periódica.**
- `getPilot` a cada foco **cada 5 s**, solo mientras la ventana está visible **y** la pestaña del grupo está
  activa. Se pausa al ocultar o al cambiar de pestaña.
- Un cambio hecho desde el celular aparece en ≤ 5 s.

**Estados de conexión:**

| Estado | Condición | Punto en la pestaña |
|---|---|---|
| `conectado` | todos responden | verde |
| `parcial` | algunos responden | ámbar; chip "1 de 2 conectadas" |
| `sin_respuesta` | ninguno responde | rojo; aviso con causas: apagados de la pared, otra red wifi, "Comunicación local" desactivada en la app WiZ |
| `buscando` | mientras se re-ubica | girando |

**Favoritas.**
- 7 escenas visibles en la grilla. En la lista "Todas", cada escena tiene una ★ para agregarla o quitarla de
  favoritas (máximo 7).
- Por defecto: Luz de día, Concentración, Relax, Luz nocturna, Fiesta, Chimenea, Océano.

## 6. Escenas (nombres oficiales de la app WiZ en español)

IDs según la documentación de la comunidad (pywizlight / Home Assistant). `12` = Luz de día está verificado en los
focos reales; el resto se verifica en la implementación leyendo `sceneId` con `getPilot` tras enviarla.

- **Fijas:**
  - 6 Acogedor · 11 Blanco cálido · 12 Luz de día · 13 Blanco frío · 14 Luz nocturna
  - 15 Concentración · 16 Relax · 17 Colores reales · 18 Hora de la tele · 19 Crecimiento de planta
- **Animadas:**
  - 1 Océano · 2 Romance · 3 Atardecer · 4 Fiesta · 5 Chimenea · 7 Bosque · 8 Colores pastel
  - 9 Despertar · 10 Hora de acostarse · 20 Primavera · 21 Verano · 22 Otoño · 23 Inmersión profunda
  - 24 Jungla · 25 Mojito · 26 Club · 27 Navidad · 28 Halloween · 29 Luz de vela · 30 Blanco dorado
  - 31 Pulso · 32 Steampunk · 33 Diwali

Los focos dibujados animan Fiesta y Chimenea como en la maqueta. El resto de las animadas muestra el color
reportado por el foco en cada consulta.

## 7. Interfaz (maqueta aprobada: opción B, versión 2)

- **Pestaña:** "💡 Cuarto" (nombre del grupo) con punto de estado. El estado de conexión va en el chip del panel,
  no en la barra.
- **Área de ambiente:** 112 px de alto. Los dos focos cuelgan de cables y brillan con el color y brillo actuales.
  Un foco apagado o sin respuesta se ve apagado.
- **Debajo:**
  - fila con ⏻ (SVG centrado, como en el sable) y el chip "● Conectadas · 2 focos";
  - tarjeta Blanco/Color (segmentado) con el deslizador de temperatura (2200–6500 K, degradé cálido→frío, valor en
    K) o los colores comunes más la rueda;
  - tarjeta Brillo con %;
  - tarjeta Escenas (grilla de 4 columnas: 7 favoritas + "Todas", que abre la lista con ★);
  - sección plegable "💡 Focos (2)": fila por foco con su color, nombre e interruptor, más "⟳ Sincronizar los dos".
- Todo entra en 380×600 sin scroll con la sección "Focos" cerrada. Abierta, se permite scroll en los controles.

## 8. Agregar y configurar

- "Buscar dispositivos" busca sables (BLE) y focos (difusión UDP) en paralelo.
- Los focos con el mismo `roomId` se proponen como **un grupo** ("Cuarto"). Al guardar se pide el nombre del grupo,
  y cada foco toma un nombre por defecto ("Foco 1", "Foco 2") que se puede editar.
- La configuración guarda el grupo con sus focos (`mac`, `nombre`, `ip`), las favoritas y la última caché de estado.

## 9. Errores

| Situación | Comportamiento |
|---|---|
| Un foco no responde (sin corriente) | Ese foco "sin respuesta"; el resto sigue; estado `parcial` |
| Ninguno responde | `sin_respuesta` con aviso y botón "Reintentar" (re-búsqueda por MAC) |
| La IP cambió (DHCP) | Re-ubicación automática por MAC con difusión |
| PC sin red / otra red | Búsqueda vacía con mensaje; la pestaña en `sin_respuesta` |
| Respuesta inválida o `success:false` | Aviso breve y el control vuelve al último estado confirmado |
| Firewall de Windows | Puede pedir permiso la primera vez para recibir respuestas de difusión: permitir solo en redes privadas (README) |

## 10. Pruebas

- **Automáticas (pytest), sin hardware:** un `FocoSimulado` (servidor UDP local en 127.0.0.1 en un puerto efímero,
  solo durante el test) que responde como los reales. Cubren:
  - lista blanca y combinaciones inválidas;
  - reintentos ante pérdida de paquetes;
  - envío en paralelo al grupo;
  - foco que no responde (`parcial`);
  - re-ubicación por MAC;
  - consulta periódica que se pausa al ocultar;
  - sincronización;
  - eventos al puente.
- **Manual con los focos reales:** lista de pasos que incluye verificar los `sceneId` de §6.
- **Consumo:** CPU ≈ 0 % con la pestaña oculta, y sin aumento apreciable de RAM respecto de la etapa 1.
