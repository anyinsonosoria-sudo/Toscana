"""
Tests para los blueprints principales
"""

import pytest


@pytest.mark.integration
class TestApartmentsBlueprint:
    """Tests para el blueprint de apartamentos"""
    
    def test_list_apartments(self, auth_client):
        """Test listar apartamentos"""
        response = auth_client.get('/apartamentos/')
        assert response.status_code == 200
    
    def test_add_apartment_form_loads(self, auth_client):
        """Test que el formulario de agregar carga"""
        response = auth_client.get('/apartamentos/')
        assert response.status_code == 200
        assert b'apartamento' in response.data.lower()


@pytest.mark.integration
class TestSuppliersBlueprint:
    """Tests para el blueprint de suplidores"""
    
    def test_list_suppliers(self, auth_client):
        """Test listar suplidores"""
        response = auth_client.get('/suplidores/')
        assert response.status_code == 200
    
    def test_suppliers_requires_auth(self, client):
        """Test que requiere autenticación"""
        response = client.get('/suplidores/')
        assert response.status_code == 302


@pytest.mark.integration
class TestProductsBlueprint:
    """Tests para el blueprint de productos"""
    
    def test_list_products(self, auth_client):
        """Test listar productos"""
        response = auth_client.get('/productos/')
        assert response.status_code == 200
    
    def test_products_requires_auth(self, client):
        """Test que requiere autenticación"""
        response = client.get('/productos/')
        assert response.status_code == 302


@pytest.mark.integration
class TestExpensesBlueprint:
    """Tests para el blueprint de gastos"""
    
    def test_list_expenses(self, auth_client):
        """Test listar gastos"""
        response = auth_client.get('/gastos/')
        assert response.status_code == 200
    
    def test_expenses_requires_auth(self, client):
        """Test que requiere autenticación"""
        response = client.get('/gastos/')
        assert response.status_code == 302


@pytest.mark.integration
class TestBillingBlueprint:
    """Tests para el blueprint de facturación"""
    
    def test_list_invoices(self, auth_client):
        """Test listar facturas"""
        response = auth_client.get('/facturacion')
        assert response.status_code == 200
    
    def test_billing_requires_auth(self, client):
        """Test que requiere autenticación"""
        response = client.get('/facturacion')
        assert response.status_code == 302


@pytest.mark.integration
class TestReportsBlueprint:
    """Tests para el blueprint de reportes"""
    
    def test_list_reports(self, auth_client):
        """Test ver reportes"""
        response = auth_client.get('/reportes/')
        assert response.status_code in [200, 429]  # 429 si rate limit activo
    
    def test_reports_requires_auth(self, client):
        """Test que requiere autenticación"""
        response = client.get('/reportes/')
        assert response.status_code == 302


@pytest.mark.integration
class TestAccountingBlueprint:
    """Tests para el blueprint de contabilidad"""
    
    def test_list_accounting(self, auth_client):
        """Test ver contabilidad"""
        response = auth_client.get('/contabilidad/')
        assert response.status_code == 200
    
    def test_accounting_requires_auth(self, client):
        """Test que requiere autenticación"""
        response = client.get('/contabilidad/')
        assert response.status_code == 302


@pytest.mark.integration
class TestCompanyBlueprint:
    """Tests para el blueprint de empresa"""
    
    def test_view_company(self, auth_client):
        """Test ver información de empresa"""
        response = auth_client.get('/empresa/')
        assert response.status_code == 200
    
    def test_company_requires_auth(self, client):
        """Test que requiere autenticación"""
        response = client.get('/empresa/')
        assert response.status_code == 302
