"""
File Validator - Validacion Segura de Archivos
Implementa validacion robusta de uploads con magic bytes
"""

import os
from werkzeug.utils import secure_filename
from pathlib import Path

# Intentar importar python-magic, pero no es requerido
try:
    import magic
    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False

# Configuracion
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_FILENAME_LENGTH = 255

# MIME types permitidos
ALLOWED_MIME_TYPES = {
    # Imagenes
    'image/png',
    'image/jpeg',
    'image/jpg',
    'image/gif',
    'image/webp',
    # Documentos
    'application/pdf',
}

# Extensiones permitidas (como fallback)
ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'
}

# Magic bytes para validacion sin python-magic
MAGIC_BYTES = {
    'png': {'signatures': [(0, b'\x89PNG\r\n\x1a\n')], 'mime': 'image/png'},
    'jpg': {'signatures': [(0, b'\xff\xd8\xff')], 'mime': 'image/jpeg'},
    'jpeg': {'signatures': [(0, b'\xff\xd8\xff')], 'mime': 'image/jpeg'},
    'gif': {'signatures': [(0, b'GIF87a'), (0, b'GIF89a')], 'mime': 'image/gif'},
    'webp': {'signatures': [(0, b'RIFF')], 'mime': 'image/webp'},  # RIFF header
    'pdf': {'signatures': [(0, b'%PDF')], 'mime': 'application/pdf'},
}


class FileValidationError(Exception):
    """Excepción personalizada para errores de validación de archivos"""
    pass


def validate_file_size(file):
    """
    Valida el tamaño del archivo
    
    Args:
        file: FileStorage object de Flask
        
    Raises:
        FileValidationError: Si el archivo es demasiado grande
    """
    # Ir al final del archivo para obtener tamaño
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)  # Volver al inicio
    
    if size > MAX_FILE_SIZE:
        size_mb = size / (1024 * 1024)
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        raise FileValidationError(
            f'Archivo demasiado grande ({size_mb:.1f}MB). Máximo permitido: {max_mb:.0f}MB'
        )
    
    if size == 0:
        raise FileValidationError('El archivo está vacío')


def validate_filename(filename):
    """
    Valida y sanitiza el nombre del archivo
    
    Args:
        filename: Nombre del archivo
        
    Returns:
        str: Nombre de archivo sanitizado
        
    Raises:
        FileValidationError: Si el nombre es inválido
    """
    if not filename:
        raise FileValidationError('Nombre de archivo vacío')
    
    # Sanitizar con Werkzeug
    safe_filename = secure_filename(filename)
    
    if not safe_filename:
        raise FileValidationError('Nombre de archivo inválido')
    
    if len(safe_filename) > MAX_FILENAME_LENGTH:
        # Truncar manteniendo la extensión
        name, ext = os.path.splitext(safe_filename)
        max_name_length = MAX_FILENAME_LENGTH - len(ext)
        safe_filename = name[:max_name_length] + ext
    
    return safe_filename


def validate_file_extension(filename):
    """
    Valida la extension del archivo
    
    Args:
        filename: Nombre del archivo
        
    Raises:
        FileValidationError: Si la extension no esta permitida
    """
    if '.' not in filename:
        raise FileValidationError('Archivo sin extension')
    
    extension = filename.rsplit('.', 1)[1].lower()
    
    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f'Extension .{extension} no permitida. Permitidas: {", ".join(ALLOWED_EXTENSIONS)}'
        )


def validate_magic_bytes(header, expected_extension):
    """
    Valida que los magic bytes coincidan con la extension declarada.
    Metodo robusto que no requiere dependencias externas.
    
    Args:
        header: Primeros bytes del archivo
        expected_extension: Extension declarada
        
    Returns:
        tuple: (es_valido, mime_type_detectado)
    """
    ext = expected_extension.lower()
    
    if ext not in MAGIC_BYTES:
        return True, None  # Extension sin firma conocida, aceptar
    
    info = MAGIC_BYTES[ext]
    for offset, signature in info['signatures']:
        if len(header) >= offset + len(signature):
            if header[offset:offset + len(signature)] == signature:
                return True, info['mime']
    
    return False, None


def detect_real_type(header):
    """
    Detecta el tipo real del archivo basado en magic bytes.
    
    Args:
        header: Primeros bytes del archivo
        
    Returns:
        str: Extension detectada o None
    """
    for ext, info in MAGIC_BYTES.items():
        for offset, signature in info['signatures']:
            if len(header) >= offset + len(signature):
                if header[offset:offset + len(signature)] == signature:
                    return ext
    return None


