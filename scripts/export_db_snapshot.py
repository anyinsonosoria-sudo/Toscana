"""CLI para exportar una copia consistente de la base SQLite activa."""

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
        description="Exporta una copia consistente de la base SQLite actual."
    )
    parser.add_argument(
        "--source",
        help="Ruta de la base SQLite origen. Si se omite, usa BUILDING_MAINTENANCE_DB o data/data.db.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directorio donde se guardara el backup. Default: backups/db.",
    )
    parser.add_argument(
        "--filename",
        help="Nombre del archivo de salida. Si se omite, se genera uno con timestamp.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        destination_path = db.create_snapshot(
            source_path=args.source,
            output_dir=args.output_dir,
            filename=args.filename,
        )
        snapshot_info = db.validate_snapshot(destination_path)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 1

    print(f"[INFO] Base origen: {db._resolve_repo_path(args.source, db.DB_PATH)}")
    print(f"[INFO] Backup destino: {destination_path}")
    print(f"[OK] Backup creado correctamente: {destination_path}")
    print(f"[OK] Tablas detectadas: {len(snapshot_info['tables'])}")
    if snapshot_info['tables']:
        print("[OK] Primeras tablas: " + ", ".join(snapshot_info['tables'][:10]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())