-- Migración 004: Corregir inconsistencias en Foreign Keys
-- Fecha: 2026-01-23
-- Descripción: Unificar referencias a apartments(id) y resolver inconsistencias

-- NOTA IMPORTANTE:
-- SQLite no permite modificar foreign keys directamente con ALTER TABLE
-- Esta migración documenta el problema y proporciona scripts de verificación
-- Para aplicar los cambios se requiere recrear las tablas

-- PROBLEMA 1: charges.unit_id -> apartments(id) (CORRECTO)
-- PROBLEMA 2: invoices.unit_id -> apartments(id) (CORRECTO)
-- PROBLEMA 3: recurring_sales.resident_id -> apartments(id) (NOMBRE INCONSISTENTE)
-- SOLUCIÓN: Cambiar recurring_sales.resident_id a unit_id para consistencia

-- ============================================================
-- VERIFICACIÓN DE INTEGRIDAD REFERENCIAL
-- ============================================================

-- Verificar facturas huérfanas (sin apartamento)
SELECT 
    'INVOICES SIN APARTAMENTO' as problema,
    COUNT(*) as cantidad
FROM invoices 
WHERE unit_id NOT IN (SELECT id FROM apartments);

-- Verificar cargos huérfanos
SELECT 
    'CHARGES SIN APARTAMENTO' as problema,
    COUNT(*) as cantidad
FROM charges 
WHERE unit_id NOT IN (SELECT id FROM apartments);

-- Verificar ventas recurrentes huérfanas
SELECT 
    'RECURRING_SALES SIN APARTAMENTO' as problema,
    COUNT(*) as cantidad
FROM recurring_sales 
WHERE resident_id NOT IN (SELECT id FROM apartments);

-- ============================================================
-- LIMPIEZA DE DATOS HUÉRFANOS (EJECUTAR SI HAY PROBLEMAS)
-- ============================================================

-- ADVERTENCIA: Esto eliminará datos. Hacer backup antes.
-- Descomentar solo si es necesario:

-- DELETE FROM invoices WHERE unit_id NOT IN (SELECT id FROM apartments);
-- DELETE FROM charges WHERE unit_id NOT IN (SELECT id FROM apartments);
-- DELETE FROM recurring_sales WHERE resident_id NOT IN (SELECT id FROM apartments);

-- ============================================================
-- RECREACIÓN DE TABLA recurring_sales CON COLUMNA CORRECTA
-- ============================================================

-- Paso 1: Crear tabla temporal con el esquema correcto
CREATE TABLE IF NOT EXISTS recurring_sales_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,  -- CAMBIADO de resident_id a unit_id
    service_id INTEGER,
    amount REAL NOT NULL,
    frequency TEXT NOT NULL,
    billing_day INTEGER DEFAULT 1,
    start_date TEXT NOT NULL,
    description TEXT,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES apartments(id) ON DELETE CASCADE
);

-- Paso 2: Copiar datos existentes (mapear resident_id -> unit_id)
INSERT INTO recurring_sales_new (id, unit_id, service_id, amount, frequency, billing_day, start_date, description, active, created_at)
SELECT id, resident_id, service_id, amount, frequency, billing_day, start_date, description, active, created_at
FROM recurring_sales;

-- Paso 3: Eliminar tabla antigua
DROP TABLE recurring_sales;

-- Paso 4: Renombrar tabla nueva
ALTER TABLE recurring_sales_new RENAME TO recurring_sales;

-- ============================================================
-- AGREGAR CASCADE A OTRAS TABLAS (OPCIONAL PERO RECOMENDADO)
-- ============================================================

-- Para aplicar ON DELETE CASCADE a invoices y charges:
-- 1. Crear tabla temporal con CASCADE
-- 2. Copiar datos
-- 3. Eliminar tabla antigua
-- 4. Renombrar

-- EJEMPLO PARA INVOICES:
CREATE TABLE IF NOT EXISTS invoices_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER,
    description TEXT,
    amount REAL,
    issued_date TEXT DEFAULT CURRENT_TIMESTAMP,
    due_date TEXT,
    paid INTEGER DEFAULT 0,
    recurring_sale_id INTEGER,
    FOREIGN KEY(unit_id) REFERENCES apartments(id) ON DELETE CASCADE,
    FOREIGN KEY(recurring_sale_id) REFERENCES recurring_sales(id) ON DELETE SET NULL
);

INSERT INTO invoices_new SELECT * FROM invoices;
DROP TABLE invoices;
ALTER TABLE invoices_new RENAME TO invoices;

-- EJEMPLO PARA CHARGES:
CREATE TABLE IF NOT EXISTS charges_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER,
    description TEXT,
    amount REAL,
    due_date TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(unit_id) REFERENCES apartments(id) ON DELETE CASCADE
);

INSERT INTO charges_new SELECT * FROM charges;
DROP TABLE charges;
ALTER TABLE charges_new RENAME TO charges;

-- ============================================================
-- VERIFICACIÓN FINAL
-- ============================================================

-- Verificar que las foreign keys están activas
PRAGMA foreign_keys;

-- Verificar integridad referencial
PRAGMA foreign_key_check;

-- Ver esquema de tablas actualizadas
SELECT sql FROM sqlite_master WHERE type='table' AND name IN ('invoices', 'charges', 'recurring_sales');
