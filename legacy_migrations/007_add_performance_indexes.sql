-- Migration: Add Performance Indexes
-- Date: 2026-02-02
-- Description: Agregar índices para mejorar performance en consultas frecuentes

-- Índice para búsqueda de pagos por factura
CREATE INDEX IF NOT EXISTS idx_payments_invoice_id ON payments(invoice_id);

-- Índice para búsqueda de pagos por fecha
CREATE INDEX IF NOT EXISTS idx_payments_paid_date ON payments(paid_date);

-- Índice para búsqueda de gastos por fecha
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(date);

-- Índice para búsqueda de gastos por categoría
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);

-- Índice para búsqueda de gastos por proveedor
CREATE INDEX IF NOT EXISTS idx_expenses_supplier ON expenses(supplier_id);

-- Índice para transacciones contables por fecha
CREATE INDEX IF NOT EXISTS idx_accounting_date ON accounting_transactions(date);

-- Índice para transacciones contables por tipo
CREATE INDEX IF NOT EXISTS idx_accounting_type ON accounting_transactions(type);

-- Índice para facturas por fecha de emisión
CREATE INDEX IF NOT EXISTS idx_invoices_issued ON invoices(issued_date);

-- Índice para facturas por estado de pago
CREATE INDEX IF NOT EXISTS idx_invoices_paid ON invoices(paid);

-- Índice compuesto para consultas de facturas pendientes por unidad
CREATE INDEX IF NOT EXISTS idx_invoices_unit_paid ON invoices(unit_id, paid);

-- Índice para búsqueda de residentes por unidad
CREATE INDEX IF NOT EXISTS idx_residents_unit ON residents(unit_id);

-- Índice para productos/servicios activos
CREATE INDEX IF NOT EXISTS idx_products_active ON products_services(active);
