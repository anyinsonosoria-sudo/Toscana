# Sistema de Notificaciones Automáticas de Facturas

## Resumen

El sistema envía automáticamente notificaciones por email (y opcionalmente WhatsApp) cuando se crean facturas nuevas.

## ✅ Estado Actual

- ✅ **Configuración SMTP**: Completada y funcional
- ✅ **Email Notificaciones**: Activo
- ⚠️ **WhatsApp**: Configuración opcional (deshabilitado por defecto)
- ✅ **Generación PDF**: Automática con adjunto en email

## 🔧 Configuración

### Variables de Entorno (.env)

```env
# Email (SMTP) - REQUERIDO
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=invoicetoscana@gmail.com
SMTP_PASSWORD=ypxevbdokinhqjcp
SMTP_FROM=invoicetoscana@gmail.com

# WhatsApp (OPCIONAL)
WHATSAPP_ENABLED=false
WHATSAPP_API_URL=
WHATSAPP_API_TOKEN=
```

## 📧 Flujo de Notificaciones

### Al Crear una Factura:

1. Usuario llena formulario en sección "Facturación"
2. Selecciona cliente/residente (se auto-completa email y teléfono)
3. **Si proporciona email**: Se envía notificación automáticamente
4. **Si NO proporciona email**: Factura se crea sin notificación

### Contenido del Email:

```
Asunto: [Nombre Cliente] - Apartamento [#] - Factura #[ID]

Contenido:
- Número de factura
- Apartamento
- Descripción de servicios
- Monto total
- Fecha de emisión
- Fecha de vencimiento
- PDF adjunto (si se marca opción "Adjuntar PDF")
```

## 🎯 Uso en la Interfaz Web

### Crear Factura con Notificación:

1. Ir a **Facturación** → **Facturas**
2. Click en "➕ Crear Nueva Venta / Factura"
3. Seleccionar cliente/residente
4. **Email y teléfono se auto-completan** desde datos del residente
5. Agregar servicios/productos
6. ✅ Marcar "Adjuntar PDF" (opcional pero recomendado)
7. Click en "Crear Factura"
8. ✅ **Sistema envía email automáticamente**

### Resultado:

```
✅ Factura #123 creada y enviada a cliente@example.com
```

### Crear Factura SIN Notificación:

1. Mismo proceso pero **borrar el campo email**
2. Sistema crea factura sin enviar notificación

```
ℹ️ Factura #123 creada (sin notificación automática)
```

## 🔄 Reenviar Factura Existente

Si necesita reenviar una factura ya creada:

1. Ir a lista de facturas
2. Click en botón **"📨 Reenviar"** junto a la factura
3. Sistema envía email con la factura

## 📁 Almacenamiento de PDFs

Los PDFs de facturas se almacenan en:

```
/static/invoices/invoice_[ID].pdf
```

Ejemplo: `/static/invoices/invoice_123.pdf`

## 🐛 Troubleshooting

### Factura creada pero email no llega:

1. **Verificar logs del servidor**:
   ```
   ✅ Notificación de factura #123 enviada a cliente@example.com
   ```

2. **Verificar archivo de log**:
   ```
   /notifications.log
   ```

3. **Verificar configuración SMTP**:
   ```bash
   python scripts/debug/test_invoice_notification.py
   ```

### Error al crear factura:

Si aparece mensaje:
```
❌ Error al crear factura: Error al enviar notificación: [mensaje]
```

**Causa**: Error en servidor SMTP

**Solución**:
1. Verificar credenciales SMTP en `.env`
2. Verificar que cuenta Gmail tenga "Acceso de apps menos seguras" activado
3. O usar "Contraseña de aplicación" de Gmail

### Email no se auto-completa:

**Causa**: Cliente no tiene email registrado

**Solución**:
1. Ir a **Apartamentos**
2. Editar apartamento del cliente
3. Agregar email del residente
4. Guardar cambios

## 📊 Logs y Auditoría

### Console Logs:

```python
# Éxito
✅ Notificación de factura #123 enviada a cliente@example.com

# Sin email proporcionado
⚠️  Factura #123 creada sin envío de notificación (no se proporcionó email)

# Error
❌ Error al enviar notificación de factura #123: [detalle]
```

### Archivo de Log:

```
notifications.log
```

Formato:
```
2026-01-17T10:30:00Z - Notificación de factura #123 enviada exitosamente
2026-01-17T10:35:00Z - Error al enviar notificación de factura #124: SMTP timeout
```

## 🔐 Seguridad

### Datos Sensibles:

- ❌ **NUNCA** commitear `.env` al repositorio
- ✅ Usar contraseñas de aplicación de Gmail (no contraseña real)
- ✅ Configuración SMTP se carga desde variables de entorno
- ✅ Logs no muestran contraseñas

### Permisos:

- Crear facturas: Requiere permiso `facturacion.create`
- Ver facturas: Requiere permiso `facturacion.view`
- Los emails se envían desde cuenta configurada en `SMTP_FROM`

## 🚀 Mejoras Futuras

### Posibles Extensiones:

1. **WhatsApp Automation**: Integración con API de WhatsApp Business
2. **Recordatorios Automáticos**: Emails antes de vencimiento
3. **Confirmación de Lectura**: Tracking de apertura de emails
4. **Templates Personalizables**: Editor de plantillas de email
5. **Notificaciones SMS**: Vía Twilio u otro proveedor

## 📞 Soporte

Para problemas o preguntas:

1. Revisar esta guía primero
2. Ejecutar script de diagnóstico:
   ```bash
   python scripts/debug/test_invoice_notification.py
   ```
3. Revisar logs del servidor y `notifications.log`
4. Contactar al administrador del sistema

---

**Última Actualización**: 2026-01-17
**Versión del Sistema**: 8.4/10 (Post-Auditoría v2)
