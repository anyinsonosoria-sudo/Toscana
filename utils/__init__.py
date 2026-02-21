"""
Utils Package
=============
Utilidades y helpers de la aplicación.
"""

from .decorators import role_required, admin_required, permission_required, audit_log, log_action
from .permissions import (
    get_all_permissions,
    get_permissions_by_module,
    get_user_permissions,
    user_has_permission,
    check_permission,
    grant_permission,
    revoke_permission,
    set_user_permissions
)
from .file_validator import save_upload_file, FileValidationError
from .pagination import Pagination, paginate, get_page_range

__all__ = [
    'role_required',
    'admin_required',
    'permission_required',
    'audit_log',
    'log_action',
    'get_all_permissions',
    'get_permissions_by_module',
    'get_user_permissions',
    'user_has_permission',
    'check_permission',
    'grant_permission',
    'revoke_permission',
    'set_user_permissions',
    'save_upload_file',
    'FileValidationError',
    'Pagination',
    'paginate',
    'get_page_range'
]
