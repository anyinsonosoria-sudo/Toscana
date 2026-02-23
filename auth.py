"""
Authentication Blueprint - Sistema de Login/Logout
Maneja autenticación de usuarios
"""

import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import user_model
import customization
import company
from utils import permissions as perm_module
from extensions import limiter, csrf


def _login_context():
    """Build context dict for login template."""
    custom = customization.get_settings_with_defaults()
    accent = customization.get_setting('accent_color', '#795548')
    try:
        co = company.get_company_info() or {}
    except Exception:
        co = {}
    return dict(customization=custom, accent_color=accent, company_info=co)

logger = logging.getLogger(__name__)

# Crear blueprint
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Página de login con protección contra fuerza bruta"""
    
    # Si ya está autenticado, redirigir al dashboard
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)
        
        # Validaciones básicas
        if not username or not password:
            flash('Usuario y contraseña son requeridos', 'error')
            return render_template('login.html', **_login_context())
        
        # Buscar usuario
        user = user_model.get_user_by_username(username)
        
        if user is None:
            flash('Usuario o contraseña incorrectos', 'error')
            return render_template('login.html', **_login_context())
        
        # Verificar si está activo
        if not user.is_active:
            flash('Usuario desactivado. Contacte al administrador', 'error')
            return render_template('login.html', **_login_context())
        
        # Verificar contraseña
        if not user.check_password(password):
            flash('Usuario o contraseña incorrectos', 'error')
            return render_template('login.html', **_login_context())
        
        # Login exitoso
        login_user(user, remember=remember)
        user_model.update_last_login(user.id)
        
        flash(f'Bienvenido, {user.full_name or user.username}!', 'success')
        
        # Redirigir a la página solicitada o al dashboard
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        
        return redirect(url_for('index'))
    
    # GET request - mostrar formulario
    return render_template('login.html', **_login_context())


@auth_bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    username = current_user.username
    logout_user()
    flash(f'Sesión cerrada correctamente. Hasta pronto, {username}!', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
@limiter.limit("10 per hour")
def register():
    """
    Registro de nuevos usuarios (solo admins) con rate limiting
    """
    
    # Solo administradores pueden registrar usuarios
    if not current_user.is_admin():
        flash('No tienes permisos para registrar usuarios', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'operator')
        
        # Validaciones
        errors = []
        
        if not username or len(username) < 3:
            errors.append('El usuario debe tener al menos 3 caracteres')
        
        if not email or '@' not in email:
            errors.append('Email inválido')
        
        if not password or len(password) < 6:
            errors.append('La contraseña debe tener al menos 6 caracteres')
        
        if password != password_confirm:
            errors.append('Las contraseñas no coinciden')
        
        if role not in ['admin', 'operator', 'resident']:
            errors.append('Rol inválido')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('register.html')
        
        # Intentar crear usuario
        try:
            user_id = user_model.create_user(
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                role=role
            )
            
            flash(f'Usuario {username} creado exitosamente', 'success')
            return redirect(url_for('auth.list_users'))
            
        except ValueError as e:
            flash(str(e), 'error')
            return render_template('register.html')
        except Exception as e:
            flash(f'Error al crear usuario: {str(e)}', 'error')
            return render_template('register.html')
    
    # GET request
    return render_template('register.html')


@auth_bp.route('/users')
@login_required
def list_users():
    """Lista de usuarios (solo admins)"""
    
    if not current_user.is_admin():
        flash('No tienes permisos para ver usuarios', 'error')
        return redirect(url_for('index'))
    
    users = user_model.list_users()
    return render_template('users.html', users=users)


@auth_bp.route('/users/deactivate/<int:user_id>', methods=['POST'])
@login_required
def deactivate_user(user_id):
    """Desactivar usuario (solo admins)"""
    
    if not current_user.is_admin():
        flash('No tienes permisos para desactivar usuarios', 'error')
        return redirect(url_for('index'))
    
    # No permitir desactivarse a sí mismo
    if user_id == current_user.id:
        flash('No puedes desactivar tu propio usuario', 'error')
        return redirect(url_for('auth.list_users'))
    
    try:
        user_model.deactivate_user(user_id)
        flash('Usuario desactivado correctamente', 'success')
    except Exception as e:
        flash(f'Error al desactivar usuario: {str(e)}', 'error')
    
    return redirect(url_for('auth.list_users'))


@auth_bp.route('/users/activate/<int:user_id>', methods=['POST'])
@login_required
def activate_user(user_id):
    """Activar usuario (solo admins)"""
    
    if not current_user.is_admin():
        flash('No tienes permisos para activar usuarios', 'error')
        return redirect(url_for('index'))
    
    try:
        user_model.activate_user(user_id)
        flash('Usuario activado correctamente', 'success')
    except Exception as e:
        flash(f'Error al activar usuario: {str(e)}', 'error')
    
    return redirect(url_for('auth.list_users'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Cambiar contraseña del usuario actual"""
    
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validaciones
        if not current_user.check_password(current_password):
            flash('Contraseña actual incorrecta', 'error')
            return render_template('change_password.html')
        
        if len(new_password) < 6:
            flash('La nueva contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('change_password.html')
        
        # Actualizar contraseña
        try:
            user_model.update_password(current_user.id, new_password)
            flash('Contraseña actualizada correctamente', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            flash(f'Error al actualizar contraseña: {str(e)}', 'error')
            return render_template('change_password.html')
    
    # GET request
    return render_template('change_password.html')

@auth_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """Editar usuario y asignar rol"""
    from utils.decorators import admin_required
    
    # Solo admin puede editar usuarios
    if current_user.role != 'admin':
        flash('No tienes permisos para editar usuarios', 'error')
        return redirect(url_for('auth.list_users'))
    
    user = user_model.get_user_by_id(user_id)
    if not user:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('auth.list_users'))
    
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'operator')
        
        # Validar rol
        if role not in ['admin', 'operator', 'resident']:
            flash('Rol inválido', 'error')
            return render_template('edit_user.html', user=user)
        
        # No permitir cambiar rol del usuario actual
        if user_id == current_user.id:
            flash('No puedes cambiar tu propio rol', 'error')
            return render_template('edit_user.html', user=user)
        
        try:
            # Actualizar usuario
            conn = user_model.get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users
                SET full_name = ?, email = ?, role = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (full_name, email, role, user_id))
            conn.commit()
            conn.close()
            
            flash(f'Usuario {user.username} actualizado correctamente', 'success')
            return redirect(url_for('auth.list_users'))
        except Exception as e:
            flash(f'Error al actualizar usuario: {str(e)}', 'error')
    
    return render_template('edit_user.html', user=user)


