"""
Módulo de Reportes
Análisis y reportes de ventas, cuentas por cobrar y estadísticas financieras
"""

import os
import sqlite3
from typing import List, Dict, Optional
from db import get_conn
from datetime import datetime, timedelta, timezone
from pathlib import Path

LOG_PATH = Path(__file__).parent / "run.log"
REPORT_TIMEZONE = "America/Santo_Domingo"
MONTHLY_REPORT_TYPE = "monthly_financial_report"
MONTH_NAMES_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}

def _log(msg: str):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()} - {msg}\n")
    except Exception:
        pass


def _normalize_email(email: Optional[str]) -> str:
    return (email or "").strip().lower()


def _is_placeholder_admin_email(email: Optional[str]) -> bool:
    normalized = _normalize_email(email)
    return normalized in {'admin@toscana.local', 'admin@building.local'}


def _parse_bool_setting(raw_value, default: bool = False) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value).strip().lower() in {'1', 'true', 'yes', 'on', 'si', 'sí'}


def _get_customization_setting(key: str):
    try:
        import customization
        return customization.get_setting(key)
    except Exception:
        return None


def _resolve_monthly_report_admin_email(company_info: Optional[Dict] = None,
                                        admin_email_override: Optional[str] = None) -> str:
    company_info = company_info or {}
    candidates = [
        admin_email_override,
        _get_customization_setting('monthly_financial_report_admin_email'),
        os.environ.get('MONTHLY_FINANCIAL_REPORT_ADMIN_EMAIL'),
        company_info.get('email'),
        os.environ.get('ADMIN_EMAIL'),
        os.environ.get('SMTP_FROM'),
        os.environ.get('SMTP_USER'),
    ]

    for candidate in candidates:
        normalized = _normalize_email(candidate)
        if normalized and not _is_placeholder_admin_email(normalized):
            return normalized
    return ""


def _utcnow_sql() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _normalize_period_mode(period_mode: Optional[str]) -> str:
    mode = (period_mode or 'previous_month').strip().lower()
    if mode not in {'previous_month', 'current_month_to_date'}:
        return 'previous_month'
    return mode


def get_monthly_report_settings(app_config: Optional[Dict] = None) -> Dict[str, object]:
    app_config = app_config or {}

    enabled_default = bool(app_config.get('MONTHLY_FINANCIAL_REPORT_ENABLED', True))
    admin_only_default = bool(app_config.get('MONTHLY_FINANCIAL_REPORT_ADMIN_ONLY', False))
    admin_email_default = (app_config.get('MONTHLY_FINANCIAL_REPORT_ADMIN_EMAIL') or '').strip()
    hour = int(app_config.get('MONTHLY_FINANCIAL_REPORT_HOUR', 6) or 6)
    minute = int(app_config.get('MONTHLY_FINANCIAL_REPORT_MINUTE', 0) or 0)

    enabled = _parse_bool_setting(
        _get_customization_setting('monthly_financial_report_enabled'),
        enabled_default,
    )
    admin_only = _parse_bool_setting(
        _get_customization_setting('monthly_financial_report_admin_only'),
        admin_only_default,
    )

    admin_email_value = _get_customization_setting('monthly_financial_report_admin_email')
    if admin_email_value is None:
        admin_email = _normalize_email(admin_email_default)
    else:
        admin_email = _normalize_email(admin_email_value)

    return {
        'enabled': enabled,
        'admin_only': admin_only,
        'admin_email': admin_email,
        'schedule_day': 1,
        'schedule_hour': hour,
        'schedule_minute': minute,
        'schedule_time': f'{hour:02d}:{minute:02d}',
        'schedule_label': f'Cada día 1 a las {hour:02d}:{minute:02d}',
        'period_basis': 'Mes anterior completo',
    }


