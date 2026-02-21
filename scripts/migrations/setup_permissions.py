"""
Setup Permissions - Crea tablas de permisos y asigna permisos por defecto
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data.db"

def setup_permissions():
    """Crea tablas de permisos y datos iniciales"""
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║  CONFIGURACIÓN DE SISTEMA DE PERMISOS                    ║
    ║  Building Maintenance System v2.0                        ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    print(f"\n📁 Base de datos: {DB_PATH}\n")
    
    if not DB_PATH.exists():
        print("❌ Error: La base de datos no existe. Ejecuta setup_database.py primero.")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        print("📦 Creando tablas de permisos...\n")
        
        # Crear tablas
        conn.executescript("""
            -- Tabla de permisos disponibles
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                module TEXT NOT NULL,
                action TEXT NOT NULL,
                description TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Tabla de relación usuario-permiso
            CREATE TABLE IF NOT EXISTS user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission_id INTEGER NOT NULL,
                granted_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                granted_by INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
                FOREIGN KEY (granted_by) REFERENCES users(id) ON DELETE SET NULL,
                UNIQUE(user_id, permission_id)
            );
            
            -- Tabla de roles y sus permisos
            CREATE TABLE IF NOT EXISTS role_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL CHECK(role IN ('admin', 'operator', 'resident')),
                permission_id INTEGER NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE,
                UNIQUE(role, permission_id)
            );
            
            -- Índices para optimización
            CREATE INDEX IF NOT EXISTS idx_permissions_module ON permissions(module);
            CREATE INDEX IF NOT EXISTS idx_permissions_name ON permissions(name);
            CREATE INDEX IF NOT EXISTS idx_user_permissions_user ON user_permissions(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_permissions_permission ON user_permissions(permission_id);
            CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role);
        """)
        
        print("  ✅ Tablas creadas exitosamente\n")
        
        print("📝 Insertando permisos del sistema...\n")
        
        # Definir permisos por módulo (41 permisos)
        permissions = [
            # Apartamentos (4)
            ("apartamentos.view", "apartamentos", "view", "Ver listado de apartamentos"),
            ("apartamentos.create", "apartamentos", "create", "Crear nuevos apartamentos"),
            ("apartamentos.edit", "apartamentos", "edit", "Editar apartamentos existentes"),
            ("apartamentos.delete", "apartamentos", "delete", "Eliminar apartamentos"),
            
            # Suplidores (4)
            ("suplidores.view", "suplidores", "view", "Ver listado de suplidores"),
            ("suplidores.create", "suplidores", "create", "Crear nuevos suplidores"),
            ("suplidores.edit", "suplidores", "edit", "Editar suplidores existentes"),
            ("suplidores.delete", "suplidores", "delete", "Eliminar suplidores"),
            
            # Productos y Servicios (4)
            ("productos.view", "productos", "view", "Ver listado de productos/servicios"),
            ("productos.create", "productos", "create", "Crear nuevos productos/servicios"),
            ("productos.edit", "productos", "edit", "Editar productos/servicios"),
            ("productos.delete", "productos", "delete", "Eliminar productos/servicios"),
            
            # Gastos (5)
            ("gastos.view", "gastos", "view", "Ver listado de gastos"),
            ("gastos.create", "gastos", "create", "Registrar nuevos gastos"),
            ("gastos.edit", "gastos", "edit", "Editar gastos existentes"),
            ("gastos.delete", "gastos", "delete", "Eliminar gastos"),
            ("gastos.ocr", "gastos", "ocr", "Usar OCR para extraer datos de recibos"),
            
            # Facturación (7)
            ("facturacion.view", "facturacion", "view", "Ver facturas y ventas"),
            ("facturacion.create", "facturacion", "create", "Crear nuevas facturas"),
            ("facturacion.edit", "facturacion", "edit", "Editar facturas existentes"),
            ("facturacion.delete", "facturacion", "delete", "Eliminar facturas"),
            ("facturacion.payments", "facturacion", "payments", "Registrar pagos"),
            ("facturacion.recurring", "facturacion", "recurring", "Gestionar ventas recurrentes"),
            ("facturacion.pdf", "facturacion", "pdf", "Generar PDFs de facturas"),
            
            # Reportes (3)
            ("reportes.view", "reportes", "view", "Ver reportes financieros"),
            ("reportes.export", "reportes", "export", "Exportar reportes"),
            ("reportes.advanced", "reportes", "advanced", "Acceder a reportes avanzados"),
            
            # Contabilidad (4)
            ("contabilidad.view", "contabilidad", "view", "Ver registros contables"),
            ("contabilidad.create", "contabilidad", "create", "Crear asientos contables"),
            ("contabilidad.edit", "contabilidad", "edit", "Editar asientos contables"),
            ("contabilidad.close_period", "contabilidad", "close_period", "Cerrar períodos contables"),
            
            # Residentes (4)
            ("residentes.view", "residentes", "view", "Ver listado de residentes"),
            ("residentes.create", "residentes", "create", "Registrar nuevos residentes"),
            ("residentes.edit", "residentes", "edit", "Editar información de residentes"),
            ("residentes.delete", "residentes", "delete", "Eliminar residentes"),
            
            # Configuración (4)
            ("configuracion.view", "configuracion", "view", "Ver configuración del sistema"),
            ("configuracion.edit", "configuracion", "edit", "Modificar configuración"),
            ("configuracion.users", "configuracion", "users", "Gestionar usuarios del sistema"),
            ("configuracion.permissions", "configuracion", "permissions", "Gestionar permisos"),
            
            # Empresa (2)
            ("empresa.view", "empresa", "view", "Ver información de la empresa"),
            ("empresa.edit", "empresa", "edit", "Editar información de la empresa"),
        ]
        
        # Insertar permisos
        for name, module, action, description in permissions:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO permissions (name, module, action, description)
                    VALUES (?, ?, ?, ?)
                """, (name, module, action, description))
            except Exception as e:
                print(f"  ⚠️  Error insertando {name}: {e}")
        
        conn.commit()
        print(f"  ✅ {len(permissions)} permisos insertados\n")
        
        print("🔑 Asignando permisos por defecto al rol 'admin'...\n")
        
        # Obtener todos los permisos
        cur = conn.cursor()
        cur.execute("SELECT id FROM permissions")
        permission_ids = [row[0] for row in cur.fetchall()]
        
        # Asignar todos los permisos al rol admin
        for perm_id in permission_ids:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO role_permissions (role, permission_id)
                    VALUES ('admin', ?)
                """, (perm_id,))
            except Exception as e:
                print(f"  ⚠️  Error asignando permiso {perm_id}: {e}")
        
        conn.commit()
        print(f"  ✅ {len(permission_ids)} permisos asignados al rol 'admin'\n")
        
        print("👤 Asignando permisos al usuario admin...\n")
        
        # Obtener ID del usuario admin
        cur.execute("SELECT id FROM users WHERE username = 'admin'")
        admin_row = cur.fetchone()
        
        if admin_row:
            admin_id = admin_row[0]
            
            # Asignar todos los permisos al usuario admin
            for perm_id in permission_ids:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO user_permissions (user_id, permission_id, granted_by)
                        VALUES (?, ?, ?)
                    """, (admin_id, perm_id, admin_id))
                except Exception as e:
                    print(f"  ⚠️  Error asignando permiso {perm_id}: {e}")
            
            conn.commit()
            print(f"  ✅ {len(permission_ids)} permisos asignados al usuario 'admin'\n")
        else:
            print("  ⚠️  Usuario 'admin' no encontrado. Ejecuta setup_database.py primero.\n")
        
        # Mostrar resumen
        cur.execute("SELECT COUNT(*) FROM permissions")
        total_permissions = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM user_permissions WHERE user_id = ?", (admin_id,) if admin_row else (0,))
        admin_permissions = cur.fetchone()[0]
        
        print(f"""
    ╔══════════════════════════════════════════════════════════╗
    ║  ✅ CONFIGURACIÓN COMPLETADA                             ║
    ╠══════════════════════════════════════════════════════════╣
    ║  • Permisos del sistema: {total_permissions:>3}                            ║
    ║  • Permisos usuario admin: {admin_permissions:>3}                          ║
    ║  • Tablas creadas: permissions, user_permissions,        ║
    ║    role_permissions                                      ║
    ╚══════════════════════════════════════════════════════════╝
        """)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error durante la configuración: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
        
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    success = setup_permissions()
    sys.exit(0 if success else 1)
