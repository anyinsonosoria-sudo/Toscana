"""CLI para restaurar localmente una copia SQLite descargada."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import db


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Restaura localmente una base SQLite exportada desde PythonAnywhere."
    )
    parser.add_argument(
        "snapshot_path",
        help="Ruta del archivo .sqlite/.sqlite3 descargado desde PythonAnywhere.",
    )
    parser.add_argument(
        "--target",
        help="Ruta de la base local a reemplazar. Default: BUILDING_MAINTENANCE_DB o data/data.db.",
    )
    parser.add_argument(
        "--backup-dir",
        help="Directorio donde guardar el respaldo previo de la BD local. Default: backups/db.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo valida el archivo de backup y muestra el resumen; no reemplaza la BD local.",
    )
    parser.add_argument(
        "--skip-local-backup",
        action="store_true",
        help="No crea una copia del data/data.db actual antes de restaurar.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    source_path = db._resolve_repo_path(args.snapshot_path, db.DB_PATH)
    target_path = db._resolve_repo_path(args.target, db.DB_PATH)

    try:
        snapshot_info = db.validate_snapshot(source_path)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"[INFO] Backup origen: {source_path}")
    print(f"[INFO] Base local destino: {target_path}")
    print(f"[INFO] Tablas detectadas: {len(snapshot_info['tables'])}")
    print(
        "[INFO] Registros clave: " + ", ".join(
            f"{table}={snapshot_info['counts'].get(table, 0)}" for table in db.REQUIRED_SNAPSHOT_TABLES
        )
    )

    if args.dry_run:
        print("[OK] Validacion completada. No se realizaron cambios.")
        return 0

    try:
        result = db.restore_snapshot(
            snapshot_path=source_path,
            target_path=target_path,
            backup_dir=args.backup_dir,
            create_backup=not args.skip_local_backup,
        )
    except PermissionError:
        print("[ERROR] No se pudo reemplazar la base local. Cierra la app o cualquier proceso que la tenga abierta e intenta de nuevo.")
        return 1
    except Exception as exc:
        print(f"[ERROR] Fallo al restaurar el backup: {exc}")
        return 1

    if result['backup_path']:
        print(f"[OK] Respaldo local previo guardado en: {result['backup_path']}")
    print(f"[OK] Base local restaurada correctamente en: {result['target_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())