def build_monthly_report_dispatch_summary(result: Dict) -> Dict[str, object]:
    sent_count = len(result.get('sent', []))
    skipped_count = len(result.get('skipped', []))
    failed_count = len(result.get('failed', []))
    report_period = result.get('report_period', 'N/A')
    status = str(result.get('status') or 'processed')

    if status == 'disabled':
        message = 'Reporte financiero mensual deshabilitado por configuración.'
        return {
            'status': status,
            'category': 'warning',
            'message': message,
            'detail': None,
            'log_message': message,
            'sent_count': sent_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
        }

    if sent_count == 0 and skipped_count == 0 and failed_count == 0:
        message = 'No se encontraron destinatarios con correo configurado para este reporte mensual.'
        return {
            'status': status,
            'category': 'warning',
            'message': message,
            'detail': None,
            'log_message': message,
            'sent_count': sent_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
        }

    if failed_count:
        first_failed = (result.get('failed') or [{}])[0]
        failed_email = first_failed.get('email') or 'destinatario desconocido'
        failed_error = first_failed.get('error') or 'Error desconocido'
        message = (
            f'Reporte {report_period} procesado: {sent_count} enviados, '
            f'{skipped_count} omitidos y {failed_count} con error.'
        )
        detail = f'Primer error de envío para {failed_email}: {failed_error}'
        return {
            'status': status,
            'category': 'warning',
            'message': message,
            'detail': detail,
            'log_message': f'{message} {detail}',
            'sent_count': sent_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
        }

    if sent_count:
        message = (
            f'Reporte {report_period} enviado: {sent_count} destinatarios enviados '
            f'y {skipped_count} omitidos.'
        )
        return {
            'status': status,
            'category': 'success',
            'message': message,
            'detail': None,
            'log_message': message,
            'sent_count': sent_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
        }

    message = f'Reporte {report_period} sin nuevos envíos: {skipped_count} destinatarios ya lo habían recibido.'
    return {
        'status': status,
        'category': 'warning',
        'message': message,
        'detail': None,
        'log_message': message,
        'sent_count': sent_count,
        'skipped_count': skipped_count,
        'failed_count': failed_count,
    }


def dispatch_monthly_financial_report(reference_dt: Optional[datetime] = None,
                                      output_path: Optional[str] = None,
                                      allow_retry_failed: bool = True,
                                      period_mode: str = 'previous_month',
                                      app_config: Optional[Dict] = None,
                                      admin_only: Optional[bool] = None,
                                      admin_email_override: Optional[str] = None,
                                      respect_enabled_setting: bool = False) -> Dict:
    settings = get_monthly_report_settings(app_config)

    effective_admin_only = settings['admin_only'] if admin_only is None else bool(admin_only)
    effective_admin_email = admin_email_override
    if effective_admin_email is None:
        configured_admin_email = str(settings.get('admin_email') or '').strip()
        effective_admin_email = configured_admin_email or None

    if respect_enabled_setting and not settings.get('enabled', True):
        result = {
            'report_period': get_report_period(reference_dt=reference_dt, period_mode=period_mode)['report_period'],
            'period_mode': _normalize_period_mode(period_mode),
            'pdf_path': None,
            'admin_only': effective_admin_only,
            'resolved_admin_email': _normalize_email(effective_admin_email),
            'sent': [],
            'skipped': [],
            'failed': [],
            'status': 'disabled',
        }
        result['summary'] = build_monthly_report_dispatch_summary(result)
        return result

    result = send_previous_month_financial_report(
        reference_dt=reference_dt,
        output_path=output_path,
        allow_retry_failed=allow_retry_failed,
        admin_only=effective_admin_only,
        admin_email_override=effective_admin_email,
        period_mode=period_mode,
    )
    result['status'] = 'processed'
    result['summary'] = build_monthly_report_dispatch_summary(result)
    return result


def get_previous_month_period(reference_dt: Optional[datetime] = None) -> Dict[str, str]:
    reference_dt = reference_dt or datetime.now()
    first_day_current_month = reference_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day_previous_month = first_day_current_month - timedelta(days=1)
    first_day_previous_month = last_day_previous_month.replace(day=1)
    month_name = MONTH_NAMES_ES[last_day_previous_month.month]

    return {
        'date_from': first_day_previous_month.strftime('%Y-%m-%d'),
        'date_to': last_day_previous_month.strftime('%Y-%m-%d'),
        'report_period': first_day_previous_month.strftime('%Y-%m'),
        'month_name': month_name,
        'period_label': f"{month_name.title()} {last_day_previous_month.year}",
    }


