"""
Company/Administrator Information Management
Handles CRUD operations for company/admin data
"""
import db
from typing import Optional, Dict

def get_company_info() -> Optional[Dict]:
    """
    Get the company information from the database.
    Returns None if no company info exists.
    """
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, legal_id, address, city, country, phone, email, website,
               bank_name, bank_account, bank_routing, tax_id, logo_path, notes, updated_at
        FROM company_info
        ORDER BY updated_at DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "legal_id": row[2],
            "address": row[3],
            "city": row[4],
            "country": row[5],
            "phone": row[6],
            "email": row[7],
            "website": row[8],
            "bank_name": row[9],
            "bank_account": row[10],
            "bank_routing": row[11],
            "tax_id": row[12],
            "logo_path": row[13],
            "notes": row[14],
            "updated_at": row[15]
        }
    return None

def update_company_info(
    name: str,
    legal_id: Optional[str] = None,
    address: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    website: Optional[str] = None,
    bank_name: Optional[str] = None,
    bank_account: Optional[str] = None,
    bank_routing: Optional[str] = None,
    tax_id: Optional[str] = None,
    logo_path: Optional[str] = None,
    notes: Optional[str] = None
) -> int:
    """
    Insert or update company information.
    Only one company record should exist at a time.
    Returns the record ID.
    """
    conn = db.get_conn()
    cursor = conn.cursor()
    
    # Check if a record exists
    cursor.execute("SELECT id FROM company_info LIMIT 1")
    existing = cursor.fetchone()
    
    if existing:
        # Update existing record
        cursor.execute("""
            UPDATE company_info
            SET name=?, legal_id=?, address=?, city=?, country=?, phone=?, email=?, 
                website=?, bank_name=?, bank_account=?, bank_routing=?, tax_id=?, 
                logo_path=?, notes=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (name, legal_id, address, city, country, phone, email, website,
              bank_name, bank_account, bank_routing, tax_id, logo_path, notes, existing[0]))
        record_id = existing[0]
    else:
        # Insert new record
        cursor.execute("""
            INSERT INTO company_info (name, legal_id, address, city, country, phone, email,
                                     website, bank_name, bank_account, bank_routing, tax_id,
                                     logo_path, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, legal_id, address, city, country, phone, email, website,
              bank_name, bank_account, bank_routing, tax_id, logo_path, notes))
        record_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return record_id

def has_company_info() -> bool:
    """Check if company information exists in the database."""
    conn = db.get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM company_info")
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0
