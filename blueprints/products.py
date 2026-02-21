"""
Products/Services Blueprint
============================
Gestión de productos y servicios.
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

# Importar decoradores y utils
from utils.decorators import permission_required, audit_log
from utils.pagination import paginate
from extensions import cache

# Importar módulos de datos
import products_services
import customization

logger = logging.getLogger(__name__)

# Crear blueprint
products_bp = Blueprint('products', __name__, url_prefix='/productos')


@products_bp.route("/")
@login_required
@permission_required('productos.view')
@cache.cached(timeout=60, query_string=True)
def list():
    """Lista todos los productos y servicios con paginación"""
    try:
        products_services_list = products_services.list_products_services(active_only=False)
        custom_settings = customization.get_settings_with_defaults()
        
        # Aplicar paginación (20 items por página)
        pagination = paginate(products_services_list, per_page=20)
        
    except Exception as e:
        logger.error(f"Error loading products/services: {e}")
        pagination = paginate([], per_page=20)
        custom_settings = {}
    
    return render_template("productos.html", 
                         products_services=pagination.items,
                         pagination=pagination,
                         customization=custom_settings)


@products_bp.route("/add", methods=["POST"])
@login_required
@permission_required('productos.create')
@audit_log('CREATE', 'Agregar producto/servicio')
def add():
    """Agrega un nuevo producto o servicio"""
    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()
    type_val = request.form.get("type", "").strip()
    price_str = request.form.get("price", "0").strip()
    additional_notes = request.form.get("additional_notes", "").strip() or None
    
    # Convertir tipo de español a inglés para la BD
    type_mapping = {
        'Producto': 'product',
        'Servicio': 'service',
        'product': 'product',  # por si acaso ya viene en inglés
        'service': 'service'
    }
    type_val = type_mapping.get(type_val, type_val.lower())
    
    # Validaciones
    if not code:
        flash("Código es requerido.", "error")
        return redirect(url_for("products.list"))
    
    if not name:
        flash("Descripción es requerida.", "error")
        return redirect(url_for("products.list"))
    
    if not type_val:
        flash("Tipo es requerido.", "error")
        return redirect(url_for("products.list"))
    
    try:
        price = float(price_str) if price_str else 0
    except ValueError:
        flash("Precio inválido.", "error")
        return redirect(url_for("products.list"))
    
    try:
        products_services.add_product_service(
            name, type_val, price, code, None, additional_notes, 1
        )
        # Invalidar cache
        cache.clear()
        flash("Producto/Servicio agregado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al agregar producto/servicio: {e}", "error")
    
    return redirect(url_for("products.list"))


@products_bp.route("/edit/<int:id>", methods=["POST"])
@login_required
@permission_required('productos.edit')
@audit_log('UPDATE', 'Editar producto/servicio')
def edit(id):
    """Edita un producto o servicio existente"""
    code = request.form.get("code", "").strip()
    name = request.form.get("name", "").strip()
    type_val = request.form.get("type", "").strip()
    price_str = request.form.get("price", "0").strip()
    additional_notes = request.form.get("additional_notes", "").strip() or None
    active = 1 if request.form.get("active") else 0
    
    # Convertir tipo de español a inglés para la BD
    type_mapping = {
        'Producto': 'product',
        'Servicio': 'service',
        'product': 'product',
        'service': 'service'
    }
    type_val = type_mapping.get(type_val, type_val.lower())
    
    # Validaciones
    if not code:
        flash("Código es requerido.", "error")
        return redirect(url_for("products.list"))
    
    if not name:
        flash("Descripción es requerida.", "error")
        return redirect(url_for("products.list"))
    
    if not type_val:
        flash("Tipo es requerido.", "error")
        return redirect(url_for("products.list"))
    
    try:
        price = float(price_str) if price_str else 0
    except ValueError:
        flash("Precio inválido.", "error")
        return redirect(url_for("products.list"))
    
    try:
        products_services.update_product_service(
            id,
            name=name,
            code=code,
            type=type_val,
            price=price,
            additional_notes=additional_notes,
            active=active
        )
        # Invalidar cache
        cache.clear()
        flash("Producto/Servicio actualizado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al actualizar producto/servicio: {e}", "error")
    
    return redirect(url_for("products.list"))


@products_bp.route("/delete/<int:id>", methods=["POST"])
@login_required
@permission_required('productos.delete')
@audit_log('DELETE', 'Eliminar producto/servicio')
def delete(id):
    """Elimina un producto o servicio"""
    try:
        products_services.delete_product_service(id)
        # Invalidar cache
        cache.clear()
        flash("Producto/Servicio eliminado exitosamente.", "success")
    except Exception as e:
        flash(f"Error al eliminar producto/servicio: {e}", "error")
    
    return redirect(url_for("products.list"))