def get_report_period(reference_dt: Optional[datetime] = None, period_mode: str = 'previous_month') -> Dict[str, object]:
    reference_dt = reference_dt or datetime.now()
    period_mode = _normalize_period_mode(period_mode)

    if period_mode == 'current_month_to_date':
        first_day_current_month = reference_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_name = MONTH_NAMES_ES[first_day_current_month.month]
        return {
            'date_from': first_day_current_month.strftime('%Y-%m-%d'),
            'date_to': reference_dt.strftime('%Y-%m-%d'),
            'report_period': first_day_current_month.strftime('%Y-%m'),
            'month_name': month_name,
            'period_label': f"{month_name.title()} {first_day_current_month.year} (al {reference_dt.strftime('%d/%m/%Y')})",
            'period_mode': period_mode,
            'period_mode_label': 'Mes actual a la fecha',
            'is_partial_period': True,
        }

    period = get_previous_month_period(reference_dt=reference_dt)
    period['period_mode'] = period_mode
    period['period_mode_label'] = 'Mes anterior completo'
    period['is_partial_period'] = False
    return period


def get_monthly_financial_report_data(reference_dt: Optional[datetime] = None,
                                      period_mode: str = 'previous_month') -> Dict:
    from accounting import get_cash_flow_statement, get_income_statement

    period = get_report_period(reference_dt=reference_dt, period_mode=period_mode)
    income_statement = get_income_statement(period['date_from'], period['date_to'])
    cash_flow_statement = get_cash_flow_statement(period['date_from'], period['date_to'])

    return {
        'report_type': MONTHLY_REPORT_TYPE,
        'date_from': period['date_from'],
        'date_to': period['date_to'],
        'report_period': period['report_period'],
        'month_name': period['month_name'],
        'period_label': period['period_label'],
        'period_mode': period['period_mode'],
        'period_mode_label': period['period_mode_label'],
        'is_partial_period': period['is_partial_period'],
        'generated_at': _utcnow_sql(),
        'opening_balance': cash_flow_statement.get('opening_balance', 0),
        'closing_balance': cash_flow_statement.get('closing_balance', 0),
        'net_change': cash_flow_statement.get('net_change', 0),
        'net_operating': cash_flow_statement.get('net_operating', 0),
        'collections': income_statement.get('income_payments', []),
        'total_collections': income_statement.get('operating_income', 0),
        'pending_receivables': income_statement.get('pending_invoices', []),
        'total_pending_receivables': income_statement.get('total_pending', 0),
        'expenses': income_statement.get('expense_items', []),
        'total_expenses': income_statement.get('operating_expenses', 0),
        'other_income': income_statement.get('other_income', 0),
        'other_income_detail': income_statement.get('other_income_detail', []),
        'other_expenses': income_statement.get('other_expenses', 0),
        'other_expenses_detail': income_statement.get('other_expenses_detail', []),
        'financing_inflows': cash_flow_statement.get('financing_inflows', 0),
        'financing_inflows_detail': cash_flow_statement.get('financing_inflows_detail', []),
        'financing_outflows': cash_flow_statement.get('financing_outflows', 0),
        'financing_outflows_detail': cash_flow_statement.get('financing_outflows_detail', []),
        'income_statement': income_statement,
        'cash_flow_statement': cash_flow_statement,
    }


def add_current_balance_context(report_data: Dict, as_of: Optional[datetime] = None) -> Dict:
    from accounting import get_balance_summary

    balance_summary = get_balance_summary()
    as_of_dt = as_of or datetime.now()
    period_label = report_data.get('period_label', report_data.get('report_period', 'este periodo'))

    enriched_report_data = dict(report_data)
    enriched_report_data.update({
        'current_balance_as_of': as_of_dt.strftime('%d-%m-%Y'),
        'current_balance_amount': balance_summary.get('balance', 0),
        'current_balance_title': f"Saldo actualizado al {as_of_dt.strftime('%d-%m-%Y')}",
        'current_balance_note': (
            f"El cierre del reporte para {period_label} permanece sin cambios; "
            "este saldo actualizado es informativo y se recalcula al descargar o enviar el reporte."
        ),
    })
    return enriched_report_data


