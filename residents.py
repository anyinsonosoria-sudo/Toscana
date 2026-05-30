import secrets
from datetime import datetime
import sqlite3
from typing import List, Dict, Optional, Sequence, Set
from db import get_conn

ACTIVE_RESIDENT_LINK_STATUSES = ('active',)
SUPPORTED_RESIDENT_LINK_STATUSES = {'invited', 'active', 'revoked'}


def _current_timestamp() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _normalize_link_status(status: Optional[str]) -> str:
    normalized = (status or 'active').strip().lower()
    if normalized not in SUPPORTED_RESIDENT_LINK_STATUSES:
        raise ValueError(f"Estado de vinculo no soportado: {status}")
    return normalized


def _normalize_invitation_code(invitation_code: Optional[str]) -> str:
    normalized = (invitation_code or '').strip().upper()
    if not normalized:
        raise ValueError("Codigo de invitacion requerido")
    return normalized


def _generate_invitation_code(cur) -> str:
    while True:
        code = secrets.token_hex(4).upper()
        cur.execute(
            "SELECT 1 FROM resident_user_units WHERE invitation_code = ? LIMIT 1",
            (code,),
        )
        if not cur.fetchone():
            return code


def _legacy_apartments_for_email(cur, email: Optional[str]) -> List[Dict]:
    normalized_email = (email or '').strip()
    if not normalized_email:
        return []

    cur.execute(
        """
        SELECT DISTINCT id, number, resident_name, resident_email, resident_phone, notes, floor
        FROM (
            SELECT id, number, resident_name, resident_email, resident_phone, notes, floor
            FROM apartments
            WHERE resident_email = ?
            UNION ALL
            SELECT a.id, a.number, r.name as resident_name, r.email as resident_email, r.phone as resident_phone, a.notes, a.floor
            FROM residents r
            JOIN apartments a ON r.unit_id = a.id
            WHERE r.email = ?
        )
        ORDER BY number
        """,
        (normalized_email, normalized_email),
    )
    return [dict(row) for row in cur.fetchall()]


def _resolve_resident_id(cur, unit_id: int, resident_email: Optional[str], resident_id: Optional[int]) -> Optional[int]:
    if resident_id:
        return resident_id

    normalized_email = (resident_email or '').strip()
    if not normalized_email:
        return None

    cur.execute(
        """
        SELECT id
        FROM residents
        WHERE unit_id = ? AND email = ?
        ORDER BY id
        LIMIT 1
        """,
        (unit_id, normalized_email),
    )
    row = cur.fetchone()
    return row['id'] if row else None


def list_linked_apartments_for_user(user_id: Optional[int], fallback_email: Optional[str] = None,
                                    include_invited: bool = False) -> List[Dict]:
    statuses: Sequence[str] = ('active', 'invited') if include_invited else ACTIVE_RESIDENT_LINK_STATUSES
    conn = get_conn()
    try:
        cur = conn.cursor()

        if user_id is not None:
            placeholders = ', '.join('?' for _ in statuses)
            cur.execute(
                f"""
                SELECT DISTINCT a.id,
                                a.number,
                                COALESCE(r.name, a.resident_name) as resident_name,
                                COALESCE(r.email, a.resident_email) as resident_email,
                                COALESCE(r.phone, a.resident_phone) as resident_phone,
                                a.notes,
                                a.floor,
                                l.is_primary,
                                l.status,
                                l.resident_id
                FROM resident_user_units l
                JOIN apartments a ON a.id = l.unit_id
                LEFT JOIN residents r ON r.id = l.resident_id
                WHERE l.user_id = ? AND l.status IN ({placeholders})
                ORDER BY l.is_primary DESC, a.number
                """,
                (user_id, *statuses),
            )
            linked_rows = [dict(row) for row in cur.fetchall()]
            if linked_rows:
                return linked_rows
    except sqlite3.OperationalError as exc:
        if 'resident_user_units' not in str(exc):
            raise
    finally:
        conn.close()

    conn = get_conn()
    try:
        cur = conn.cursor()
        return _legacy_apartments_for_email(cur, fallback_email)
    finally:
        conn.close()


def get_allowed_unit_ids_for_user(user_id: Optional[int], fallback_email: Optional[str] = None,
                                  include_invited: bool = False) -> Set[int]:
    return {
        apartment['id']
        for apartment in list_linked_apartments_for_user(
            user_id,
            fallback_email=fallback_email,
            include_invited=include_invited,
        )
        if apartment.get('id') is not None
    }


