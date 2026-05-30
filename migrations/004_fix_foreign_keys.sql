-- Migración 004: neutralizada.
--
-- Esta migración original contenía scripts manuales de recreación y verificación
-- para un esquema legacy (`charges`, `recurring_sales.resident_id`) que ya no
-- coincide con el esquema actual creado por `db._create_schema()` y migraciones
-- posteriores. Ejecutarla en instalaciones nuevas generaba errores de arranque.
--
-- Las correcciones reales de esquema quedaron absorbidas por migraciones más
-- recientes e inicialización idempotente; por eso esta migración se conserva
-- solo para mantener continuidad histórica del orden de archivos.

SELECT '004_fix_foreign_keys.sql skipped: legacy manual migration retired' AS status;
