"""
OCR Processing Module for Receipt Recognition
Extrae información automáticamente de fotos de recibos usando Tesseract OCR
con preprocesamiento avanzado de imagen y parsing inteligente de campos.
"""

import os
import subprocess
import re
import io
import base64
from typing import Dict, Optional, Tuple
from datetime import datetime
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import requests

import platform

# Configurar variables de entorno ANTES de importar pytesseract
def _setup_tesseract_env():
    """Configura variables de entorno para Tesseract (Windows y Linux)."""
    # --- Linux / PythonAnywhere ---
    if platform.system() != 'Windows':
        for p in ('/usr/bin/tesseract', '/usr/local/bin/tesseract'):
            if os.path.exists(p):
                return p
        return None

    # --- Windows ---
    possible_paths = [
        r'C:\Users\anyinson.osoria\AppData\Local\Programs\Tesseract-OCR',
        r'C:\Program Files\Tesseract-OCR',
        r'C:\Program Files (x86)\Tesseract-OCR',
    ]
    app_data_dir = os.path.expandvars(r'%USERPROFILE%\AppData\Local\Programs\Tesseract-OCR')
    if app_data_dir not in possible_paths:
        possible_paths.append(app_data_dir)

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

    return None


def _check_tesseract_langs() -> list:
    """Devuelve idiomas disponibles en Tesseract local."""
    try:
        cmd = pytesseract.pytesseract.pytesseract_cmd or 'tesseract'
        proc = subprocess.run([cmd, '--list-langs'], capture_output=True, text=True, timeout=5)
        langs = [l.strip() for l in proc.stdout.strip().split('\n')[1:] if l.strip()]
        return langs
    except Exception:
        return []


_tesseract_exe = _setup_tesseract_env()

import pytesseract

_TESSERACT_AVAILABLE = False
_TESSERACT_HAS_SPA = False

if _tesseract_exe:
    pytesseract.pytesseract.pytesseract_cmd = _tesseract_exe
    _TESSERACT_AVAILABLE = True
    _langs = _check_tesseract_langs()
    _TESSERACT_HAS_SPA = 'spa' in _langs
    print(f"[OCR] Tesseract configurado: {_tesseract_exe}")
    print(f"[OCR] Idiomas disponibles: {_langs}")
