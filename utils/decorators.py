"""
Custom Decorators - Autorización y Auditoría
Decoradores personalizados para control de acceso
"""

from functools import wraps
from flask import abort, flash, redirect, url_for, request, jsonify
from flask_login import current_user
import logging
from utils.permissions import check_permission

# Configurar logger
audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)

# Handler para archivo de auditoría
audit_handler = logging.FileHandler('audit.log')
audit_handler.setLevel(logging.INFO)
audit_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
audit_handler.setFormatter(audit_formatter)
audit_logger.addHandler(audit_handler)


def role_required(*roles):
    """
    Decorador para requerir roles específicos
    
    Uso:
        @app.route('/admin/users')
        @login_required
        @role_required('admin')
        def admin_users():
            ...
        
        @app.route('/edit')
        @login_required
        @role_required('admin', 'operator')  # Admin O Operador
        def edit_item():
            ...
    
    Args:
        *roles: Uno o más roles permitidos ('admin', 'operator', 'resident')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Debes iniciar sesión para acceder a esta página', 'error')
                return redirect(url_for('auth.login'))
            
            # Verificar si el usuario tiene alguno de los roles permitidos
            if current_user.role not in roles:
                audit_logger.warning(
                    f"ACCESO DENEGADO - Usuario: {current_user.username} "
                    f"(Rol: {current_user.role}) - Intentó acceder: {request.endpoint} "
                    f"- Roles requeridos: {roles}"
                )
                
                # Para solicitudes AJAX, devolver JSON
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False,
                        'error': f'No tienes permisos para acceder a esta función. Se requiere rol: {" o ".join(roles)}'
                    }), 403
                
                flash(f'No tienes permisos para acceder a esta función. Se requiere rol: {" o ".join(roles)}', 'error')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """
    Decorador específico para rutas de solo administradores
    Atajo para @role_required('admin')
    
    Uso:
        @app.route('/admin/settings')
        @login_required
        @admin_required
        def admin_settings():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Debes iniciar sesión para acceder a esta página', 'error')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin():
            audit_logger.warning(
                f"ACCESO DENEGADO - Usuario: {current_user.username} "
                f"(Rol: {current_user.role}) - Intentó acceder a área de admin: {request.endpoint}"
            )
            
            # Para solicitudes AJAX, devolver JSON
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'error': 'Esta función está restringida solo para administradores'
                }), 403
            
            flash('Esta función está restringida solo para administradores', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def permission_required(permission_name):
    """
    Decorador para verificar permisos granulares específicos
    Los administradores tienen todos los permisos automáticamente
    
    Uso:
        @app.route('/apartamentos/delete/<int:id>', methods=['POST'])
        @login_required
        @permission_required('apartamentos.delete')
        def delete_apartment(id):
            ...
        
        @app.route('/facturas/edit/<int:id>', methods=['POST'])
        @login_required
        @permission_required('facturacion.editar')
        def edit_invoice(id):
            ...
    
    Args:
        permission_name: Nombre del permiso requerido (ej: 'apartamentos.delete', 'facturacion.crear')
    
    Permisos disponibles por módulo:
        - Apartamentos: apartamentos.view, apartamentos.create, apartamentos.edit, apartamentos.delete
        - Residentes: residentes.view, residentes.create, residentes.edit, residentes.delete
        - Proveedores: proveedores.view, proveedores.create, proveedores.edit, proveedores.delete
        - Productos: productos.view, productos.create, productos.edit, productos.delete
        - Gastos: gastos.view, gastos.create, gastos.edit, gastos.delete, gastos.approve
        - Facturación: facturacion.view, facturacion.crear, facturacion.editar, facturacion.anular
        - Ventas: ventas.view, ventas.create, ventas.edit, ventas.delete
        - Contabilidad: contabilidad.view, contabilidad.export
        - Reportes: reportes.view, reportes.export
        - Empresa: empresa.view, empresa.edit
        - Personalización: personalizacion.view, personalizacion.edit
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Debes iniciar sesión para acceder a esta página', 'error')
                return redirect(url_for('auth.login'))
            
            # Verificar permiso (administradores pasan automáticamente)
            if not check_permission(current_user.id, permission_name, current_user.role):
                audit_logger.warning(
                    f"PERMISO DENEGADO - Usuario: {current_user.username} "
                    f"(Rol: {current_user.role}) - Permiso: {permission_name} "
                    f"- Endpoint: {request.endpoint}"
                )
                
                # Para solicitudes AJAX, devolver JSON
                if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False,
                        'error': f'No tienes permiso para realizar esta acción. Permiso requerido: {permission_name}'
                    }), 403
                
                flash(f'No tienes permiso para realizar esta acción. Permiso requerido: {permission_name}', 'warning')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def audit_log(action_type, description=None):
    """
    Decorador para registrar acciones en el log de auditoría
    
    Uso:
        @app.route('/delete/<int:id>', methods=['POST'])
        @login_required
        @admin_required
        @audit_log('DELETE', 'Eliminar apartamento')
        def delete_apartment(id):
            ...
    
    Args:
        action_type: Tipo de acción (CREATE, UPDATE, DELETE, VIEW, LOGIN, LOGOUT, etc.)
        description: Descripción opcional de la acción
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Ejecutar la función
            result = f(*args, **kwargs)
            
            # Registrar en auditoría
            user_info = f"{current_user.username} ({current_user.role})" if current_user.is_authenticated else "Anónimo"
            endpoint_info = request.endpoint or request.path
            
            log_msg = f"{action_type} - Usuario: {user_info} - Endpoint: {endpoint_info}"
            if description:
                log_msg += f" - {description}"
            
            # Agregar parámetros de la ruta si existen
            if kwargs:
                log_msg += f" - Params: {kwargs}"
            
            # Agregar IP del cliente
            client_ip = request.remote_addr
            log_msg += f" - IP: {client_ip}"
            
            audit_logger.info(log_msg)
            
            return result
        return decorated_function
    return decorator


def log_action(action_type, message):
    """
    Función auxiliar para registrar acciones manualmente
    
    Uso:
        from decorators import log_action
        
        log_action('UPDATE', f'Actualizado apartamento {apt_id}')
    """
    if current_user.is_authenticated:
        user_info = f"{current_user.username} ({current_user.role})"
    else:
        user_info = "Sistema"
    
    client_ip = request.remote_addr if request else "N/A"
    
    audit_logger.info(
        f"{action_type} - Usuario: {user_info} - {message} - IP: {client_ip}"
    )
