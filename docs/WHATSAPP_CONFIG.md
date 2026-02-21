# Configuración de WhatsApp con Twilio

## ✅ Funcionalidad Implementada

El sistema ahora envía automáticamente notificaciones por WhatsApp para:

1. **Facturas** - Cuando se crea una nueva factura
2. **Pagos** - Cuando se registra un pago
3. **Estados de Cuenta** - Cuando se solicita enviar el estado de cuenta

## 📋 Requisitos Previos

1. Cuenta de Twilio (gratis para pruebas): https://www.twilio.com/try-twilio
2. Teléfonos de clientes registrados en formato internacional (+1XXXXXXXXXX)

## ⚙️ Configuración

### Paso 1: Obtener Credenciales de Twilio

1. Crea una cuenta en https://www.twilio.com/try-twilio
2. Ve al Dashboard de Twilio
3. Copia tu **Account SID** y **Auth Token**

### Paso 2: Configurar WhatsApp Sandbox (Para Pruebas)

1. En Twilio Console, ve a **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Sigue las instrucciones para conectar tu WhatsApp al sandbox
3. Envía el mensaje de activación desde tu WhatsApp al número indicado
4. Copia el número **From** (será algo como `whatsapp:+14155238886`)

### Paso 3: Configurar Variables de Entorno

Agrega estas variables al archivo `.env` en el directorio `building_maintenance`:

```env
# Credenciales de Twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here

# Número de WhatsApp de Twilio (sandbox o número verificado)
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886

# SMTP (Email) - Ya configurado
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=invoicetoscana@gmail.com
SMTP_PASSWORD=your_password
SMTP_FROM=invoicetoscana@gmail.com
```

### Paso 4: Formato de Teléfonos en la Base de Datos

Los teléfonos de los clientes deben estar en formato internacional:

**Formato Correcto:**
- `+18091234567` (República Dominicana)
- `+18291234567` (República Dominicana)
- `+18491234567` (República Dominicana)
- `+15551234567` (Estados Unidos)

**Formato Incorrecto:**
- `8091234567` ❌
- `(809) 123-4567` ❌
- `1-809-123-4567` ❌

## 🧪 Prueba del Sistema

### 1. Verificar Configuración

Ejecuta este comando para verificar que Twilio está configurado:

```bash
python -c "import os; print('TWILIO_ACCOUNT_SID:', 'Configurado' if os.getenv('TWILIO_ACCOUNT_SID') else 'NO CONFIGURADO'); print('TWILIO_AUTH_TOKEN:', 'Configurado' if os.getenv('TWILIO_AUTH_TOKEN') else 'NO CONFIGURADO')"
```

### 2. Actualizar Teléfono de Cliente

Ve a **Residentes** en el sistema y actualiza el teléfono del cliente de prueba:
- Formato: `+18091234567`
- Asegúrate de que el teléfono esté conectado al sandbox de Twilio

### 3. Probar Envío de Factura

1. Crea una nueva factura para un cliente con teléfono configurado
2. Verifica que llegue:
   - ✉️ Email con PDF adjunto
   - 📱 WhatsApp con resumen de la factura

### 4. Probar Envío de Pago

1. Registra un pago para una factura
2. Activa las opciones:
   - ✅ Enviar comprobante por email
   - ✅ Adjuntar estado de cuenta (opcional)
3. Verifica que llegue:
   - ✉️ Email con comprobante PDF
   - 📱 WhatsApp con confirmación de pago
   - 📱 WhatsApp con estado de cuenta (si se solicitó)

## 📱 Mensajes de WhatsApp

### Factura Nueva
```
📄 *NUEVA FACTURA*

🏠 Apartamento: 1A
📋 Factura #: 34
📅 Fecha emisión: 2026-01-13
📅 Vencimiento: 2026-02-13

💼 Descripción:
CARGO MANTENIMIENTO MENSUAL

💰 Monto: RD$1,000.00

Por favor, realice el pago antes de la fecha de vencimiento.

_Mensaje automático - No responder_
```

### Confirmación de Pago
```
✅ *PAGO RECIBIDO*

🏠 Apartamento: 1A
🧾 Recibo #: 26
📋 Factura #: 34
📅 Fecha: Enero 13, 2026
💳 Método: Efectivo

💰 Monto Pagado: RD$500.00

¡Gracias por su pago puntual!

_Mensaje automático - No responder_
```

### Estado de Cuenta
```
📊 *ESTADO DE CUENTA*

🏠 Apartamento: 1A
👤 Residente: Williams Osoria

📋 Total Facturado: RD$5,000.00
💵 Total Pagado: RD$4,500.00
💰 Balance: RD$500.00

⚠️ PENDIENTE DE PAGO

📄 Facturas: 5
🧾 Pagos: 4

Para ver el detalle completo, revise su email.

_Mensaje automático - No responder_
```

## 🔐 Producción (Número Verificado)

Para usar WhatsApp en producción (sin sandbox):

1. **Verificar tu Número de WhatsApp Business:**
   - Ve a Twilio Console → **Messaging** → **WhatsApp senders**
   - Sigue el proceso de verificación de Meta

2. **Actualizar Variables de Entorno:**
   ```env
   TWILIO_WHATSAPP_FROM=whatsapp:+tuNumerVerificado
   ```

3. **Sin Limitaciones:**
   - Los clientes NO necesitan enviar mensaje de activación
   - Puedes enviar a cualquier número
   - Sin límites de mensajes

## ⚠️ Limitaciones del Sandbox

- Los clientes deben activar el sandbox enviando un mensaje primero
- Solo funciona con números que han enviado el código de activación
- Límite de mensajes por día

## 🆘 Solución de Problemas

### Error: "TWILIO credentials not configured"
- Verifica que las variables de entorno estén en el archivo `.env`
- Reinicia el servidor Flask después de agregar las variables

### Error: "requests required for Twilio"
```bash
pip install requests
```

### WhatsApp no llega pero email sí
1. Verifica que el teléfono esté en formato internacional (+1...)
2. Verifica que el número esté conectado al sandbox (si estás en pruebas)
3. Revisa los logs en la consola del servidor Flask

### Mensajes no llegan
1. Verifica el Dashboard de Twilio para ver si hay errores
2. Asegúrate de que el saldo de Twilio sea suficiente
3. Verifica que el número "From" sea correcto

## 📊 Monitoreo

Los logs del servidor Flask mostrarán:
- ✓ Comprobante de pago enviado por WhatsApp a +18091234567
- ✓ Estado de cuenta enviado por WhatsApp a +18091234567
- ✓ Factura enviada por WhatsApp a +18091234567
- ✗ Error enviando por WhatsApp: [descripción del error]

## 💡 Consejos

1. **Primero configura y prueba el sandbox** antes de verificar un número
2. **Usa un número de prueba** (tuyo) para las primeras pruebas
3. **Verifica los logs** en la terminal del servidor para debugging
4. **Los PDFs no se envían por WhatsApp** (limitación de la API), solo resúmenes de texto
5. **Los emails siguen funcionando** con los PDFs adjuntos como siempre

## 📞 Soporte

Si necesitas ayuda adicional:
- Documentación de Twilio WhatsApp: https://www.twilio.com/docs/whatsapp
- Sandbox de WhatsApp: https://www.twilio.com/console/sms/whatsapp/sandbox
