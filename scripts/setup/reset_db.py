import sys
from pathlib import Path

# Ensure building_maintenance is on sys.path
BASE_DIR = Path(__file__).resolve().parents[3]  # points to Xpack folder
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / 'Xpack' / 'building_maintenance')) if (BASE_DIR / 'Xpack' / 'building_maintenance').exists() else None

try:
    from building_maintenance import db  # if package-style import works
except Exception:
    import importlib.util
    db_path = BASE_DIR / 'Xpack' / 'building_maintenance' / 'db.py'
    if not db_path.exists():
        # fallback to sibling path without nested Xpack
        db_path = BASE_DIR / 'building_maintenance' / 'db.py'
    spec = importlib.util.spec_from_file_location('db', db_path)
    db = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(db)

if __name__ == '__main__':
    print("Resetting database...")
    db.reset_db()
    print("Done. You can restart the server.")