def get_monthly_report_recipients(admin_email_override: Optional[str] = None) -> Dict[str, object]:
    from company import get_company_info

    company_info = get_company_info() or {}
    admin_email = _resolve_monthly_report_admin_email(
        company_info=company_info,
        admin_email_override=admin_email_override,
    )

    recipients: List[Dict[str, str]] = []
    seen_emails = set()

    if admin_email:
        recipients.append({
            'email': admin_email,
            'name': company_info.get('name') or 'Administración',
            'recipient_type': 'admin',
            'unit_number': '',
        })
        seen_emails.add(admin_email)

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT resident_email as email,
                   COALESCE(resident_name, 'Residente') as name,
                   number as unit_number
            FROM apartments
            WHERE resident_email IS NOT NULL AND TRIM(resident_email) != ''
            ORDER BY number
        """)
        apartment_rows = [dict(row) for row in cur.fetchall()]

        cur.execute("""
            SELECT r.email,
                   COALESCE(r.name, a.resident_name, 'Residente') as name,
                   COALESCE(a.number, '') as unit_number
            FROM residents r
            LEFT JOIN apartments a ON a.id = r.unit_id
            WHERE r.email IS NOT NULL AND TRIM(r.email) != ''
            ORDER BY a.number, r.name
        """)
        resident_rows = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    for row in apartment_rows + resident_rows:
        email = _normalize_email(row.get('email'))
        if not email or email in seen_emails:
            continue

        recipients.append({
            'email': email,
            'name': row.get('name') or 'Residente',
            'recipient_type': 'resident',
            'unit_number': row.get('unit_number') or '',
        })
        seen_emails.add(email)

    return {
        'admin_email': admin_email,
        'resident_recipients': [r for r in recipients if r['recipient_type'] == 'resident'],
        'all_recipients': recipients,
    }


def claim_monthly_report_dispatch(
    report_period: str,
    recipient_email: str,
    report_type: str = MONTHLY_REPORT_TYPE,
    allow_retry_failed: bool = True,
) -> bool:
    normalized_email = _normalize_email(recipient_email)
    if not normalized_email:
        return False

    now = _utcnow_sql()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, status
            FROM monthly_report_dispatch_log
            WHERE report_type = ? AND report_period = ? AND recipient_email = ?
        """, (report_type, report_period, normalized_email))
        row = cur.fetchone()

        if row:
            status = row['status']
            if status in ('sent', 'sending'):
                return False
            if status == 'failed' and not allow_retry_failed:
                return False

            cur.execute("""
                UPDATE monthly_report_dispatch_log
                SET status = 'sending',
                    error_message = NULL,
                    started_at = ?,
                    updated_at = ?
                WHERE id = ? AND status = 'failed'
            """, (now, now, row['id']))
            conn.commit()
            return cur.rowcount == 1

        try:
            cur.execute("""
                INSERT INTO monthly_report_dispatch_log (
                    report_type,
                    report_period,
                    recipient_email,
                    status,
                    started_at,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, 'sending', ?, ?, ?)
            """, (report_type, report_period, normalized_email, now, now, now))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    finally:
        conn.close()


def mark_monthly_report_dispatch_sent(
    report_period: str,
    recipient_email: str,
    report_type: str = MONTHLY_REPORT_TYPE,
    subject: Optional[str] = None,
) -> None:
    normalized_email = _normalize_email(recipient_email)
    now = _utcnow_sql()

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE monthly_report_dispatch_log
            SET status = 'sent',
                subject = ?,
                sent_at = ?,
                updated_at = ?,
                error_message = NULL
            WHERE report_type = ? AND report_period = ? AND recipient_email = ?
        """, (subject, now, now, report_type, report_period, normalized_email))
        conn.commit()
    finally:
        conn.close()


def mark_monthly_report_dispatch_failed(
    report_period: str,
    recipient_email: str,
    error_message: str,
    report_type: str = MONTHLY_REPORT_TYPE,
) -> None:
    normalized_email = _normalize_email(recipient_email)
    now = _utcnow_sql()

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE monthly_report_dispatch_log
            SET status = 'failed',
                error_message = ?,
                updated_at = ?
            WHERE report_type = ? AND report_period = ? AND recipient_email = ?
        """, (error_message[:1000], now, report_type, report_period, normalized_email))
        conn.commit()
    finally:
        conn.close()


