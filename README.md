# Desk Control

Widget de escritorio para Windows que controla los dispositivos de mi escritorio: por ahora, sables de luz con placa **Xeno3** por Bluetooth; más adelante, focos Wiz.
Es una alternativa a la app oficial Xeno Configurator.

> **Proyecto no oficial.** No está afiliado a Damien Technology, a los fabricantes de sables ni a Lucasfilm/Disney.
> Lo uso con mi propio sable. Úsalo bajo tu responsabilidad.

## Estado

- ✅ Protocolo Bluetooth de las placas Xeno3 documentado y verificado con un sable real: [PROTOCOLO.md](PROTOCOLO.md)
- ✅ Scripts de prueba en Python: [pruebas/](pruebas/)
- ✅ Widget de escritorio para el sable (etapa 1). Diseño: [docs/superpowers/specs/](docs/superpowers/specs/)
- 🔜 Control de focos Wiz

## Probar los scripts

Requiere Windows con Bluetooth, Python 3.12 y la librería `bleak`:

```bash
pip install bleak
python pruebas/escanear.py                    # busca placas Xeno3 cercanas
python pruebas/enviar.py                      # conecta y muestra el estado del sable
python pruebas/enviar.py Volume 20            # envía un comando
```

Los scripts buscan solos la primera placa Xeno3 cercana. Si tienes más de una, puedes fijar cuál usar
con la variable de entorno `XENO_SABLE` y la dirección que muestra `escanear.py`.

> ⚠️ No envíes `Reset`, `HardwareType`, `SoftwareType`, `ButtonNum` ni comandos de firmware sin entender
> bien qué hacen. Ver la sección de comandos peligrosos en PROTOCOLO.md.

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
