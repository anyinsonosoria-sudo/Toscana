# Sistema OCR para Carga de Recibos de Gastos

## Descripción

Este módulo permite cargar fotos de recibos de gastos y automáticamente extraer información usando OCR (Optical Character Recognition). El sistema extrae:

- **Descripción/Concepto** del gasto
- **Monto** total
- **Fecha** del recibo
- **Nombre del suplidor** (proveedor)
- Texto completo extraído para revisión

## Características

✅ **Carga de Imágenes**: Soporta PNG, JPG, GIF, WEBP
✅ **Extracción Automática**: Extrae información automáticamente
✅ **Revisión Manual**: Permite ajustar datos antes de guardar
✅ **Nivel de Confianza**: Muestra qué tan precisa fue la extracción
✅ **Almacenamiento**: Guarda imagen con los datos del gasto
✅ **Multiidioma**: Soporta OCR en español

## Instalación

### 1. Instalar Dependencias Python

```bash
pip install -r requirements.txt
```

Esto instala:
- **Pillow**: Procesamiento de imágenes
- **pytesseract**: Interfaz Python para Tesseract OCR

### 2. Instalar Tesseract-OCR

#### Windows:

1. Descarga el instalador desde:
   ```
   https://github.com/UB-Mannheim/tesseract/wiki
   ```

2. Busca y descarga: `tesseract-ocr-w64-v5.x.exe` (o versión más reciente)

3. Ejecuta el instalador:
   - Acepta la ubicación por defecto: `C:\Program Files\Tesseract-OCR`
   - Completa la instalación

#### macOS:

```bash
brew install tesseract
```

#### Linux (Ubuntu/Debian):

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

### 3. Verificar Instalación

Ejecuta el script de setup:

```bash
python ocr_setup.py
```

Deberías ver:
```
✓ Tesseract OCR encontrado: v5.x.x
✓ pillow instalado
✓ pytesseract instalado
✓ Sistema OCR completamente configurado y listo
```

## Cómo Usar

### Desde la Interfaz Web

1. **Navega a Gastos** (`/gastos`)

2. **Haz clic en** el botón verde "Cargar Recibo (OCR)"

3. **Paso 1 - Cargar Imagen**:
   - Selecciona una foto del recibo
   - La aplicación muestra una vista previa
   - Haz clic en "Procesar con OCR"

4. **Paso 2 - Revisar Datos**:
   - El sistema extrae automáticamente:
     - Descripción
     - Monto
     - Fecha
     - Suplidor
   - Ajusta los campos según sea necesario
   - Revisa el texto extraído en la sección "Raw"

5. **Guardar**:
   - Haz clic en "Guardar Gasto"
   - La imagen se almacena junto con el gasto

### Niveles de Confianza

- **✓ 80%+**: Excelente - Los datos extraídos son muy precisos
- **~ 60-79%**: Buena - Revisa los datos cuidadosamente
- **⚠ <60%**: Baja - Verifica y ajusta los datos manualmente

## Estructura de Archivos

```
building_maintenance/
├── ocr_processing.py       # Módulo OCR principal
├── ocr_setup.py           # Script de setup e instalación
├── expenses.py            # Módulo de gastos (actualizado)
├── app.py                 # Rutas Flask (actualizado)
├── templates/
│   └── gastos.html        # Template con modal OCR (actualizado)
├── static/uploads/        # Carpeta para guardar recibos
└── requirements.txt       # Dependencias (actualizado)
```

## API Endpoints

### POST `/gastos/upload-recibo`

Procesa una imagen y extrae información con OCR.

**Parámetros**:
- `file` (multipart/form-data): Archivo de imagen

**Respuesta exitosa** (200):
```json
{
    "success": true,
    "description": "Descripción extraída...",
    "amount": 1234.56,
    "date": "2024-01-09",
    "supplier_name": "Nombre del Suplidor",
    "confidence": 0.85,
    "raw_text": "Texto completo extraído...",
    "message": "Información extraída con 85% de confianza"
}
```