def generate_monthly_financial_report_pdf_file(report_data: Dict, company_info: Dict,
                                               output_path: Optional[str] = None) -> str:
    from receipt_pdf import generate_monthly_financial_report_pdf

    if output_path:
        pdf_path = Path(output_path)
    else:
        pdf_dir = Path(__file__).parent / 'static' / 'reports'
        pdf_path = pdf_dir / f"monthly_financial_report_{report_data['report_period']}.pdf"

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    generate_monthly_financial_report_pdf(report_data, company_info, output_path=str(pdf_path))
    return str(pdf_path)


def send_previous_month_financial_report(reference_dt: Optional[datetime] = None,
                                         output_path: Optional[str] = None,
                                         allow_retry_failed: bool = True,
                                         admin_only: bool = False,
                                         admin_email_override: Optional[str] = None,
                                         period_mode: str = 'previous_month') -> Dict:
    from company import get_company_info
    from senders import send_monthly_financial_report_email

    report_data = get_monthly_financial_report_data(
        reference_dt=reference_dt,
        period_mode=period_mode,
    )
    report_data = add_current_balance_context(report_data)
    recipients = get_monthly_report_recipients(admin_email_override=admin_email_override)
    company_info = get_company_info() or {}

    result = {
        'report_period': report_data['report_period'],
        'period_mode': report_data.get('period_mode', 'previous_month'),
        'pdf_path': None,
        'admin_only': admin_only,
        'resolved_admin_email': recipients.get('admin_email', ''),
        'sent': [],
        'skipped': [],
        'failed': [],
    }

    target_recipients = recipients['all_recipients']
    if admin_only:
        admin_email = recipients.get('admin_email')
        target_recipients = [recipient for recipient in recipients['all_recipients'] if recipient['email'] == admin_email]

    if not target_recipients:
        if admin_only:
            result['failed'].append({
                'email': recipients.get('admin_email') or '',
                'error': 'No se encontró un correo de administrador configurado para el reporte mensual.',
            })
        return result

    pdf_path = generate_monthly_financial_report_pdf_file(report_data, company_info, output_path=output_path)
    result['pdf_path'] = pdf_path

    for recipient in target_recipients:
        email = recipient['email']
        if not claim_monthly_report_dispatch(
            report_data['report_period'],
            email,
            allow_retry_failed=allow_retry_failed,
        ):
            result['skipped'].append(email)
            continue

        try:
            subject = send_monthly_financial_report_email(
                email,
                report_data,
                pdf_path,
                recipient_name=recipient.get('name'),
                recipient_type=recipient.get('recipient_type', 'resident'),
                company_name=company_info.get('name'),
            )
            mark_monthly_report_dispatch_sent(report_data['report_period'], email, subject=subject)
            result['sent'].append(email)
        except Exception as exc:
            error_message = str(exc)
            mark_monthly_report_dispatch_failed(report_data['report_period'], email, error_message)
            _log(f"Error sending monthly report to {email}: {error_message}")
            result['failed'].append({'email': email, 'error': error_message})

    return result

