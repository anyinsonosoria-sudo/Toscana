"""
Blueprint: Company
Gestion de informacion de la empresa/administrador
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from flask_login import login_required
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime

from utils.decorators import admin_required, permission_required, audit_log
from utils.file_validator import validate_upload_file, FileValidationError
import company
import customization

logger = logging.getLogger(__name__)

# Crear blueprint
company_bp = Blueprint('company', __name__, url_prefix='/empresa')


def allowed_file(filename):
    """Verificar si el archivo tiene una extension permitida (legacy)"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@company_bp.route('/')
@login_required
@permission_required('empresa.view')
def view():
    """Vista de información de la empresa"""
    try:
        info = company.get_company_info()
        custom_settings = customization.get_settings_with_defaults()
    except Exception:
        info = None
        custom_settings = {}
    
    return render_template("empresa.html", 
                         company=info, 
                         customization=custom_settings)


@company_bp.route('/update', methods=['POST'])
@login_required
@permission_required('empresa.edit')
@audit_log('UPDATE', 'Actualizar datos de empresa')
def update():
    """Actualizar información de la empresa"""
    name = request.form.get("name", "").strip()
    
    if not name:
        flash("El nombre de la empresa/administrador es requerido.", "error")
        return redirect(url_for("company.view"))
    
    # Manejar subida de logo
    logo_path = None
    
    if "logo_file" in request.files:
        file = request.files["logo_file"]
        
        if file and file.filename:
            # Validacion segura del archivo (extension + magic bytes)
            try:
                file_info = validate_upload_file(file, check_mime=True)
                logger.info(f"Logo validado: {file_info['safe_filename']}")
                
                # Obtener info actual para eliminar logo antiguo
                try:
                    current_info = company.get_company_info()
                    if current_info and current_info.get("logo_path"):
                        old_logo = Path(current_app.config["UPLOAD_FOLDER"]) / current_info["logo_path"]
                        if old_logo.exists():
                            old_logo.unlink()
                except Exception:
                    pass
                
                # Guardar nuevo logo con nombre seguro
                filename = file_info['safe_filename']
                # Agregar timestamp para evitar conflictos
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                name_parts = filename.rsplit(".", 1)
                filename = f"logo_{timestamp}.{name_parts[1]}" if len(name_parts) == 2 else f"logo_{timestamp}"
                
                file.save(Path(current_app.config["UPLOAD_FOLDER"]) / filename)
                logo_path = filename
                
            except FileValidationError as e:
                logger.warning(f"Logo rechazado: {e}")
                flash(f"Archivo no valido: {e}", "warning")
    
    # Si no se subio nuevo archivo, mantener logo existente
    if logo_path is None:
        try:
            current_info = company.get_company_info()
            if current_info:
                logo_path = current_info.get("logo_path")
        except Exception:
            pass
    
    try:
        company.update_company_info(
            name=name,
            legal_id=request.form.get("legal_id", "").strip() or None,
            address=request.form.get("address", "").strip() or None,
            city=request.form.get("city", "").strip() or None,
            country=request.form.get("country", "").strip() or None,
            phone=request.form.get("phone", "").strip() or None,
            email=request.form.get("email", "").strip() or None,
            website=request.form.get("website", "").strip() or None,
            bank_name=request.form.get("bank_name", "").strip() or None,
            bank_account=request.form.get("bank_account", "").strip() or None,
            bank_routing=request.form.get("bank_routing", "").strip() or None,
            tax_id=request.form.get("tax_id", "").strip() or None,
            logo_path=logo_path,
            notes=request.form.get("notes", "").strip() or None
        )
        flash("Información de la empresa actualizada exitosamente.", "success")
    except Exception as e:
        flash(f"Error al actualizar información: {e}", "error")
    
    # Redirigir al origen: si vino de /configuracion/, volver allí
    referrer = request.referrer or ''
    if '/configuracion' in referrer:
        return redirect(url_for('settings.view'))
    return redirect(url_for("company.view"))


@company_bp.route('/delete-logo', methods=['POST'])
@login_required
@permission_required('empresa.edit')
@audit_log('DELETE', 'Eliminar logo de empresa')
def delete_logo():
    """Eliminar logo de la empresa"""
    try:
        current_info = company.get_company_info()
        
        if current_info and current_info.get("logo_path"):
            # Eliminar archivo del disco
            logo_file = Path(current_app.config["UPLOAD_FOLDER"]) / current_info["logo_path"]
            if logo_file.exists():
                logo_file.unlink()
            
            # Actualizar base de datos para remover logo_path
            company.update_company_info(
                name=current_info["name"],
                legal_id=current_info.get("legal_id"),
                address=current_info.get("address"),
                city=current_info.get("city"),
                country=current_info.get("country"),
                phone=current_info.get("phone"),
                email=current_info.get("email"),
                website=current_info.get("website"),
                bank_name=current_info.get("bank_name"),
                bank_account=current_info.get("bank_account"),
                bank_routing=current_info.get("bank_routing"),
                tax_id=current_info.get("tax_id"),
                logo_path=None,
                notes=current_info.get("notes")
            )
            flash("Logo eliminado exitosamente.", "success")
        else:
            flash("No hay logo para eliminar.", "info")
            
    except Exception as e:
        flash(f"Error al eliminar logo: {e}", "error")
    
    return redirect(url_for("company.view"))
