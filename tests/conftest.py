"""
Configuración de pytest para el sistema Building Maintenance
"""

import pytest
import sys
from pathlib import Path

# Agregar directorio raíz al path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


@pytest.fixture(scope='session')
def app():
    """Crear aplicación Flask para testing"""
    # Importar aquí para evitar circular imports
    import os
    os.environ['TESTING'] = 'True'
    os.environ['DATABASE_NAME'] = 'test_data.db'
    
    from app import create_app
    
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Deshabilitar CSRF en tests
    app.config['LOGIN_DISABLED'] = False
    
    yield app
    
    # Cleanup
    test_db = Path(root_dir) / 'test_data.db'
    if test_db.exists():
        test_db.unlink()


@pytest.fixture(scope='function')
def client(app):
    """Cliente de testing Flask"""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """CLI runner para testing"""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def auth_client(client):
    """Cliente autenticado como admin"""
    # Login como admin
    client.post('/auth/login', data={
        'username': 'admin',
        'password': 'admin123'
    }, follow_redirects=True)
    
    yield client
    
    # Logout
    client.get('/auth/logout', follow_redirects=True)