@auth_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Eliminar usuario"""
    
    # Solo admin puede eliminar
    if current_user.role != 'admin':
        flash('No tienes permisos para eliminar usuarios', 'error')
        return redirect(url_for('auth.list_users'))
    
    # No permitir eliminar usuario actual
    if user_id == current_user.id:
        flash('No puedes eliminar tu propia cuenta', 'error')
        return redirect(url_for('auth.list_users'))
    
    try:
        conn = user_model.get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        flash('Usuario eliminado correctamente', 'success')
    except Exception as e:
        flash(f'Error al eliminar usuario: {str(e)}', 'error')
    
    return redirect(url_for('auth.list_users'))


@auth_bp.route('/users/<int:user_id>/permissions', methods=['GET', 'POST'])
@login_required
def manage_user_permissions(user_id):
    """Gestionar permisos de un usuario"""
    
    # Solo admin puede gestionar permisos
    if current_user.role != 'admin':
        flash('No tienes permisos para gestionar permisos', 'error')
        return redirect(url_for('auth.list_users'))
    
    user = user_model.get_user_by_id(user_id)
    if not user:
        flash('Usuario no encontrado', 'error')
        return redirect(url_for('auth.list_users'))
    
    # Admin siempre tiene todos los permisos, no se pueden editar
    if user.role == 'admin':
        flash('Los administradores tienen todos los permisos por defecto', 'info')
        return redirect(url_for('auth.list_users'))
    
    if request.method == 'POST':
        # Obtener permisos seleccionados del formulario
        selected_permissions = request.form.getlist('permissions')
        
        try:
            # Actualizar permisos
            perm_module.set_user_permissions(user_id, selected_permissions, current_user.id)
            flash(f'Permisos de {user.username} actualizados correctamente', 'success')
            return redirect(url_for('auth.list_users'))
        except Exception as e:
            flash(f'Error al actualizar permisos: {str(e)}', 'error')
    
    # GET request
    permissions_by_module = perm_module.get_permissions_by_module()
    user_permissions = perm_module.get_user_permissions(user_id)
    
    return render_template('manage_permissions.html', 
                         user=user, 
                         permissions_by_module=permissions_by_module,
                         user_permissions=user_permissions)