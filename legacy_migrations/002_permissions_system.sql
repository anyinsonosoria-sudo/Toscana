-- Migración: Sistema de permisos granulares
-- Fecha: 2026-01-16

-- 1. Eliminar tablas existentes si existen
DROP TABLE IF EXISTS user_permissions;
DROP TABLE IF EXISTS permissions;

-- 2. Tabla de permisos
CREATE TABLE permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    module TEXT NOT NULL,
    action TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Tabla de relación usuarios-permisos
CREATE TABLE user_permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    permission_id INTEGER NOT NULL,
    granted_by INTEGER,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
    FOREIGN KEY (granted_by) REFERENCES users(id),
    UNIQUE(user_id, permission_id)
);

-- 3. Insertar permisos por módulo
INSERT OR IGNORE INTO permissions (name, module, action, description) VALUES
-- APARTAMENTOS
('apartamentos.view', 'apartamentos', 'view', 'Ver lista de apartamentos'),
('apartamentos.create', 'apartamentos', 'create', 'Crear nuevos apartamentos'),
('apartamentos.edit', 'apartamentos', 'edit', 'Editar apartamentos existentes'),
('apartamentos.delete', 'apartamentos', 'delete', 'Eliminar apartamentos'),

-- FACTURACIÓN
('facturacion.view', 'facturacion', 'view', 'Ver facturas'),
('facturacion.create', 'facturacion', 'create', 'Crear nuevas facturas'),
('facturacion.edit', 'facturacion', 'edit', 'Editar facturas'),
('facturacion.delete', 'facturacion', 'delete', 'Eliminar facturas'),
('facturacion.duplicate', 'facturacion', 'duplicate', 'Duplicar facturas'),

-- PAGOS
('pagos.view', 'pagos', 'view', 'Ver pagos'),
('pagos.create', 'pagos', 'create', 'Registrar pagos'),
('pagos.edit', 'pagos', 'edit', 'Editar pagos'),
('pagos.delete', 'pagos', 'delete', 'Eliminar pagos'),
('pagos.send_receipt', 'pagos', 'send_receipt', 'Enviar recibos'),

-- GASTOS
('gastos.view', 'gastos', 'view', 'Ver gastos'),
('gastos.create', 'gastos', 'create', 'Crear gastos'),
('gastos.edit', 'gastos', 'edit', 'Editar gastos'),
('gastos.delete', 'gastos', 'delete', 'Eliminar gastos'),

-- SUPLIDORES
('suplidores.view', 'suplidores', 'view', 'Ver suplidores'),
('suplidores.create', 'suplidores', 'create', 'Crear suplidores'),
('suplidores.edit', 'suplidores', 'edit', 'Editar suplidores'),
('suplidores.delete', 'suplidores', 'delete', 'Eliminar suplidores'),

-- PRODUCTOS/SERVICIOS
('productos.view', 'productos', 'view', 'Ver productos y servicios'),
('productos.create', 'productos', 'create', 'Crear productos y servicios'),
('productos.edit', 'productos', 'edit', 'Editar productos y servicios'),
('productos.delete', 'productos', 'delete', 'Eliminar productos y servicios'),

-- CONTABILIDAD
('contabilidad.view', 'contabilidad', 'view', 'Ver registros contables'),
('contabilidad.create', 'contabilidad', 'create', 'Crear registros contables'),
('contabilidad.edit', 'contabilidad', 'edit', 'Editar registros contables'),
('contabilidad.delete', 'contabilidad', 'delete', 'Eliminar registros contables'),

-- REPORTES
('reportes.view', 'reportes', 'view', 'Ver reportes'),
('reportes.export', 'reportes', 'export', 'Exportar reportes'),

-- CONFIGURACIÓN
('configuracion.view', 'configuracion', 'view', 'Ver configuración'),
('configuracion.edit', 'configuracion', 'edit', 'Modificar configuración'),

-- EMPRESA
('empresa.view', 'empresa', 'view', 'Ver datos de empresa'),
('empresa.edit', 'empresa', 'edit', 'Editar datos de empresa'),

-- USUARIOS (solo admin por defecto)
('usuarios.view', 'usuarios', 'view', 'Ver usuarios del sistema'),
('usuarios.create', 'usuarios', 'create', 'Crear nuevos usuarios'),
('usuarios.edit', 'usuarios', 'edit', 'Editar usuarios'),
('usuarios.delete', 'usuarios', 'delete', 'Eliminar usuarios'),
('usuarios.manage_permissions', 'usuarios', 'manage_permissions', 'Gestionar permisos de usuarios');

-- 4. Crear índices para mejor rendimiento
CREATE INDEX IF NOT EXISTS idx_permissions_module ON permissions(module);
CREATE INDEX IF NOT EXISTS idx_permissions_name ON permissions(name);
CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_permissions_permission ON user_permissions(permission_id);
