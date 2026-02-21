#!/usr/bin/env python3
"""
Database migration script to add missing columns to tables
"""

import sqlite3
import os
from pathlib import Path

def migrate_products_services_table():
    """Add additional_notes column to products_services table if it doesn't exist"""
    # Try different possible database names
    db_names = ["data.db", "building_maintenance.db", "building_management.db"]
    db_path = None
    
    for db_name in db_names:
        candidate = Path(__file__).parent / db_name
        if candidate.exists() and candidate.stat().st_size > 0:
            db_path = candidate
            break
    
    if not db_path:
        print("❌ Database file not found. Run the application first to initialize it.")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        # Check if additional_notes column exists in products_services
        cur.execute("PRAGMA table_info(products_services)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'additional_notes' not in columns:
            print("📋 Adding 'additional_notes' column to products_services table...")
            cur.execute("ALTER TABLE products_services ADD COLUMN additional_notes TEXT")
            conn.commit()
            print("✅ Column 'additional_notes' added successfully!")
        else:
            print("✅ Column 'additional_notes' already exists.")
        
        # Check if payment_terms column exists in residents
        cur.execute("PRAGMA table_info(residents)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'payment_terms' not in columns:
            print("📋 Adding 'payment_terms' column to residents table...")
            cur.execute("ALTER TABLE residents ADD COLUMN payment_terms INTEGER DEFAULT 30")
            conn.commit()
            print("✅ Column 'payment_terms' added successfully!")
        else:
            print("✅ Column 'payment_terms' already exists.")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🔄 Starting database migration...")
    if migrate_products_services_table():
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed. Please check the error above.")
