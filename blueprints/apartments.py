"""
Apartments Blueprint
====================
Gestión de apartamentos y residentes.
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from utils.decorators import permission_required, audit_log
from utils.pagination import paginate
from extensions import cache, csrf
import apartments
import customization

logger = logging.getLogger(__name__)

apartments_bp = Blueprint('apartments', __name__, url_prefix='/apartamentos')

@apartments_bp.route("/", endpoint="list")
@login_required
@permission_required('apartamentos.view')
def apartments_list():
    """Lista todos los apartamentos con paginación"""
    try:
        apts = apartments.list_apartments()
        custom_settings = customization.get_settings_with_defaults()
        pagination = paginate(apts, per_page=20)
        
        # Si la página solicitada está vacía pero hay apartamentos, redirigir a primera página
        if not pagination.items and len(apts) > 0:
            return redirect(url_for('apartments.list', page=1))
            
    except Exception as e:
        logger.error(f"Error loading apartments: {e}")
        apts = []
        pagination = paginate([], per_page=20)
        custom_settings = {}
        flash("Error al cargar apartamentos. Intente nuevamente.", "error")
    return render_template("apartamentos.html", 
        apartments=apts,
        pagination=pagination,
        customization=custom_settings)

@apartments_bp.route("/add", methods=["POST"])
@login_required
@permission_required('apartamentos.create')
@audit_log('CREATE', 'Agregar apartamento')
def add():
    """Agrega un nuevo apartamento"""
    number = request.form.get("number", "").strip()
    floor = request.form.get("floor", "").strip()
    notes = request.form.get("notes", "").strip()
    resident_name = request.form.get("resident_name", "").strip()
    resident_role = request.form.get("resident_role", "tenant")
    resident_email = request.form.get("resident_email", "").strip()
    resident_phone = request.form.get("resident_phone", "").strip()
    payment_terms = request.form.get("payment_terms", "30")

    if not number:
        flash("Número de apartamento es requerido.", "error")
        return redirect(url_for("apartments.list"))

    try:
        payment_terms_int = int(payment_terms) if payment_terms else 30
        apt_id = apartments.add_apartment(
            number, 
            floor or None, 
            notes or None,
            resident_name or None,
            resident_role,
            resident_email or None,
            resident_phone or None,
            payment_terms_int
        )
        # Procesar residentes adicionales
        extra_names = request.form.getlist('extra_name[]')
        extra_roles = request.form.getlist('extra_role[]')
        extra_emails = request.form.getlist('extra_email[]')
        extra_phones = request.form.getlist('extra_phone[]')
        extras = []
        for i, name in enumerate(extra_names):
            name = name.strip()
            if name:
                extras.append({
                    'name': name,
                    'role': extra_roles[i] if i < len(extra_roles) else 'tenant',
                    'email': extra_emails[i].strip() if i < len(extra_emails) else '',
                    'phone': extra_phones[i].strip() if i < len(extra_phones) else '',
                })
        if extras:
            apartments.save_extra_residents(apt_id, extras)
        # Invalidar cache
        cache.clear()
        flash("Apartamento agregado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al agregar apartamento: {e}", "error")
    
    return redirect(url_for("apartments.list"))


@apartments_bp.route("/edit/<int:id>", methods=["POST"])
@login_required
@permission_required('apartamentos.edit')
@audit_log('UPDATE', 'Editar apartamento')
def edit(id):
    """Edita un apartamento existente"""
    fields = {}
    
    if "number" in request.form:
        fields["number"] = request.form["number"].strip()
    if "floor" in request.form:
        fields["floor"] = request.form["floor"].strip() or None
    if "notes" in request.form:
        fields["notes"] = request.form["notes"].strip() or None
    if "resident_name" in request.form:
        fields["resident_name"] = request.form["resident_name"].strip() or None
    if "resident_role" in request.form:
        fields["resident_role"] = request.form["resident_role"]
    if "resident_email" in request.form:
        fields["resident_email"] = request.form["resident_email"].strip() or None
    if "resident_phone" in request.form:
        fields["resident_phone"] = request.form["resident_phone"].strip() or None
    if "payment_terms" in request.form:
        try:
            fields["payment_terms"] = int(request.form["payment_terms"])
        except:
            fields["payment_terms"] = 30
    
    try:
        apartments.update_apartment(id, **fields)
        # Procesar residentes adicionales (reemplaza los anteriores)
        extra_names = request.form.getlist('extra_name[]')
        extra_roles = request.form.getlist('extra_role[]')
        extra_emails = request.form.getlist('extra_email[]')
        extra_phones = request.form.getlist('extra_phone[]')
        extras = []
        for i, name in enumerate(extra_names):
            name = name.strip()
            if name:
                extras.append({
                    'name': name,
                    'role': extra_roles[i] if i < len(extra_roles) else 'tenant',
                    'email': extra_emails[i].strip() if i < len(extra_emails) else '',
                    'phone': extra_phones[i].strip() if i < len(extra_phones) else '',
                })
        apartments.save_extra_residents(id, extras)
        # Invalidar cache
        cache.clear()
        flash("Apartamento actualizado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al actualizar apartamento: {e}", "error")
    
    return redirect(url_for("apartments.list"))


@apartments_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
@permission_required('apartamentos.delete')
@audit_log('DELETE', 'Eliminar apartamento')
def delete(id):
    """Elimina un apartamento"""
    try:
        apartments.delete_apartment(id)
        # Invalidar cache
        cache.clear()
        flash("Apartamento eliminado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al eliminar apartamento: {e}", "error")
    
    return redirect(url_for("apartments.list"))