def clear_user_apartment_links(user_id: int, clear_emails: Optional[Sequence[str]] = None) -> None:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM resident_user_units WHERE user_id = ?", (user_id,))

        normalized_emails = {
            (email or '').strip()
            for email in (clear_emails or [])
            if (email or '').strip()
        }
        for email in normalized_emails:
            cur.execute(
                "UPDATE apartments SET resident_email = NULL WHERE resident_email = ?",
                (email,),
            )

        conn.commit()
    finally:
        conn.close()


def link_user_to_apartment(user_id: int, unit_id: int, resident_email: Optional[str] = None,
                           resident_name: Optional[str] = None, resident_id: Optional[int] = None,
                           is_primary: bool = True, status: str = 'active',
                           invitation_code: Optional[str] = None,
                           created_by: Optional[int] = None) -> None:
    normalized_status = _normalize_link_status(status)
    now = _current_timestamp()
    conn = get_conn()
    try:
        cur = conn.cursor()
        resolved_resident_id = _resolve_resident_id(cur, unit_id, resident_email, resident_id)

        if is_primary:
            cur.execute(
                "UPDATE resident_user_units SET is_primary = 0, updated_at = ? WHERE user_id = ?",
                (now, user_id),
            )

        cur.execute(
            """
            INSERT INTO resident_user_units (
                user_id,
                unit_id,
                resident_id,
                is_primary,
                status,
                invitation_code,
                invited_at,
                activated_at,
                created_by,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, unit_id) DO UPDATE SET
                resident_id = excluded.resident_id,
                is_primary = excluded.is_primary,
                status = excluded.status,
                invitation_code = COALESCE(excluded.invitation_code, resident_user_units.invitation_code),
                invited_at = COALESCE(resident_user_units.invited_at, excluded.invited_at),
                activated_at = COALESCE(excluded.activated_at, resident_user_units.activated_at),
                created_by = COALESCE(excluded.created_by, resident_user_units.created_by),
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                unit_id,
                resolved_resident_id,
                1 if is_primary else 0,
                normalized_status,
                invitation_code,
                now,
                now if normalized_status == 'active' else None,
                created_by,
                now,
                now,
            ),
        )

        apartment_updates = []
        apartment_values = []
        if resident_email is not None:
            apartment_updates.append('resident_email = ?')
            apartment_values.append((resident_email or '').strip() or None)
        if resident_name is not None:
            apartment_updates.append('resident_name = ?')
            apartment_values.append((resident_name or '').strip() or None)

        if apartment_updates:
            apartment_values.append(unit_id)
            cur.execute(
                f"UPDATE apartments SET {', '.join(apartment_updates)} WHERE id = ?",
                apartment_values,
            )

        conn.commit()
    finally:
        conn.close()


def list_pending_invitations_for_user(user_id: int) -> List[Dict]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT l.id,
                   l.user_id,
                   l.unit_id,
                   l.resident_id,
                   l.is_primary,
                   l.status,
                   l.invitation_code,
                   l.invited_at,
                   l.activated_at,
                   l.created_by,
                   a.number as apartment_number,
                   a.floor,
                   COALESCE(r.name, a.resident_name) as resident_name,
                   COALESCE(r.email, a.resident_email) as resident_email,
                   COALESCE(r.phone, a.resident_phone) as resident_phone
            FROM resident_user_units l
            JOIN apartments a ON a.id = l.unit_id
            LEFT JOIN residents r ON r.id = l.resident_id
            WHERE l.user_id = ? AND l.status = 'invited'
            ORDER BY l.is_primary DESC, a.number
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def issue_resident_invitation(user_id: int, unit_id: int, resident_email: Optional[str] = None,
                              resident_name: Optional[str] = None, resident_id: Optional[int] = None,
                              is_primary: bool = True, created_by: Optional[int] = None) -> Dict:
    conn = get_conn()
    try:
        cur = conn.cursor()
        invitation_code = _generate_invitation_code(cur)
    finally:
        conn.close()

    link_user_to_apartment(
        user_id,
        unit_id,
        resident_email=resident_email,
        resident_name=resident_name,
        resident_id=resident_id,
        is_primary=is_primary,
        status='invited',
        invitation_code=invitation_code,
        created_by=created_by,
    )

    invitations = list_pending_invitations_for_user(user_id)
    for invitation in invitations:
        if invitation.get('unit_id') == unit_id and invitation.get('invitation_code') == invitation_code:
            return invitation

    raise RuntimeError("No se pudo recuperar la invitacion creada")


def activate_resident_invitation(user_id: int, invitation_code: str,
                                 resident_email: Optional[str] = None,
                                 resident_name: Optional[str] = None) -> Dict:
    normalized_code = _normalize_invitation_code(invitation_code)
    now = _current_timestamp()

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT l.id,
                   l.unit_id,
                   l.resident_id,
                   a.number as apartment_number
            FROM resident_user_units l
            JOIN apartments a ON a.id = l.unit_id
            WHERE l.user_id = ? AND l.invitation_code = ? AND l.status = 'invited'
            LIMIT 1
            """,
            (user_id, normalized_code),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("Codigo de invitacion invalido o expirado")

        cur.execute(
            """
            UPDATE resident_user_units
            SET status = 'active',
                invitation_code = NULL,
                activated_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now, now, row['id']),
        )

        apartment_updates = []
        apartment_values = []
        if resident_email is not None:
            apartment_updates.append('resident_email = ?')
            apartment_values.append((resident_email or '').strip() or None)
        if resident_name is not None:
            apartment_updates.append('resident_name = ?')
            apartment_values.append((resident_name or '').strip() or None)

        if apartment_updates:
            apartment_values.append(row['unit_id'])
            cur.execute(
                f"UPDATE apartments SET {', '.join(apartment_updates)} WHERE id = ?",
                apartment_values,
            )

        conn.commit()
    finally:
        conn.close()

    linked_apartments = list_linked_apartments_for_user(user_id, include_invited=True)
    for apartment in linked_apartments:
        if apartment.get('id') == row['unit_id']:
            apartment['apartment_number'] = apartment.get('number')
            return apartment

    raise RuntimeError("No se pudo recuperar el apartamento activado")


def list_resident_invoices_for_user(user_id: Optional[int], fallback_email: Optional[str] = None,
                                    paid: Optional[bool] = None, limit: Optional[int] = None) -> List[Dict]:
    allowed_unit_ids = sorted(get_allowed_unit_ids_for_user(user_id, fallback_email=fallback_email))
    if not allowed_unit_ids:
        return []

    conn = get_conn()
    try:
        cur = conn.cursor()
        placeholders = ','.join('?' for _ in allowed_unit_ids)
        query = f"""
            SELECT i.id,
                   i.unit_id,
                   i.description,
                   i.amount,
                   i.issued_date,
                   i.due_date,
                   i.paid,
                   a.number as apartment_number,
                   COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as total_paid
            FROM invoices i
            JOIN apartments a ON a.id = i.unit_id
            WHERE i.unit_id IN ({placeholders})
        """
        params = list(allowed_unit_ids)

        if paid is not None:
            query += " AND i.paid = ?"
            params.append(1 if paid else 0)

        query += " ORDER BY i.issued_date DESC, i.id DESC"
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)

        cur.execute(query, params)
        rows = [dict(row) for row in cur.fetchall()]
        for row in rows:
            row['remaining'] = max(float(row.get('amount') or 0) - float(row.get('total_paid') or 0), 0)
        return rows
    finally:
        conn.close()


def get_resident_statement_summary_for_user(user_id: Optional[int], fallback_email: Optional[str] = None) -> Dict:
    apartments = list_linked_apartments_for_user(user_id, fallback_email=fallback_email)
    invoices = list_resident_invoices_for_user(user_id, fallback_email=fallback_email)

    summary_by_unit = {
        apartment['id']: {
            'unit_id': apartment['id'],
            'apartment_number': apartment.get('number'),
            'resident_name': apartment.get('resident_name'),
            'resident_email': apartment.get('resident_email'),
            'balance': 0.0,
            'pending_invoices': 0,
            'invoice_count': 0,
            'total_invoiced': 0.0,
            'total_paid': 0.0,
        }
        for apartment in apartments
        if apartment.get('id') is not None
    }

    for invoice in invoices:
        unit_summary = summary_by_unit.setdefault(
            invoice['unit_id'],
            {
                'unit_id': invoice['unit_id'],
                'apartment_number': invoice.get('apartment_number'),
                'resident_name': None,
                'resident_email': None,
                'balance': 0.0,
                'pending_invoices': 0,
                'invoice_count': 0,
                'total_invoiced': 0.0,
                'total_paid': 0.0,
            },
        )
        unit_summary['invoice_count'] += 1
        unit_summary['total_invoiced'] += float(invoice.get('amount') or 0)
        unit_summary['total_paid'] += float(invoice.get('total_paid') or 0)
        unit_summary['balance'] += float(invoice.get('remaining') or 0)
        if not invoice.get('paid'):
            unit_summary['pending_invoices'] += 1

    apartment_summaries = sorted(summary_by_unit.values(), key=lambda item: (item.get('apartment_number') or ''))
    return {
        'apartments': apartment_summaries,
        'totals': {
            'apartments': len(apartment_summaries),
            'pending_invoices': sum(item['pending_invoices'] for item in apartment_summaries),
            'invoice_count': sum(item['invoice_count'] for item in apartment_summaries),
            'balance': sum(item['balance'] for item in apartment_summaries),
            'total_invoiced': sum(item['total_invoiced'] for item in apartment_summaries),
            'total_paid': sum(item['total_paid'] for item in apartment_summaries),
        },
    }

def check_apartment_owner(unit_id: Optional[int], exclude_resident_id: Optional[int] = None) -> Optional[Dict]:
    """
    Verifica si un apartamento ya tiene un propietario asignado.
    Retorna el residente propietario si existe, None si no.
    exclude_resident_id: ID de residente a excluir de la búsqueda (para ediciones)
    """
    if not unit_id:
        return None
    
    conn = get_conn()
    cur = conn.cursor()
    
    if exclude_resident_id:
        cur.execute("""
            SELECT id, name, role FROM residents 
            WHERE unit_id=? AND role='Propietario' AND id!=?
        """, (unit_id, exclude_resident_id))
    else:
        cur.execute("""
            SELECT id, name, role FROM residents 
            WHERE unit_id=? AND role='Propietario'
        """, (unit_id,))
    
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def add_resident(unit_id: Optional[int], name: str, role: str = "tenant", email: Optional[str] = None, phone: Optional[str] = None, role_other: Optional[str] = None, payment_terms: int = 30) -> int:
    """
    role: 'Propietario', 'Inquilino', or 'Otro'
    role_other: If role is 'Otro', this specifies the custom role
    unit_id can be None if not assigned yet
    payment_terms: Days for invoice due date
    """
    # Validar si se intenta asignar un propietario a un apartamento que ya tiene uno
    if unit_id and role == 'Propietario':
        existing_owner = check_apartment_owner(unit_id)
        if existing_owner:
            raise ValueError(f"El apartamento ya tiene un propietario asignado: {existing_owner['name']}")
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO residents(unit_id, name, role, role_other, email, phone, payment_terms) VALUES(?,?,?,?,?,?,?)",
                (unit_id, name, role, role_other, email, phone, payment_terms))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid

def list_residents(unit_id: Optional[int] = None) -> List[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    if unit_id is not None:
        cur.execute("""
            SELECT r.id, r.unit_id, r.name, r.role, r.role_other, r.email, r.phone, r.payment_terms, r.created_at,
                   a.number as apartment_number
            FROM residents r
            LEFT JOIN apartments a ON r.unit_id = a.id
            WHERE r.unit_id=? 
            ORDER BY r.name
        """, (unit_id,))
    else:
        cur.execute("""
            SELECT r.id, r.unit_id, r.name, r.role, r.role_other, r.email, r.phone, r.payment_terms, r.created_at,
                   a.number as apartment_number
            FROM residents r
            LEFT JOIN apartments a ON r.unit_id = a.id
            ORDER BY r.name
        """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_resident(resident_id: int) -> Optional[Dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM residents WHERE id=?", (resident_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def update_resident(resident_id: int, **fields) -> None:
    if not fields:
        return
    
    # Validar si se intenta cambiar el rol a Propietario o cambiar de apartamento siendo Propietario
    if 'unit_id' in fields or 'role' in fields:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT unit_id, role FROM residents WHERE id=?", (resident_id,))
        current = cur.fetchone()
        conn.close()
        
        if current:
            current_unit_id = current['unit_id']
            current_role = current['role']
            new_unit_id = fields.get('unit_id', current_unit_id)
            new_role = fields.get('role', current_role)
            
            # Si el nuevo rol es Propietario y el apartamento cambió o se está cambiando a Propietario
            if new_unit_id and new_role == 'Propietario':
                # Verificar si ya hay un propietario en ese apartamento (excluyendo el residente actual)
                existing_owner = check_apartment_owner(new_unit_id, exclude_resident_id=resident_id)
                if existing_owner:
                    raise ValueError(f"El apartamento ya tiene un propietario asignado: {existing_owner['name']}")
    
    keys = []
    vals = []
    for k, v in fields.items():
        keys.append(f"{k}=?")
        vals.append(v)
    vals.append(resident_id)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"UPDATE residents SET {', '.join(keys)} WHERE id=?", vals)
    conn.commit()
    conn.close()

def delete_resident(resident_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM residents WHERE id=?", (resident_id,))
    conn.commit()
    conn.close()

def list_by_unit(unit_id: int) -> List[Dict]:
    return list_residents(unit_id)
