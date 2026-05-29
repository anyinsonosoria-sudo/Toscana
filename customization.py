import json

def get_sidebar_menu_order(defaults):
    """Devuelve la lista ordenada de menús para el sidebar según la configuración"""
    order_mode = get_setting("sidebar_order_mode", "custom")
    menu_order = get_setting("sidebar_menu_order")
    if menu_order:
        try:
            menu_order = json.loads(menu_order)
        except Exception:
            menu_order = [m["key"] for m in defaults]
    else:
        menu_order = [m["key"] for m in defaults]
    if order_mode == "alphabetical":
        sorted_objs = sorted(defaults, key=lambda m: m["label"].lower())
        return sorted_objs
    # Personalizado
    key_to_obj = {m["key"]: m for m in defaults}
    ordered = [key_to_obj[k] for k in menu_order if k in key_to_obj]
    # Agregar faltantes
    for m in defaults:
        if m["key"] not in [x["key"] for x in ordered]:
            ordered.append(m)
    return ordered
from typing import Dict, Optional
from db import get_conn

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a customization setting by key with request-level caching"""
    try:
        from flask import has_app_context, g
        if has_app_context():
            if 'customization_settings' not in g:
                g.customization_settings = get_all_settings()
            return g.customization_settings.get(key, default)
    except Exception:
        pass
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT setting_value FROM customization_settings WHERE setting_key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["setting_value"] if row else default

def set_setting(key: str, value: str) -> None:
    """Set a customization setting"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""INSERT INTO customization_settings(setting_key, setting_value, updated_at) 
                   VALUES(?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(setting_key) DO UPDATE SET 
                   setting_value=excluded.setting_value, 
                   updated_at=CURRENT_TIMESTAMP""",
                (key, value))
    conn.commit()
    conn.close()
    try:
        from flask import has_app_context, g
        if has_app_context() and 'customization_settings' in g:
            g.customization_settings[key] = value
    except Exception:
        pass

def get_all_settings() -> Dict[str, str]:
    """Get all customization settings as a dictionary with request-level caching"""
    try:
        from flask import has_app_context, g
        if has_app_context() and 'customization_settings' in g:
            return g.customization_settings
    except Exception:
        pass
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT setting_key, setting_value FROM customization_settings")
    rows = cur.fetchall()
    conn.close()
    result = {row["setting_key"]: row["setting_value"] for row in rows}
    try:
        from flask import has_app_context, g
        if has_app_context():
            g.customization_settings = result
    except Exception:
        pass
    return result

def get_settings_with_defaults() -> Dict[str, str]:
    """Get all settings with default values"""
    defaults = {
        "accent_color": "#795547",
        "logo_url": "",
        "display_logo": "1",
        "invoice_template": "modern",
        "company_name": "",
        "company_address": "",
        "company_phone": "",
        "company_email": ""
    }
    settings = get_all_settings()
    return {**defaults, **settings}
