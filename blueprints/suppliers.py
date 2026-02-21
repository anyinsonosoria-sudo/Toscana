"""
Suppliers Blueprint
===================
Gestión de proveedores/suplidores.
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required

# Importar decoradores y utils
from utils.decorators import permission_required, audit_log
from utils.pagination import paginate
from extensions import cache, csrf

# Importar módulos de datos
import suppliers
import customization

logger = logging.getLogger(__name__)

# Crear blueprint
suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/suplidores')


@suppliers_bp.route("/")
@login_required
@permission_required('proveedores.view')
@cache.cached(timeout=60, query_string=True)
def list():
    """Lista todos los proveedores con paginación"""
    try:
        suppliers_list = suppliers.list_suppliers()
        custom_settings = customization.get_settings_with_defaults()
        
        # Aplicar paginación (20 items por página)
        pagination = paginate(suppliers_list, per_page=20)
        
    except Exception as e:
        logger.error(f"Error loading suppliers: {e}")
        pagination = paginate([], per_page=20)
        custom_settings = {}
    
    return render_template("suplidores.html", 
                         suppliers=pagination.items,
                         pagination=pagination,
                         customization=custom_settings)


@suppliers_bp.route("/add", methods=["POST"])
@login_required
@permission_required('proveedores.create')
@audit_log('CREATE', 'Agregar suplidor')
def add():
    """Agrega un nuevo proveedor"""
    name = request.form.get("name", "").strip()
    supplier_type = request.form.get("supplier_type", "").strip() or None
    supplier_type_other = request.form.get("supplier_type_other", "").strip() or None
    
    if not name:
        flash("Nombre del suplidor es requerido.", "error")
        return redirect(url_for("suppliers.list"))
    
    if not supplier_type:
        flash("Tipo de suplidor es requerido.", "error")
        return redirect(url_for("suppliers.list"))
    
    contact_name = request.form.get("contact_name", "").strip() or None
    email = request.form.get("email", "").strip() or None
    phone = request.form.get("phone", "").strip() or None
    address = request.form.get("address", "").strip() or None
    tax_id = request.form.get("tax_id", "").strip() or None
    payment_terms = int(request.form.get("payment_terms", "30"))
    
    try:
        suppliers.add_supplier(
            name, supplier_type, supplier_type_other, 
            contact_name, email, phone, address, 
            tax_id, payment_terms
        )
        # Invalidar cache
        cache.delete_memoized(list)
        flash("Suplidor agregado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al agregar suplidor: {e}", "error")
    
    return redirect(url_for("suppliers.list"))


@suppliers_bp.route("/edit/<int:id>", methods=["POST"])
@login_required
@permission_required('proveedores.edit')
@audit_log('UPDATE', 'Editar suplidor')
def edit(id):
    """Edita un proveedor existente"""
    name = request.form.get("name", "").strip()
    supplier_type = request.form.get("supplier_type", "").strip() or None
    supplier_type_other = request.form.get("supplier_type_other", "").strip() or None
    
    if not name:
        flash("Nombre del suplidor es requerido.", "error")
        return redirect(url_for("suppliers.list"))
    
    if not supplier_type:
        flash("Tipo de suplidor es requerido.", "error")
        return redirect(url_for("suppliers.list"))
    
    contact_name = request.form.get("contact_name", "").strip() or None
    email = request.form.get("email", "").strip() or None
    phone = request.form.get("phone", "").strip() or None
    address = request.form.get("address", "").strip() or None
    tax_id = request.form.get("tax_id", "").strip() or None
    payment_terms = int(request.form.get("payment_terms", "30"))
    
    try:
        suppliers.update_supplier(
            id, 
            name=name, 
            supplier_type=supplier_type, 
            supplier_type_other=supplier_type_other,
            contact_name=contact_name, 
            email=email, 
            phone=phone, 
            address=address, 
            tax_id=tax_id, 
            payment_terms=payment_terms
        )
        # Invalidar cache
        cache.delete_memoized(list)
        flash("Suplidor actualizado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al actualizar suplidor: {e}", "error")
    
    return redirect(url_for("suppliers.list"))


@suppliers_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
@permission_required('proveedores.delete')
@audit_log('DELETE', 'Eliminar suplidor')
def delete(id):
    """Elimina un proveedor"""
    try:
        suppliers.delete_supplier(id)
        # Invalidar cache
        cache.delete_memoized(list)
        flash("Suplidor eliminado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al eliminar suplidor: {e}", "error")
    
    return redirect(url_for("suppliers.list"))


# ========== API JSON ==========

@suppliers_bp.route("/api/list", methods=["GET"])
@login_required
@csrf.exempt
def api_list():
    """Devuelve lista de proveedores como JSON."""
    try:
        slist = suppliers.list_suppliers()
        return jsonify({'success': True, 'suppliers': [
            {'id': s['id'], 'name': s['name'], 'type': s.get('supplier_type', ''),
             'phone': s.get('phone', ''), 'email': s.get('email', '')}
            for s in slist
        ]})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@suppliers_bp.route("/api/create", methods=["POST"])
@login_required
@csrf.exempt
@permission_required('proveedores.create')
def api_create():
    """Crea un proveedor via JSON y devuelve su ID."""
    try:
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'success': False, 'error': 'Nombre requerido'}), 400
        supplier_type = data.get('supplier_type', 'General')
        phone = data.get('phone', '').strip() or None
        email = data.get('email', '').strip() or None
        new_id = suppliers.add_supplier(name, supplier_type, phone=phone, email=email)
        cache.delete_memoized(list)
        return jsonify({'success': True, 'id': new_id, 'name': name})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
