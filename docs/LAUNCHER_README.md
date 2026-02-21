# Building Maintenance System - Launcher

## ¿Qué cambió?

El sistema ahora utiliza un **launcher web** en lugar de una interfaz GUI de escritorio.

### Antes:
- Dos interfaces separadas: GUI (Tkinter) y Web (Flask)
- Código duplicado y difícil de mantener
- Funcionalidades inconsistentes entre versiones

### Ahora:
- **Una sola interfaz web** accesible desde cualquier dispositivo
- **Launcher de escritorio** que simplemente inicia el servidor y abre el navegador
- **PWA (Progressive Web App)** instalable en móviles
- Sistema OCR integrado para cargar recibos desde la cámara del móvil

## Cómo usar

### Desde escritorio:
1. Ejecuta `main.py` o `run_gui.bat`
2. Se abrirá una ventana pequeña con el estado del servidor
3. Automáticamente se abre el navegador en http://127.0.0.1:5000
4. Usa la aplicación web desde el navegador
5. Cierra la ventana del launcher para detener el servidor

### Desde móvil (PWA):
1. Accede a http://[IP_DEL_SERVIDOR]:5000 desde tu navegador móvil
2. Añade la app a tu pantalla de inicio
3. Usa como una app nativa con acceso a la cámara para OCR

## Ventajas

✅ **Una sola base de código** - más fácil de mantener
✅ **Acceso desde cualquier dispositivo** - PC, móvil, tablet
✅ **PWA instalable** - experiencia tipo app nativa
✅ **OCR desde móvil** - toma fotos de recibos directamente
✅ **Interfaz moderna** - Bootstrap 5, responsiva
✅ **Más completa** - todos los módulos implementados

## Archivos

- `main.py` - Launcher de escritorio (nuevo)
- `main_backup.py` - GUI antigua de Tkinter (respaldo)
- `app.py` - Aplicación web Flask
- `static/manifest.json` - Configuración PWA
- `static/sw.js` - Service Worker para PWA

## Desarrollo

Para ejecutar solo el servidor web sin el launcher:
```bash
python app.py
```

El servidor estará disponible en http://127.0.0.1:5000
