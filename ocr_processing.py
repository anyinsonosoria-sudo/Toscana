"""
OCR Processing Module for Receipt Recognition
Extrae información automáticamente de fotos de recibos usando Tesseract OCR
con preprocesamiento avanzado de imagen y parsing inteligente de campos.
"""

import os
import subprocess
import re
import io
from typing import Dict, Optional, Tuple
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter

# Configurar variables de entorno ANTES de importar pytesseract
def _setup_tesseract_env():
    """Configura variables de entorno para Tesseract"""
    possible_paths = [
        r'C:\Users\anyinson.osoria\AppData\Local\Programs\Tesseract-OCR',
        r'C:\Program Files\Tesseract-OCR',
        r'C:\Program Files (x86)\Tesseract-OCR',
    ]
    
    for base_path in possible_paths:
        tesseract_exe = os.path.join(base_path, 'tesseract.exe')
        if os.path.exists(tesseract_exe):
            tessdata_dir = os.path.join(base_path, 'tessdata')
            if os.path.exists(tessdata_dir):
                os.environ['TESSDATA_PREFIX'] = tessdata_dir
            current_path = os.environ.get('PATH', '')
            if base_path not in current_path:
                os.environ['PATH'] = base_path + ';' + current_path
            return tesseract_exe
    
    app_data_dir = os.path.expandvars(r'%USERPROFILE%\AppData\Local\Programs\Tesseract-OCR')
    if os.path.exists(app_data_dir):
        tessdata_dir = os.path.join(app_data_dir, 'tessdata')
        if os.path.exists(tessdata_dir):
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
        current_path = os.environ.get('PATH', '')
        if app_data_dir not in current_path:
            os.environ['PATH'] = app_data_dir + ';' + current_path
        return os.path.join(app_data_dir, 'tesseract.exe')
    
    return None

_tesseract_exe = _setup_tesseract_env()

import pytesseract

if _tesseract_exe:
    pytesseract.pytesseract.pytesseract_cmd = _tesseract_exe
    print(f"[OCR] Tesseract configurado: {_tesseract_exe}")
    print(f"[OCR] TESSDATA_PREFIX: {os.environ.get('TESSDATA_PREFIX', 'NO CONFIGURADO')}")
else:
    print("[OCR] ADVERTENCIA: Tesseract no encontrado. Instálalo desde https://github.com/UB-Mannheim/tesseract/wiki")


# ── Palabras clave para filtrar líneas de dirección ──
_ADDRESS_KEYWORDS = re.compile(
    r'\b(calle|carretera|avenida|av\.|cra\.?|sector|edif|edificio|piso|'
    r'local|plaza|centro|urbanizacion|urb\.?|km|manzana|mza|colonia|col\.|'
    r'barrio|esquina|esq\.?|no\.\s*\d|#\s*\d|apartado|p\.o\.?\s*box|'
    r'santo\s+domingo|santiago|la\s+vega|san\s+cristobal|puerto\s+plata|'
    r'muelle|autopista|camino|boulevard|blvd|diagonal|transversal)\b',
    re.IGNORECASE
)

_NOISE_KEYWORDS = re.compile(
    r'\b(rnc|tel|telefono|fax|email|www\.|http|cel|whatsapp|'
    r'horario|lunes|martes|miercoles|jueves|viernes|sabado|domingo|'
    r'gracias|ncf|gobierno|dgii|factura\s+valida|comprobante\s+fiscal)\b',
    re.IGNORECASE
)