**Respuesta con error** (422):
```json
{
    "success": false,
    "error": "No se pudo extraer texto de la imagen...",
    "raw_text": "..."
}
```

### POST `/gastos/save-with-receipt`

Guarda un gasto con la imagen del recibo.

**Parámetros**:
- `description`: Descripción del gasto
- `amount`: Monto
- `date`: Fecha
- `category`: Categoría (opcional)
- `supplier_id`: ID del suplidor (opcional)
- `receipt_file`: Archivo de recibo (opcional)
- `payment_method`: Método de pago (opcional)
- `notes`: Notas (opcional)

## Ejemplos de Uso

### Ejemplo 1: Recibo de Compra Simple

1. Toma foto de un recibo de compra
2. Sube la imagen
3. El sistema extrae:
   - Nombre del negocio
   - Monto total
   - Fecha de compra

### Ejemplo 2: Recibo con Múltiples Artículos

El sistema extrae el total general y genera una descripción basada en los primeros artículos encontrados.

### Ejemplo 3: Recibo Digital

También funciona con fotos de pantalla o PDF convertidos a imagen.

## Limitaciones y Notas

⚠️ **Calidad de Imagen**: La precisión depende de:
- Claridad de la foto
- Iluminación
- Ángulo de fotografía
- Tipo de fuente del recibo

⚠️ **Idiomas**: Actualmente configurado para español. Para otros idiomas, edita `ocr_processing.py`:
```python
raw_text = pytesseract.image_to_string(image, lang='spa')
# Cambiar 'spa' a: 'eng' (inglés), 'fra' (francés), 'deu' (alemán), etc.
```

⚠️ **Tamaño de Archivo**: Las imágenes muy grandes (>10MB) pueden procesarse lentamente.

## Solución de Problemas

### Error: "Tesseract OCR no disponible"

**Solución**:
1. Instala Tesseract-OCR desde: https://github.com/UB-Mannheim/tesseract/wiki
2. En Windows, verifica que esté en: `C:\Program Files\Tesseract-OCR`
3. Reinicia la aplicación Flask

### Error: "No se pudo extraer texto"

**Causas**:
- Imagen de mala calidad (borrosa, oscura)
- Idioma no soportado
- Archivo no es una imagen válida

**Solución**:
- Toma una foto más clara
- Asegúrate de que el recibo sea en español (o ajusta el idioma)
- Intenta con otro formato de imagen

### Error: "pytesseract no instalado"

**Solución**:
```bash
pip install pytesseract pillow
```

## Estructura de Base de Datos

La tabla `expenses` se actualizó con una nueva columna:

```sql
ALTER TABLE expenses ADD COLUMN receipt_path TEXT;
```

Esta columna almacena la ruta a la imagen del recibo:
```
static/uploads/receipt_1_20240109_143025.png
```

## Seguridad

- ✅ Las imágenes se guardan en carpeta `static/uploads/`
- ✅ Los nombres incluyen timestamp para evitar conflictos
- ✅ Se valida el tipo de archivo antes de procesar
- ✅ Se verifican extensiones permitidas

## Mejoras Futuras

- [ ] Soporte para múltiples idiomas
- [ ] Extracción de detalles de línea (artículos individuales)
- [ ] Análisis de comportamiento para sugerencias
- [ ] Procesamiento batch de múltiples recibos
- [ ] Exportación de datos extraídos
- [ ] Integración con APIs de OCR en la nube (Google Vision, AWS Textract)

## Recursos

- **Tesseract Wiki**: https://github.com/UB-Mannheim/tesseract/wiki
- **pytesseract Docs**: https://github.com/madmaze/pytesseract
- **Pillow Docs**: https://python-pillow.org/

## Soporte

Para reportar problemas, verifica:
1. Que Tesseract está instalado: `tesseract --version`
2. Que pytesseract funciona: `python -c "import pytesseract; print(pytesseract.get_tesseract_version())"`
3. Que los logs en Flask no muestren errores
