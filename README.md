# Saber Widget

Widget de escritorio para Windows que controla sables de luz con placa **Xeno3** por Bluetooth.
Es una alternativa a la app oficial Xeno Configurator.

> **Proyecto no oficial.** No está afiliado a Damien Technology, a los fabricantes de sables ni a Lucasfilm/Disney.
> Lo uso con mi propio sable. Úsalo bajo tu responsabilidad.

## Estado

- ✅ Protocolo Bluetooth de las placas Xeno3 documentado y verificado con un sable real: [PROTOCOLO.md](PROTOCOLO.md)
- ✅ Scripts de prueba en Python: [pruebas/](pruebas/)
- 🛠️ Widget en desarrollo. Diseño: [docs/superpowers/specs/](docs/superpowers/specs/)
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