def validate_mime_type(file):
    """
    Valida el MIME type real del archivo (no solo la extension).
    Usa python-magic si esta disponible, sino magic bytes.
    
    Args:
        file: FileStorage object de Flask
        
    Returns:
        str: MIME type detectado
        
    Raises:
        FileValidationError: Si el MIME type no esta permitido
    """
    # Leer primeros bytes para detectar tipo
    header = file.read(2048)
    file.seek(0)  # Volver al inicio
    
    mime = None
    
    # Intentar con python-magic si esta disponible
    if MAGIC_AVAILABLE:
        try:
            mime = magic.from_buffer(header, mime=True)
            # Verificar que no sea generico (significa que libmagic no funciona bien)
            if mime and mime != 'application/octet-stream':
                if mime not in ALLOWED_MIME_TYPES:
                    raise FileValidationError(
                        f'Tipo de archivo no permitido: {mime}. '
                        f'Permitidos: {", ".join(ALLOWED_MIME_TYPES)}'
                    )
                return mime
        except Exception:
            pass  # Fallback a magic bytes
    
    # Fallback: usar magic bytes
    # Obtener extension del archivo
    filename = getattr(file, 'filename', '')
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
        is_valid, detected_mime = validate_magic_bytes(header, ext)
        
        if not is_valid:
            # Detectar tipo real para mensaje de error
            real_type = detect_real_type(header)
            if real_type:
                raise FileValidationError(
                    f'El archivo dice ser .{ext} pero su contenido parece ser .{real_type}'
                )
            else:
                raise FileValidationError(
                    f'El contenido del archivo no coincide con la extension .{ext}'
                )
        
        mime = detected_mime
    
    return mime

    return mime


def validate_upload_file(file, check_mime=True):
    """
    Validación completa de archivo subido
    
    Args:
        file: FileStorage object de Flask
        check_mime: Si True, valida MIME type real (requiere python-magic)
        
    Returns:
        dict: Información del archivo validado
            {
                'filename': str,
                'safe_filename': str,
                'mime_type': str,
                'size': int
            }
        
    Raises:
        FileValidationError: Si alguna validación falla
    """
    if not file:
        raise FileValidationError('No se recibió ningún archivo')
    
    if not file.filename:
        raise FileValidationError('Archivo sin nombre')
    
    # 1. Validar tamaño
    validate_file_size(file)
    
    # 2. Validar y sanitizar nombre
    safe_filename = validate_filename(file.filename)
    
    # 3. Validar extensión
    validate_file_extension(safe_filename)
    
    # 4. Validar MIME type real (opcional pero recomendado)
    mime_type = None
    if check_mime:
        try:
            mime_type = validate_mime_type(file)
        except FileValidationError:
            # Si falla la detección de MIME, podemos decidir si es crítico
            # Por ahora, solo confiamos en extensión si falla
            pass
    
    # Obtener tamaño
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    
    return {
        'filename': file.filename,
        'safe_filename': safe_filename,
        'mime_type': mime_type,
        'size': size
    }


def get_unique_filename(directory, filename):
    """
    Genera un nombre de archivo único en el directorio dado
    
    Args:
        directory: Directorio donde se guardará
        filename: Nombre de archivo propuesto
        
    Returns:
        str: Nombre de archivo único
    """
    base_path = Path(directory)
    file_path = base_path / filename
    
    # Si no existe, usar el nombre original
    if not file_path.exists():
        return filename
    
    # Si existe, agregar contador
    name, ext = os.path.splitext(filename)
    counter = 1
    
    while file_path.exists():
        new_filename = f"{name}_{counter}{ext}"
        file_path = base_path / new_filename
        counter += 1
        
        # Prevenir loop infinito
        if counter > 1000:
            raise FileValidationError('No se pudo generar nombre único para el archivo')
    
    return file_path.name


def save_upload_file(file, upload_folder, make_unique=True, check_mime=True):
    """
    Valida y guarda un archivo de forma segura
    
    Args:
        file: FileStorage object de Flask
        upload_folder: Carpeta donde guardar
        make_unique: Si True, genera nombre único si ya existe
        check_mime: Si True, valida MIME type real
        
    Returns:
        dict: Información del archivo guardado
            {
                'filename': str,
                'filepath': str,
                'mime_type': str,
                'size': int
            }
        
    Raises:
        FileValidationError: Si alguna validación falla
    """
    # Validar archivo
    file_info = validate_upload_file(file, check_mime=check_mime)
    
    # Crear directorio si no existe
    upload_path = Path(upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Obtener nombre único si es necesario
    filename = file_info['safe_filename']
    if make_unique:
        filename = get_unique_filename(upload_folder, filename)
    
    # Guardar archivo
    filepath = upload_path / filename
    file.save(str(filepath))
    
    return {
        'filename': filename,
        'filepath': str(filepath),
        'mime_type': file_info['mime_type'],
        'size': file_info['size']
    }
