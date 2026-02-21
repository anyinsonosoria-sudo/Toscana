"""
Tests para utilidades y decoradores
"""

import pytest
from utils.permissions import check_permission, user_has_permission


@pytest.mark.unit
class TestPermissions:
    """Tests para el sistema de permisos"""
    
    def test_check_permission_function_exists(self):
        """Test que la función de permisos existe"""
        assert callable(check_permission)
        assert callable(user_has_permission)


@pytest.mark.unit
class TestDecorators:
    """Tests para decoradores"""
    
    def test_permission_required_decorator_exists(self):
        """Test que el decorador existe"""
        from utils.decorators import permission_required
        assert callable(permission_required)
    
    def test_audit_log_decorator_exists(self):
        """Test que el decorador de auditoría existe"""
        from utils.decorators import audit_log
        assert callable(audit_log)