def get_sales_by_period(period: str = "month") -> List[Dict]:
    """Ventas agrupadas por período con montos reales cobrados"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        period_format = {
            'day': '%Y-%m-%d',
            'week': '%Y-W%W',
            'month': '%Y-%m',
            'year': '%Y'
        }
        fmt = period_format.get(period, '%Y-%m')
        
        cur.execute(f"""
            SELECT 
                strftime('{fmt}', i.issued_date) as period,
                COUNT(*) as total_invoices,
                SUM(i.amount) as total_amount,
                AVG(i.amount) as avg_amount,
                COALESCE(SUM(CASE WHEN i.paid = 1 THEN i.amount ELSE 0 END), 0) as paid_amount,
                COALESCE((
                    SELECT SUM(p.amount) FROM payments p
                    JOIN invoices i2 ON p.invoice_id = i2.id
                    WHERE strftime('{fmt}', i2.issued_date) = strftime('{fmt}', i.issued_date)
                ), 0) as collected
            FROM invoices i
            GROUP BY period
            ORDER BY period DESC
        """)
        
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_sales_by_period: {e}")
        return []

def get_sales_by_client(limit: int = 20) -> List[Dict]:
    """Ventas por cliente con montos reales pagados (JOIN con apartments)"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                i.unit_id as id,
                a.number as unit_number,
                COALESCE(a.resident_name, 'Unidad ' || a.number) as client_name,
                COUNT(i.id) as invoice_count,
                SUM(i.amount) as total_spent,
                COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id IN 
                    (SELECT id FROM invoices WHERE unit_id = i.unit_id)), 0) as paid_amount,
                SUM(i.amount) - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id IN 
                    (SELECT id FROM invoices WHERE unit_id = i.unit_id)), 0) as pending_amount
            FROM invoices i
            LEFT JOIN apartments a ON i.unit_id = a.id
            GROUP BY i.unit_id
            ORDER BY total_spent DESC
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_sales_by_client: {e}")
        return []