class ReceiptOCR:
    """Procesa recibos mediante OCR para extraer información"""

    # ── Tesseract configuration ──
    TESSERACT_CONFIG = '--psm 6 --oem 3'

    @staticmethod
    def _run_ocr(image: Image.Image) -> str:
        """Ejecuta Tesseract con la mejor configuración disponible."""
        raw_text = ""
        # Intentar español primero, luego español+inglés, luego sin lang
        for lang in ('spa', 'spa+eng', None):
            try:
                kw = {'config': ReceiptOCR.TESSERACT_CONFIG}
                if lang:
                    kw['lang'] = lang
                raw_text = pytesseract.image_to_string(image, **kw)
                if raw_text.strip():
                    return raw_text
            except Exception:
                continue

        # Fallback: subprocess directo
        try:
            png_buf = io.BytesIO()
            image.save(png_buf, format='PNG')
            png_buf.seek(0)
            cmd = pytesseract.pytesseract.pytesseract_cmd or 'tesseract'
            proc = subprocess.run(
                [cmd, 'stdin', 'stdout', '-l', 'spa', '--psm', '6'],
                input=png_buf.read(), capture_output=True, timeout=15
            )
            raw_text = proc.stdout.decode('utf-8', errors='ignore')
        except Exception:
            pass

        return raw_text

    @staticmethod
    def process_image(file_path: str) -> Dict:
        """Procesa una imagen de recibo y extrae información."""
        try:
            image = Image.open(file_path)
            return ReceiptOCR._process(image)
        except FileNotFoundError:
            return {'error': f'Archivo no encontrado: {file_path}', 'raw_text': '', 'confidence': 0.0}
        except Exception as e:
            return {'error': f'Error procesando imagen: {str(e)}', 'raw_text': '', 'confidence': 0.0}

    @staticmethod
    def process_image_bytes(image_bytes: bytes) -> Dict:
        """Procesa bytes de imagen (desde upload)."""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            return ReceiptOCR._process(image)
        except Exception as e:
            return {'error': f'Error procesando imagen: {str(e)}', 'raw_text': '', 'confidence': 0.0}

    @staticmethod
    def _process(image: Image.Image) -> Dict:
        """Pipeline unificado de procesamiento."""
        image = ReceiptOCR._optimize_image(image)
        raw_text = ReceiptOCR._run_ocr(image)

        if not raw_text.strip():
            return {
                'error': 'No se pudo extraer texto de la imagen. Verifica que sea un recibo claro.',
                'raw_text': '', 'confidence': 0.0
            }

        return {
            'raw_text': raw_text,
            'description': ReceiptOCR._extract_description(raw_text),
            'amount': ReceiptOCR._extract_amount(raw_text),
            'date': ReceiptOCR._extract_date(raw_text),
            'supplier_name': ReceiptOCR._extract_supplier(raw_text),
            'confidence': ReceiptOCR._calculate_confidence(raw_text),
            'error': None
        }

    # ─────────────────────────────────────────────
    # IMAGE PREPROCESSING  (upgraded)
    # ─────────────────────────────────────────────
    @staticmethod
    def _optimize_image(image: Image.Image) -> Image.Image:
        """Preprocesamiento avanzado para mejor precisión de OCR."""
        # 1. Convertir a RGB
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        # 2. Escalar imágenes pequeñas (Tesseract funciona mejor ≥300 DPI)
        min_dim = 1200
        if image.width < min_dim or image.height < min_dim:
            scale = max(min_dim / image.width, min_dim / image.height)
            new_size = (int(image.width * scale), int(image.height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # 3. Convertir a escala de grises
        gray = image.convert('L')

        # 4. Aumentar contraste
        enhancer = ImageEnhance.Contrast(gray)
        gray = enhancer.enhance(2.0)

        # 5. Aumentar nitidez
        enhancer = ImageEnhance.Sharpness(gray)
        gray = enhancer.enhance(2.0)

        # 6. Binarización adaptativa (umbral Otsu simulado)
        # Usar punto medio del histograma como umbral
        histogram = gray.histogram()
        total_pixels = sum(histogram)
        cumulative = 0
        threshold = 128
        for i, count in enumerate(histogram):
            cumulative += count
            if cumulative >= total_pixels * 0.5:
                threshold = i
                break
        gray = gray.point(lambda x: 255 if x > threshold else 0, '1')

        # Convertir de vuelta a L para Tesseract
        gray = gray.convert('L')

        return gray

    # ─────────────────────────────────────────────
    # AMOUNT EXTRACTION  (fixed — NO division by 100)
    # ─────────────────────────────────────────────
    @staticmethod
    def _normalize_amount_str(s: str) -> Optional[float]:
        """
        Normaliza un string de monto a float.
        Reglas para República Dominicana:
         - Coma puede ser separador de miles (1,500 = 1500) o decimal (1,50 = 1.50)
         - Punto puede ser separador de miles (1.500 = 1500) o decimal (1.50)
         - Si hay coma seguida de exactamente 2 dígitos al final → coma es decimal
         - Si hay coma seguida de 3+ dígitos → coma es miles
        NUNCA divide por 100.
        """
        s = s.strip()
        if not s:
            return None

        # Remover símbolo de moneda
        s = re.sub(r'^[RD$\s]+', '', s, flags=re.IGNORECASE)
        s = re.sub(r'[\$]', '', s)
        s = s.strip()

        if not s:
            return None

        # Caso: solo dígitos (e.g. "199", "1500")
        if re.match(r'^\d+$', s):
            return float(s)

        # Caso: 1,500.00 o 1.500,00 (mixed separators)
        if ',' in s and '.' in s:
            # Último separador es el decimal
            last_comma = s.rfind(',')
            last_dot = s.rfind('.')
            if last_comma > last_dot:
                # Formato: 1.500,00 → punto=miles, coma=decimal
                s = s.replace('.', '').replace(',', '.')
            else:
                # Formato: 1,500.00 → coma=miles, punto=decimal
                s = s.replace(',', '')
        elif ',' in s:
            # Solo coma: si termina en ,XX (2 dígitos) → decimal; sino → miles
            m = re.match(r'^(\d+),(\d+)$', s)
            if m:
                decimals = m.group(2)
                if len(decimals) == 2:
                    s = s.replace(',', '.')  # decimal
                else:
                    s = s.replace(',', '')   # miles
            else:
                s = s.replace(',', '')
        # Si solo tiene punto, dejarlo como está (ya es correcto)

        try:
            val = float(s)
            return val if val > 0 else None
        except ValueError:
            return None

    @staticmethod
    def _extract_amount(text: str) -> Optional[float]:
        """Extrae monto del texto. Nunca divide por 100."""
        text_lower = text.lower()
        candidates = []  # (priority, amount)

        # ── Prioridad 1: "Total a pagar", "Total", "Monto" con valor ──
        labeled_patterns = [
            # TOTAL A PAGAR: 199 / TOTAL A PAGAR 199.00
            r'total\s*(?:a\s*pagar)?[:\s]*(?:rd\$?|us\$?)?\s*([0-9]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\b',
            r'total\s*(?:a\s*pagar)?[:\s]*(?:rd\$?|us\$?)?\s*([0-9]+)\b',
            # Sin espacios: TOTALAPAGAR199
            r'total\s*a?\s*pagar\s*([0-9]+(?:[.,][0-9]{1,2})?)',
            # MONTO / IMPORTE / SUBTOTAL
            r'(?:monto|importe|subtotal|sub\s*total|grand\s*total)[:\s]*(?:rd\$?|us\$?)?\s*([0-9]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\b',
            r'(?:monto|importe|subtotal|sub\s*total|grand\s*total)[:\s]*(?:rd\$?|us\$?)?\s*([0-9]+)\b',
        ]
        for pat in labeled_patterns:
            for m in re.finditer(pat, text_lower):
                val = ReceiptOCR._normalize_amount_str(m.group(1))
                if val and 0.01 <= val < 10_000_000:
                    candidates.append((1, val))

        # ── Prioridad 2: Símbolo de moneda  $199  RD$1,500.00 ──
        currency_patterns = [
            r'(?:rd\$|us\$|\$)\s*([0-9]{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?)\b',
            r'(?:rd\$|us\$|\$)\s*([0-9]+)\b',
        ]
        for pat in currency_patterns:
            for m in re.finditer(pat, text_lower):
                val = ReceiptOCR._normalize_amount_str(m.group(1))
                if val and 0.01 <= val < 10_000_000:
                    candidates.append((2, val))

        # ── Prioridad 3: Números con decimales (formato X.XX o X,XX) en cualquier parte ──
        for m in re.finditer(r'\b([0-9]{1,3}(?:[.,]\d{3})*[.,]\d{2})\b', text):
            val = ReceiptOCR._normalize_amount_str(m.group(1))
            if val and 0.50 <= val < 10_000_000:
                candidates.append((3, val))

        # ── Prioridad 4: Números enteros solos en línea (probablemente total) ──
        for m in re.finditer(r'(?:^|\n)\s*([0-9]{2,7})\s*(?:$|\n)', text):
            val = ReceiptOCR._normalize_amount_str(m.group(1))
            if val and 1 <= val < 10_000_000:
                candidates.append((4, val))

        if not candidates:
            return None

        # Seleccionar: prioridad más alta (número menor), luego monto más grande
        candidates.sort(key=lambda x: (x[0], -x[1]))
        return candidates[0][1]

    # ─────────────────────────────────────────────
    # DATE EXTRACTION  (fixed — returns None if not found)
    # ─────────────────────────────────────────────
    @staticmethod
    def _extract_date(text: str) -> Optional[str]:
        """Extrae fecha del recibo. Retorna None si no encuentra (NO usa fecha actual)."""
        text_lower = text.lower()

        month_map = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        }

        def _valid_date(day, month, year):
            """Valida y retorna fecha o None."""
            try:
                if 1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2099:
                    dt = datetime(year, month, day)
                    return dt.strftime('%Y-%m-%d')
            except ValueError:
                pass
            return None

        # 1. "Fecha: DD/MM/YYYY" o "Fecha: DD-MM-YYYY" (etiquetado)
        m = re.search(r'(?:fecha|date|fec)[:\s]+(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', text_lower)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 2000
            result = _valid_date(d, mo, y)
            if result:
                return result

        # 2. "16 de enero del 2025" / "16 enero 2025"
        for m in re.finditer(r'(\d{1,2})\s+(?:de\s+)?(\w+)\s+(?:del?\s+)?(\d{4})', text_lower):
            d_str, month_str, y_str = m.group(1), m.group(2), m.group(3)
            mo = month_map.get(month_str)
            if mo:
                result = _valid_date(int(d_str), mo, int(y_str))
                if result:
                    return result

        # 3. "enero 16, 2025" / "enero 16 2025"
        for m in re.finditer(r'(\w+)\s+(\d{1,2})[,\s]+(\d{4})', text_lower):
            month_str, d_str, y_str = m.group(1), m.group(2), m.group(3)
            mo = month_map.get(month_str)
            if mo:
                result = _valid_date(int(d_str), mo, int(y_str))
                if result:
                    return result

        # 4. DD/MM/YYYY o DD-MM-YYYY (sin etiqueta)
        for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b', text):
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            result = _valid_date(d, mo, y)
            if result:
                return result

        # 5. YYYY-MM-DD / YYYY/MM/DD (ISO)
        for m in re.finditer(r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b', text):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            result = _valid_date(d, mo, y)
            if result:
                return result

        # 6. DD/MM con año actual (solo 2 partes)
        for m in re.finditer(r'\b(\d{1,2})[/-](\d{1,2})\b', text):
            d, mo = int(m.group(1)), int(m.group(2))
            # Verificar que no sea hora (HH:MM)
            if 1 <= mo <= 12 and 1 <= d <= 31:
                result = _valid_date(d, mo, datetime.now().year)
                if result:
                    return result

        # NO retorna fecha actual — deja que el frontend use su default
        return None

    # ─────────────────────────────────────────────
    # DESCRIPTION EXTRACTION  (improved — excludes address/noise)
    # ─────────────────────────────────────────────
    @staticmethod
    def _is_address_line(line: str) -> bool:
        """Detecta si una línea es dirección postal."""
        return bool(_ADDRESS_KEYWORDS.search(line))

    @staticmethod
    def _is_noise_line(line: str) -> bool:
        """Detecta si una línea es ruido (teléfonos, RNC, etc.)."""
        return bool(_NOISE_KEYWORDS.search(line))

    @staticmethod
    def _extract_description(text: str) -> str:
        """Extrae descripción limpia: tipo de documento + ítems, sin dirección ni ruido."""
        lines = [l.strip() for l in text.strip().split('\n') if l.strip() and len(l.strip()) > 2]
        if not lines:
            return "Gasto sin descripción"

        # Detectar tipo de documento
        doc_type = ""
        doc_patterns = [
            (r'\b(recibo)\b', 'RECIBO'),
            (r'\b(factura)\b', 'FACTURA'),
            (r'\b(cotizacion|cotización)\b', 'COTIZACIÓN'),
            (r'\b(nota\s+de\s+credito|nota\s+credito)\b', 'NOTA DE CRÉDITO'),
            (r'\b(comprobante)\b', 'COMPROBANTE'),
        ]
        for pat, label in doc_patterns:
            if re.search(pat, text, re.IGNORECASE):
                doc_type = label
                break

        # Filtrar líneas: excluir dirección, ruido, totales puros, líneas solo numérico
        relevant = []
        for line in lines:
            low = line.lower()
            # Saltar direcciones
            if ReceiptOCR._is_address_line(line):
                continue
            # Saltar ruido
            if ReceiptOCR._is_noise_line(line):
                continue
            # Saltar líneas solo numéricas o con formato de total
            if re.match(r'^[\d\s.,\$RD:]+$', line):
                continue
            # Saltar líneas de totales
            if re.match(r'^(total|subtotal|itbis|cambio|efectivo|descuento)', low):
                continue
            # Saltar líneas tipo "RECIBO" solo (ya capturado como doc_type)
            if re.match(r'^(recibo|factura|comprobante|cotizacion)$', low):
                continue
            # La línea tiene contenido textual relevante
            if re.search(r'[a-záéíóúñü]', low):
                relevant.append(line)

        # Construir descripción
        if doc_type and relevant:
            desc = f"{doc_type} - {relevant[0]}"
        elif relevant:
            desc = relevant[0]
        elif doc_type:
            desc = doc_type
        else:
            desc = lines[0] if lines else "Gasto sin descripción"

        # Agregar segunda línea relevante si es un ítem
        if len(relevant) > 1 and len(desc) < 80:
            desc += f" | {relevant[1]}"

        if len(desc) > 150:
            desc = desc[:147] + "..."

        return desc

    # ─────────────────────────────────────────────
    # SUPPLIER EXTRACTION  (improved — excludes address)
    # ─────────────────────────────────────────────
    @staticmethod
    def _extract_supplier(text: str) -> Optional[str]:
        """Extrae nombre del proveedor. Excluye direcciones y líneas de ruido."""
        lines = [l.strip() for l in text.strip().split('\n') if l.strip() and len(l.strip()) > 3]

        # Buscar etiqueta explícita primero
        for line in lines:
            m = re.match(r'(?:empresa|proveedor|suplidor|negocio|tienda)[:\s]+(.+)', line, re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                if len(name) > 3:
                    return name[:60]

        # Buscar primera línea con letras, excluyendo dirección/ruido/doc-type-solo
        for line in lines[:6]:
            # Debe tener letras
            if not re.search(r'[a-záéíóúñü]{3,}', line.lower()):
                continue
            # No debe empezar con número (podría ser dirección)
            if re.match(r'^\d+\s', line):
                continue
            # No debe ser dirección
            if ReceiptOCR._is_address_line(line):
                continue
            # No debe ser ruido
            if ReceiptOCR._is_noise_line(line):
                continue
            # No doc type solo
            if re.match(r'^(recibo|factura|comprobante|cotizacion|nota)\b', line.lower()):
                continue
            # Esta es probablemente el nombre del proveedor
            supplier = line.strip()
            if len(supplier) > 60:
                supplier = supplier[:60].rstrip()
            return supplier

        return None

    # ─────────────────────────────────────────────
    # CONFIDENCE
    # ─────────────────────────────────────────────
    @staticmethod
    def _calculate_confidence(text: str) -> float:
        """Calcula confianza de la extracción (0.0 a 1.0)."""
        if not text or not text.strip():
            return 0.0

        score = 0.0
        text_len = len(text.strip())

        # Longitud del texto (más texto = más confianza, hasta un punto)
        score += min(0.3, text_len / 1000)

        # ¿Encontró un monto?
        if ReceiptOCR._extract_amount(text) is not None:
            score += 0.30

        # ¿Encontró una fecha del recibo?
        if ReceiptOCR._extract_date(text) is not None:
            score += 0.20

        # ¿Encontró un proveedor?
        if ReceiptOCR._extract_supplier(text) is not None:
            score += 0.20

        return min(1.0, score)


def check_tesseract_available() -> Tuple[bool, str]:
    """Verifica si Tesseract-OCR está instalado."""
    try:
        result = pytesseract.get_tesseract_version()
        return True, f"Tesseract {result} disponible"
    except Exception:
        pass

    try:
        tesseract_cmd = pytesseract.pytesseract.pytesseract_cmd
        if tesseract_cmd and os.path.exists(tesseract_cmd):
            result = subprocess.run(
                [tesseract_cmd, '--version'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0] if result.stdout else "v5.0+"
                return True, f"Tesseract {version_line} disponible"
    except Exception:
        pass

    try:
        result = subprocess.run(
            ['tesseract', '--version'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0] if result.stdout else "v5.0+"
            return True, f"Tesseract {version_line} disponible"
    except Exception:
        pass

    return False, "Tesseract-OCR no está instalado o no es accesible"
