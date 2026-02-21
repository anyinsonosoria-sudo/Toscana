"""
Script temporal para testing - inicia servidor sin debug mode
"""
import os
os.environ['BM_DEBUG'] = 'False'

from app import app, db

if __name__ == "__main__":
    db.init_db()
    print("\n*** Building Maintenance - Testing Mode ***")
    print("Servidor corriendo en http://127.0.0.1:5000")
    print("Debug mode: OFF\n")
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