def get_sales_by_service(limit: int = 15) -> List[Dict]:
    """Ventas por tipo de servicio desde descripciones de facturas"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                UPPER(TRIM(description)) as service_name,
                COUNT(*) as times_sold,
                SUM(amount) as total_revenue,
                AVG(amount) as avg_price
            FROM invoices
            WHERE description IS NOT NULL AND description != ''
            GROUP BY UPPER(TRIM(description))
            ORDER BY total_revenue DESC
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows] if rows else []
    except Exception as e:
        _log(f"Error in get_sales_by_service: {e}")
        return []

def get_accounts_receivable(status: Optional[str] = None, days_overdue: Optional[int] = None) -> List[Dict]:
    """
    Cuentas por cobrar con balance real (descontando pagos parciales).
    Solo muestra facturas que aún tienen saldo pendiente.
    """
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        query = """
            SELECT 
                i.id,
                i.id as invoice_number,
                i.issued_date,
                i.due_date,
                i.unit_id,
                a.number as unit_number,
                COALESCE(a.resident_name, 'Unidad ' || COALESCE(a.number, i.unit_id)) as client_name,
                i.amount as total,
                COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as paid_amount,
                i.amount - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as balance,
                i.description,
                CAST((julianday('now') - julianday(i.issued_date)) AS INTEGER) as days_pending
            FROM invoices i
            LEFT JOIN apartments a ON i.unit_id = a.id
            WHERE i.paid = 0
              AND i.amount - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) > 0
        """
        params = []
        
        if days_overdue:
            query += " AND julianday('now') - julianday(i.issued_date) > ?"
            params.append(days_overdue)
        
        query += " ORDER BY i.issued_date ASC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_accounts_receivable: {e}")
        return []

def get_overdue_accounts(days: int = 30) -> List[Dict]:
    """Cuentas vencidas por más de X días con balance real"""
    return get_accounts_receivable(days_overdue=days)

def get_financial_summary(date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict:
    """Resumen financiero general con montos reales de pagos"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        
        # Total facturado
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_invoiced, COUNT(*) as invoice_count
            FROM invoices
            WHERE DATE(issued_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        sales = dict(cur.fetchone())
        
        # Total realmente cobrado (suma de payments, no solo flag paid)
        cur.execute("""
            SELECT COALESCE(SUM(p.amount), 0) as total_collected
            FROM payments p
            JOIN invoices i ON p.invoice_id = i.id
            WHERE DATE(i.issued_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        collected = dict(cur.fetchone())
        
        # Pendiente real (facturado - cobrado)
        total_invoiced = sales.get('total_invoiced', 0) or 0
        total_collected = collected.get('total_collected', 0) or 0
        total_pending = total_invoiced - total_collected
        
        # Facturas pendientes count
        cur.execute("""
            SELECT COUNT(*) as pending_count
            FROM invoices
            WHERE paid = 0 AND DATE(issued_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        pending_info = dict(cur.fetchone())
        
        # Gastos totales
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_expenses
            FROM expenses
            WHERE DATE(created_at) BETWEEN ? AND ?
        """, (date_from, date_to))
        expenses = dict(cur.fetchone())
        total_expenses = expenses.get('total_expenses', 0) or 0
        
        # Clientes activos
        cur.execute("""
            SELECT COUNT(DISTINCT unit_id) as active_clients
            FROM invoices
            WHERE DATE(issued_date) BETWEEN ? AND ?
        """, (date_from, date_to))
        clients = dict(cur.fetchone())
        
        conn.close()
        
        return {
            'total_invoiced': total_invoiced,
            'invoice_count': sales.get('invoice_count', 0),
            'total_collected': total_collected,
            'total_pending': total_pending,
            'pending_count': pending_info.get('pending_count', 0),
            'total_expenses': total_expenses,
            'net_income': total_collected - total_expenses,
            'active_clients': clients.get('active_clients', 0),
            'date_from': date_from,
            'date_to': date_to,
            'collection_rate': round((total_collected / total_invoiced * 100) if total_invoiced > 0 else 0, 1)
        }
    except Exception as e:
        _log(f"Error in get_financial_summary: {e}")
        return {}

def get_client_statement(unit_id: int) -> Dict:
    """Estado de cuenta detallado de un cliente"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Info del cliente desde apartments
        cur.execute("SELECT id, number, resident_name FROM apartments WHERE id = ?", (unit_id,))
        apt_row = cur.fetchone()
        if apt_row:
            apt = dict(apt_row)
            client = {'id': unit_id, 'unit_number': apt['number'], 'owner': apt['resident_name'] or f"Apto {apt['number']}"}
        else:
            client = {'id': unit_id, 'unit_number': '?', 'owner': f'Unidad {unit_id}'}
        
        # Facturas con pagos reales
        cur.execute("""
            SELECT 
                i.id, i.issued_date, i.amount as total, i.description,
                COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as paid_amount,
                i.amount - COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.invoice_id = i.id), 0) as balance,
                CASE WHEN i.paid = 1 THEN 'paid' ELSE 'pending' END as status
            FROM invoices i
            WHERE i.unit_id = ?
            ORDER BY i.issued_date DESC
        """, (unit_id,))
        
        invoices = [dict(r) for r in cur.fetchall()]
        conn.close()
        
        total_paid = sum(inv['paid_amount'] for inv in invoices)
        total_pending = sum(inv['balance'] for inv in invoices if inv['balance'] > 0)
        
        return {
            'client': client,
            'invoices': invoices,
            'total_paid': total_paid,
            'total_pending': total_pending
        }
    except Exception as e:
        _log(f"Error in get_client_statement: {e}")
        return {}

def get_top_clients(metric: str = 'sales', limit: int = 10) -> List[Dict]:
    """Clientes principales por métrica"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        if metric == 'invoices':
            select = 'COUNT(i.id) as metric_value'
        elif metric == 'pending':
            select = """SUM(i.amount) - COALESCE((SELECT SUM(p.amount) FROM payments p 
                        WHERE p.invoice_id IN (SELECT id FROM invoices WHERE unit_id = i.unit_id)), 0) as metric_value"""
        else:  # sales
            select = 'SUM(i.amount) as metric_value'
        
        cur.execute(f"""
            SELECT 
                i.unit_id as id,
                a.number as unit_number,
                COALESCE(a.resident_name, 'Unidad ' || COALESCE(a.number, i.unit_id)) as owner,
                {select}
            FROM invoices i
            LEFT JOIN apartments a ON i.unit_id = a.id
            GROUP BY i.unit_id
            ORDER BY metric_value DESC
            LIMIT ?
        """, (limit,))
        
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        _log(f"Error in get_top_clients: {e}")
        return []

def get_revenue_by_status() -> Dict[str, float]:
    """Ingresos por estado"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        
        # Cobrado real (suma de payments)
        cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM payments")
        paid = cur.fetchone()[0] or 0
        
        # Facturado total
        cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM invoices")
        invoiced = cur.fetchone()[0] or 0
        
        conn.close()
        
        return {
            'Pagado': paid,
            'Pendiente': max(invoiced - paid, 0)
        }
    except Exception as e:
        _log(f"Error in get_revenue_by_status: {e}")
        return {}
