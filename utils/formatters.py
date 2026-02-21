"""
Formatters Utility
==================
Funciones de formato para montos, fechas, etc.
"""

from datetime import datetime


def format_currency(value, currency="RD$"):
    """
    Formatea un número como moneda.
    
    Args:
        value: Número a formatear
        currency: Símbolo de moneda (default: "RD$")
    
    Returns:
        str: Valor formateado (ej: "RD$ 1,000.00")
    """
    try:
        value = float(value)
        return f"{currency} {value:,.2f}"
    except (ValueError, TypeError):
        return f"{currency} 0.00"


def format_date(date_obj, format="%d/%m/%Y"):
    """
    Formatea un objeto datetime.
    
    Args:
        date_obj: Objeto datetime o string ISO
        format: Formato de salida (default: "dd/mm/yyyy")
    
    Returns:
        str: Fecha formateada
    """
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj)
        except:
            return date_obj
    
    if isinstance(date_obj, datetime):
        return date_obj.strftime(format)
    
    return str(date_obj)


def format_datetime(datetime_obj, format="%d/%m/%Y %H:%M"):
    """
    Formatea un objeto datetime con hora.
    
    Args:
        datetime_obj: Objeto datetime o string ISO
        format: Formato de salida (default: "dd/mm/yyyy HH:MM")
    
    Returns:
        str: Fecha y hora formateadas
    """
    return format_date(datetime_obj, format)


def truncate_text(text, max_length=50, suffix="..."):
    """
    Trunca un texto largo.
    
    Args:
        text: Texto a truncar
        max_length: Longitud máxima
        suffix: Sufijo para texto truncado
    
    Returns:
        str: Texto truncado
    """
    if not text:
        return ""
    
    text = str(text)
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def parse_currency(value_str):
    """
    Convierte string de moneda a float.
    
    Args:
        value_str: String con moneda (ej: "RD$ 1,000.00" o "1000")
    
    Returns:
        float: Valor numérico
    """
    if not value_str:
        return 0.0
    
    # Remover símbolos de moneda y comas
    value_str = str(value_str).replace("RD$", "").replace("$", "").replace(",", "").strip()
    
    try:
        return float(value_str)
    except ValueError:
        return 0.0
