"""
Apartments Module
=================
Gestión de apartamentos y residentes.
Usa context managers para conexiones seguras a BD.
"""
from typing import List, Dict, Optional
import logging
from extensions import db
from data_models.models import Apartment, Resident
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)


def _apartment_to_dict(apt: Apartment) -> Dict:
    """Helper to convert Apartment model to dict format expected by templates"""
    result = {
        'id': apt.id,
        'number': apt.number,
        'floor': apt.floor,
        'notes': apt.notes,
        'created_at': apt.created_at.isoformat() if apt.created_at else None,
        'resident_name': apt.resident_name,
        'resident_role': apt.resident_role,
        'resident_email': apt.resident_email,
        'resident_phone': apt.resident_phone,
        'payment_terms': apt.payment_terms
    }
    
    # Agregar residentes adicionales si están cargados
    if hasattr(apt, 'extra_residents'):
        result['extra_residents'] = [{
            'id': r.id,
            'name': r.name,
            'role': r.role,
            'email': r.email,
            'phone': r.phone
        } for r in apt.extra_residents]
        
    return result


def add_apartment(number: str, floor: Optional[str] = None, notes: Optional[str] = None, 
                 resident_name: Optional[str] = None, resident_role: str = 'tenant',
                 resident_email: Optional[str] = None, resident_phone: Optional[str] = None,
                 payment_terms: int = 30) -> int:
    """Crea un nuevo apartamento con información del residente"""
    
    # Verificar si existe
    existing = Apartment.query.filter_by(number=number).first()
    if existing:
        raise ValueError(f"Ya existe un apartamento con el número '{number}'")
        
    apt = Apartment(
        number=number,
        floor=floor,
        notes=notes,
        resident_name=resident_name,
        resident_role=resident_role,
        resident_email=resident_email,
        resident_phone=resident_phone,
        payment_terms=payment_terms
    )
    
    try:
        db.session.add(apt)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError(f"Ya existe un apartamento con el número '{number}'")
        
    # Dual-write: sincronizar con BD legacy
    try:
        import db as legacy_db
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute("""INSERT OR IGNORE INTO apartments
                       (id, number, floor, notes, resident_name, resident_role, 
                        resident_email, resident_phone, payment_terms) 
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (apt.id, number, floor, notes, resident_name, resident_role, resident_email, 
                     resident_phone, payment_terms))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to dual-write apartment to legacy DB: {e}")

    return apt.id


def list_apartments() -> List[Dict]:
    """Lista todos los apartamentos con información del residente"""
    apartments = Apartment.query.order_by(Apartment.number).all()
    return [_apartment_to_dict(apt) for apt in apartments]


def save_extra_residents(apartment_id: int, residents_list: list) -> None:
    """Guarda residentes adicionales de un apartamento (reemplaza los anteriores)"""
    apt = db.session.get(Apartment, apartment_id)
    if not apt:
        return
        
    # Eliminar residentes existentes
    Resident.query.filter_by(unit_id=apartment_id).delete()
    
    # Añadir nuevos
    new_residents = []
    for r in residents_list:
        if r.get('name'):
            new_res = Resident(
                unit_id=apartment_id,
                name=r['name'],
                email=r.get('email', ''),
                phone=r.get('phone', ''),
                role=r.get('role', 'tenant')
            )
            db.session.add(new_res)
            new_residents.append(new_res)
            
    db.session.commit()
    
    # Dual-write: sincronizar con BD legacy
    try:
        import db as legacy_db
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM residents WHERE unit_id=?", (apartment_id,))
        for r in new_residents:
            cur.execute(
                "INSERT INTO residents (id, unit_id, name, email, phone, role) VALUES (?, ?, ?, ?, ?, ?)",
                (r.id, apartment_id, r.name, r.email, r.phone, r.role)
            )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to dual-write extra residents to legacy DB: {e}")


def get_apartment(apartment_id: int) -> Optional[Dict]:
    """Obtiene un apartamento por ID"""
    apt = db.session.get(Apartment, apartment_id)
    return _apartment_to_dict(apt) if apt else None


def update_apartment(apartment_id: int, **fields) -> None:
    """Actualiza campos de un apartamento"""
    if not fields:
        return
        
    apt = db.session.get(Apartment, apartment_id)
    if not apt:
        return
    
    # Whitelist de columnas permitidas
    ALLOWED_COLUMNS = {'number', 'floor', 'notes', 'resident_name', 'resident_role', 
                      'resident_email', 'resident_phone', 'payment_terms'}
    
    # Si se está actualizando el número, verificar que no esté duplicado
    if 'number' in fields and fields['number'] != apt.number:
        existing = Apartment.query.filter_by(number=fields['number']).first()
        if existing and existing.id != apartment_id:
            raise ValueError(f"Ya existe otro apartamento con el número '{fields['number']}'")
            
    for k, v in fields.items():
        if k not in ALLOWED_COLUMNS:
            raise ValueError(f"Columna '{k}' no permitida para actualización")
        setattr(apt, k, v)
        
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError(f"Error de integridad al actualizar apartamento")
        
    # Dual-write: sincronizar con BD legacy
    try:
        import db as legacy_db
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        
        keys = []
        vals = []
        for k, v in fields.items():
            keys.append(f"{k}=?")
            vals.append(v)
        
        vals.append(apartment_id)
        cur.execute(f"UPDATE apartments SET {', '.join(keys)} WHERE id=?", vals)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to dual-write apartment update to legacy DB: {e}")


def delete_apartment(apartment_id: int) -> None:
    """Elimina un apartamento verificando dependencias"""
    apt = db.session.get(Apartment, apartment_id)
    if not apt:
        return
        
    # Verificar si hay residentes asignados a este apartamento
    count = Resident.query.filter_by(unit_id=apartment_id).count()
    if count > 0:
        raise ValueError(f"No se puede eliminar el apartamento porque tiene {count} residente(s) asignado(s)")
        
    db.session.delete(apt)
    db.session.commit()
    
    # Dual-write: sincronizar con BD legacy
    try:
        import db as legacy_db
        conn = legacy_db.get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM apartments WHERE id=?", (apartment_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to dual-write apartment deletion to legacy DB: {e}")