else:
    # En Linux, tesseract podría estar en PATH aunque no lo encontramos
    try:
        pytesseract.get_tesseract_version()
        _TESSERACT_AVAILABLE = True
        _langs = _check_tesseract_langs()
        _TESSERACT_HAS_SPA = 'spa' in _langs
        print(f"[OCR] Tesseract en PATH. Idiomas: {_langs}")
    except Exception:
        print("[OCR] Tesseract no disponible. Se usará OCR.space (API cloud).")


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
        if not _TESSERACT_AVAILABLE:
            return ""

        raw_text = ""
        # Elegir idiomas según lo que esté instalado
        if _TESSERACT_HAS_SPA:
            lang_list = ('spa', 'spa+eng', None)
        else:
            lang_list = ('eng', None)

        for lang in lang_list:
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
    def _preprocess_soft(image: Image.Image) -> Image.Image:
        """
        Preprocesamiento suave: redimensiona + contraste mejorado.
        NO binariza — conserva tonos de gris para imágenes de color.
        """
        if image.mode not in ('RGB', 'L'):
            image = image.convert('RGB')

        # Escalar imágenes pequeñas
        min_dim = 1200
        if image.width < min_dim or image.height < min_dim:
            scale = max(min_dim / image.width, min_dim / image.height)
            new_size = (int(image.width * scale), int(image.height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        gray = image.convert('L')

        # Contraste moderado
        gray = ImageEnhance.Contrast(gray).enhance(1.8)
        # Nitidez moderada
        gray = ImageEnhance.Sharpness(gray).enhance(1.8)

        return gray

    @staticmethod
    def _build_result(raw_text: str) -> Dict:
        """Construye diccionario de resultado a partir del texto extraído."""
        return {
            'raw_text': raw_text,
            'description': ReceiptOCR._extract_description(raw_text),
            'amount': ReceiptOCR._extract_amount(raw_text),
            'date': ReceiptOCR._extract_date(raw_text),
            'supplier_name': ReceiptOCR._extract_supplier(raw_text),
            'confidence': ReceiptOCR._calculate_confidence(raw_text),
            'error': None
        }

    @staticmethod
    def _result_quality(result: Dict) -> int:
        """Puntúa la calidad de un resultado OCR (más alto = mejor)."""
        score = 0
        if result.get('amount'):  score += 3
        if result.get('date'):  score += 2
        if result.get('supplier_name'):  score += 1
        desc = result.get('description', '')
        if desc and desc != 'Gasto sin descripción':  score += 1
        return score

    @staticmethod
    def _process(image: Image.Image) -> Dict:
        """Pipeline unificado: OCR.space (cloud) + Tesseract local, elige el mejor."""
        # Corregir orientación EXIF (fotos de móviles vienen rotadas)
        try:
            image = ImageOps.exif_transpose(image)
        except Exception:
            pass

        orig = image.copy()
        best_text = ""
        best_result = None

        # ── Estrategia 1: OCR.space (cloud, fiable con español) ──
        cloud_text = ReceiptOCR._run_ocrspace(orig)
        if cloud_text.strip():
            cloud_result = ReceiptOCR._build_result(cloud_text)
            best_text = cloud_text
            best_result = cloud_result
            # Si la nube ya extrajo monto + fecha, devolver directo
            if cloud_result.get('amount') and cloud_result.get('date'):
                print(f"[OCR] Cloud exitoso: confianza {cloud_result['confidence']:.0%}")
                return cloud_result

        # ── Estrategia 2: Tesseract local (soft preprocessing) ──
        if _TESSERACT_AVAILABLE:
            img_soft = ReceiptOCR._preprocess_soft(orig)
            text_soft = ReceiptOCR._run_ocr(img_soft)

            # ── Estrategia 3: Tesseract local (hard preprocessing) ──
            img_hard = ReceiptOCR._preprocess_hard(orig)
            text_hard = ReceiptOCR._run_ocr(img_hard)

            local_text = text_soft if len(text_soft.strip()) >= len(text_hard.strip()) else text_hard

            if local_text.strip():
                local_result = ReceiptOCR._build_result(local_text)
                # Comparar calidad: usar el que extraiga más campos
                if best_result is None or ReceiptOCR._result_quality(local_result) > ReceiptOCR._result_quality(best_result):
                    best_text = local_text
                    best_result = local_result

        if best_result:
            print(f"[OCR] Resultado final: confianza {best_result['confidence']:.0%}, "
                  f"monto={best_result.get('amount')}, fecha={best_result.get('date')}, "
                  f"vendedor={best_result.get('supplier_name')}")
            # Log raw text para debug (primeras 500 chars)
            print(f"[OCR] Texto raw: {best_text[:500]}")
            return best_result

        return {
            'error': 'No se pudo extraer texto de la imagen. Verifica que sea un recibo claro.',
            'raw_text': best_text, 'confidence': 0.0
        }

    # ─────────────────────────────────────────────
    # IMAGE PREPROCESSING
    # ─────────────────────────────────────────────
    @staticmethod
    def _preprocess_hard(image: Image.Image) -> Image.Image:
        """Preprocesamiento agresivo con binarización (Otsu simulado)."""
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
    # OCR.SPACE CLOUD FALLBACK
    # ─────────────────────────────────────────────
    @staticmethod
    def _run_ocrspace(image: Image.Image) -> str:
        """
        Fallback: envía la imagen a la API gratuita de OCR.space.
        Usa la variable de entorno OCR_SPACE_API_KEY si está definida;
        si no, usa la clave pública de prueba 'helloworld'.
        """
        try:
            api_key = os.environ.get('OCR_SPACE_API_KEY', 'helloworld')

            # Redimensionar si es muy grande (OCR.space tiene límite de 1MB en free tier)
            img = image.convert('RGB')
            max_dim = 2000
            if img.width > max_dim or img.height > max_dim:
                ratio = min(max_dim / img.width, max_dim / img.height)
                img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.Resampling.LANCZOS)

            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            payload = f'data:image/jpeg;base64,{b64}'

            resp = requests.post(
                'https://api.ocr.space/parse/base64',
                data={
                    'base64Image': payload,
                    'language': 'spa',
                    'isOverlayRequired': 'false',
                    'detectOrientation': 'true',
                    'scale': 'true',
                    'OCREngine': '2',      # Engine 2 es más robusto para recibos
                },
                headers={'apikey': api_key},
                timeout=20
            )

            if resp.status_code == 200:
                data = resp.json()
                if not data.get('IsErroredOnProcessing'):
                    parsed = data.get('ParsedResults', [])
                    if parsed:
                        return parsed[0].get('ParsedText', '')
        except Exception as e:
            print(f'[OCR.space] Error: {e}')

        return ''

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
        """Extrae fecha del recibo. Muy agresivo con limpieza de OCR."""
        cleaned = ReceiptOCR._clean_for_extraction(text)
        text_lower = cleaned.lower()

        month_map = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
            'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
        }

        # Separador permisivo: permite espacios alrededor de / - .
        SEP = r'\s*[/\-.]\s*'

        def _fix_year(y):
            if y < 100:
                y += 2000
            return y

        def _valid(day, month, year):
            year = _fix_year(year)
            try:
                if 1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2099:
                    return datetime(year, month, day).strftime('%Y-%m-%d')
            except ValueError:
                pass
            return None

        # 1. Etiquetado: "Fecha: DD/MM/YYYY" (permite espacios alrededor del separador)
        m = re.search(r'(?:fecha|date)\s*:?\s*(\d{1,2})' + SEP + r'(\d{1,2})' + SEP + r'(\d{2,4})', text_lower)
        if m:
            r = _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if r: return r

        # 2. Escrito: "7 de marzo del 2026" / "7 marzo 2026" / "marzo 7, 2026"
        for m in re.finditer(r'(\d{1,2})\s+(?:de\s+)?(\w+)[,\s]+(?:del?\s+)?(\d{2,4})', text_lower):
            mo = month_map.get(m.group(2))
            if mo:
                r = _valid(int(m.group(1)), mo, int(m.group(3)))
                if r: return r
        for m in re.finditer(r'(\w+)\.?\s+(\d{1,2})[,\s]+(\d{2,4})', text_lower):
            mo = month_map.get(m.group(1))
            if mo:
                r = _valid(int(m.group(2)), mo, int(m.group(3)))
                if r: return r

        # 3. DD/MM/YYYY con cualquier separador y espacios opcionales (4 dígitos año)
        for m in re.finditer(r'(\d{1,2})' + SEP + r'(\d{1,2})' + SEP + r'(\d{4})', cleaned):
            r = _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if r: return r

        # 4. YYYY-MM-DD / YYYY/MM/DD (ISO)
        for m in re.finditer(r'(\d{4})' + SEP + r'(\d{1,2})' + SEP + r'(\d{1,2})', cleaned):
            r = _valid(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            if r: return r

        # 5. DD/MM/YY (2 dígitos año, no precedido ni seguido por dígito)
        for m in re.finditer(r'(?<!\d)(\d{1,2})' + SEP + r'(\d{1,2})' + SEP + r'(\d{2})(?!\d)', cleaned):
            r = _valid(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            if r: return r

        # 6. Secuencia pura DDMMYYYY (8 dígitos)
        for m in re.finditer(r'(?<!\d)(\d{8})(?!\d)', cleaned):
            s = m.group(1)
            r = _valid(int(s[:2]), int(s[2:4]), int(s[4:]))
            if r: return r

        # 7. Secuencia pura DDMMYY (6 dígitos)
        for m in re.finditer(r'(?<!\d)(\d{6})(?!\d)', cleaned):
            s = m.group(1)
            d, mo = int(s[:2]), int(s[2:4])
            if 1 <= d <= 31 and 1 <= mo <= 12:
                r = _valid(d, mo, int(s[4:]))
                if r: return r

        # 8. DD/MM sin año (usar año actual, excluir horas HH:MM)
        for m in re.finditer(r'(?:^|\s)(\d{1,2})' + SEP + r'(\d{1,2})(?:\s|$)', cleaned, re.MULTILINE):
            d, mo = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                r = _valid(d, mo, datetime.now().year)
                if r: return r

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
    def _clean_for_extraction(text: str) -> str:
        """Limpia artefactos comunes de OCR para mejorar extracción de campos."""
        cleaned = text
        # O/o → 0 cuando está junto a dígitos o separadores de fecha
        cleaned = re.sub(r'(?<=[0-9/\-.])[Oo](?=[0-9/\-.])', '0', cleaned)
        cleaned = re.sub(r'[Oo](?=\d[/\-.])', '0', cleaned)
        cleaned = re.sub(r'(?<=[/\-.])[Oo](?=\d)', '0', cleaned)
        # l/I → 1 entre dígitos
        cleaned = re.sub(r'(?<=\d)[lI](?=\d)', '1', cleaned)
        # Normalizar guiones Unicode a guión ASCII
        cleaned = cleaned.replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-')
        return cleaned

    # ── Patrones para identificar líneas de encabezado vs. ítems ──
    _HEADER_PATTERNS = re.compile(
        r'^(recibo|factura|comprobante|cotizaci[oó]n|nota\s+de\s+cr[eé]dito|'
        r'conduce|orden\s+de\s+compra|presupuesto|ticket|receipt|invoice)\b',
        re.IGNORECASE
    )
    _TOTAL_PATTERNS = re.compile(
        r'^(total|subtotal|sub\s*total|itbis|iva|tax|impuesto|cambio|efectivo|'
        r'descuento|desc\.?|propina|tip|vuelto|balance|neto|monto|importe|'
        r'tarjeta|visa|mastercard|cash|amount|paid|pago|abono)\b',
        re.IGNORECASE
    )
    _ITEM_HINT = re.compile(
        r'(\d+\s*[xX×]\s*\d|\d+\s+\d+[.,]\d{2}|\$\s*\d|rd\$|\d+[.,]\d{2}$|'
        r'\bund\b|\bpza\b|\bpieza|\bcaja|\bgal[oó]n|\blb\b|\bkg\b|\blt\b)',
        re.IGNORECASE
    )

    @staticmethod
    def _is_supplier_line(line: str) -> bool:
        """Detecta si una línea es probablemente el nombre del vendedor (encabezado)."""
        low = line.lower().strip()
        # Líneas todo en mayúsculas y cortas suelen ser el nombre del negocio
        if line == line.upper() and len(line) > 3 and re.search(r'[A-Z]{3,}', line):
            # Pero no si es un total o etiqueta
            if not ReceiptOCR._TOTAL_PATTERNS.match(low):
                return True
        # Contains SRL, SA, EIRL, INC, LLC, etc.
        if re.search(r'\b(s\.?r\.?l|s\.?a\.?s?|e\.?i\.?r\.?l|inc|llc|ltda|cia|c\.?a)\b', low):
            return True
        return False

    @staticmethod
    def _extract_description(text: str) -> str:
        """Retorna descripción básica. El usuario llena el detalle manualmente."""
        return ""

    # ─────────────────────────────────────────────
    # SUPPLIER EXTRACTION  (improved — excludes address)
    # ─────────────────────────────────────────────
    @staticmethod
    def _extract_supplier(text: str) -> Optional[str]:
        """Extrae nombre del vendedor/proveedor del recibo."""
        lines = [l.strip() for l in text.strip().split('\n') if l.strip() and len(l.strip()) > 2]
        if not lines:
            return None

        # 1. Buscar etiqueta explícita
        for line in lines:
            m = re.match(
                r'(?:empresa|proveedor|suplidor|negocio|tienda|vendedor|'
                r'raz[oó]n\s*social|comercio|establecimiento)[:\s]+(.+)',
                line, re.IGNORECASE
            )
            if m:
                name = m.group(1).strip()
                if len(name) > 2:
                    return name[:60]

        # 2. Buscar línea con razón social (SRL, SA, EIRL, etc.)
        for line in lines[:8]:
            if re.search(r'\b(s\.?r\.?l|s\.?a\.?s?|e\.?i\.?r\.?l|inc|llc|ltda|cia|c\.?a)\b', line, re.IGNORECASE):
                supplier = re.sub(r'\s*[-:]\s*$', '', line).strip()
                if len(supplier) > 2:
                    return supplier[:60]

        # 3. Línea ANTES de RNC o NCF (el nombre del negocio suele estar justo arriba)
        for i, line in enumerate(lines[:10]):
            if re.search(r'\b(rnc|ncf)\b', line.lower()):
                for j in range(i - 1, -1, -1):
                    prev = lines[j].strip()
                    if not prev or re.match(r'^[\d\s.,\$:]+$', prev):
                        continue
                    if ReceiptOCR._is_address_line(prev):
                        continue
                    if ReceiptOCR._HEADER_PATTERNS.match(prev.lower()):
                        continue
                    return prev[:60]

        # 4. Primera línea sustancial (no ruido, no dirección, no números)
        for line in lines[:6]:
            low = line.lower()
            if re.match(r'^[\d\s.,\$RD:]+$', line): continue
            if re.match(r'^\d+\s', line): continue
            if ReceiptOCR._HEADER_PATTERNS.match(low): continue
            if ReceiptOCR._is_address_line(line): continue
            if ReceiptOCR._is_noise_line(line): continue
            if ReceiptOCR._TOTAL_PATTERNS.match(low): continue
            if re.search(r'\d+[.,]\d{2}\s*$', line): continue
            # Debe tener al menos 2 letras
            if re.search(r'[a-zA-ZáéíóúñüÁÉÍÓÚÑÜ]{2,}', line):
                return line.strip()[:60]

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
    """Verifica si hay algún motor OCR disponible (Tesseract local o OCR.space cloud)."""
    # Tesseract local disponible
    if _TESSERACT_AVAILABLE:
        try:
            result = pytesseract.get_tesseract_version()
            lang_info = " (spa)" if _TESSERACT_HAS_SPA else " (eng only)"
            return True, f"Tesseract {result}{lang_info} + OCR.space cloud"
        except Exception:
            return True, "Tesseract local + OCR.space cloud"

    # Sin Tesseract, pero OCR.space cloud está siempre disponible
    return True, "OCR.space cloud (sin Tesseract local)"
