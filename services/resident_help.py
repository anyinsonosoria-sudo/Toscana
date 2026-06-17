"""
Resident Help Service
=====================
Lógica de negocio para el portal de residentes: NLP, respuestas,
contexto financiero, hilo de conversación e integración IA.

Extraído de app.py para mantener el archivo principal manejable.
"""

from typing import Any, Optional

from flask import url_for, session, request, render_template, current_app
from flask_login import current_user
import requests as http_requests

import db
import company
import residents


# ──────────────────────────────────────────────
# Constantes de meses (español)
# ──────────────────────────────────────────────

MONTH_NAMES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}

MONTH_LOOKUP = {name.lower(): number for number, name in MONTH_NAMES.items()}

MONTH_SHORT_NAMES = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}


# ──────────────────────────────────────────────
# Helpers de formato
# ──────────────────────────────────────────────

def format_currency(amount) -> str:
    try:
        return f"RD$ {float(amount or 0):,.2f}"
    except (TypeError, ValueError):
        return "RD$ 0.00"


def format_month_option(month_key: str) -> dict:
    try:
        year_value, month_value = month_key.split('-', 1)
        month_number = int(month_value)
        return {
            'value': month_key,
            'label': f"{MONTH_NAMES[month_number]} {year_value}",
        }
    except Exception:
        return {'value': month_key, 'label': month_key}


def format_short_date(date_value: str | None) -> str:
    from datetime import datetime

    if not date_value:
        return 'sin fecha'
    try:
        return datetime.strptime(date_value[:10], '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        return date_value[:10]


# ──────────────────────────────────────────────
# NLP helpers
# ──────────────────────────────────────────────

def normalize_question(question: str) -> str:
    import re
    import unicodedata

    normalized = unicodedata.normalize('NFKD', question or '')
    normalized = normalized.encode('ascii', 'ignore').decode('ascii')
    normalized = re.sub(r'[^a-z0-9\s]+', ' ', normalized.lower())
    return ' '.join(normalized.split())


def question_has_any(normalized_question: str, fragments: list[str]) -> bool:
    return any(fragment in normalized_question for fragment in fragments)


def is_followup_question(normalized_question: str) -> bool:
    """Returns True when the question references a previous answer rather than introducing a new topic."""
    followup_signals = [
        # Pronombres demostrativos
        'ese', 'eso', 'esa', 'esos', 'esas', 'esto', 'estos', 'estas',
        # Solicitudes de desglose
        'desglos', 'detalla', 'detalle de', 'dame mas', 'ampliar',
        'mas detalle', 'mas informacion', 'con mas detalle',
        'que incluye', 'que contiene', 'como se compone', 'que hay ahi',
        'del total', 'de eso', 'de ese', 'de esa', 'de esas', 'de esos',
        'por categoria', 'por concepto', 'en que consiste',
        'puedes desglosar', 'puedes explicar', 'puedes ampliar',
        'y cuanto', 'y cuales', 'cuales son esos', 'cuales fueron',
        # Preguntas conversacionales de seguimiento
        'explicame', 'por que', 'como asi', 'en que se gasto',
        'en que se uso', 'a que se debe', 'de donde sale',
        'de donde salio', 'como es eso', 'que paso con',
        'y el resto', 'algo mas', 'que mas', 'hay algo mas',
        'cuanto fue', 'cuando fue', 'quien', 'a quien',
        'y los demas', 'y las demas', 'continua', 'sigue',
        'y eso', 'pero', 'entonces',
    ]
    return question_has_any(normalized_question, followup_signals)


def extract_last_assistant_topic(thread: list) -> Optional[dict]:
    """Extracts the conversation topic and month reference from the last assistant message."""
    last_assistant = next(
        (msg for msg in reversed(thread) if msg.get('role') == 'assistant'),
        None,
    )
    if not last_assistant:
        return None

    raw_text = ' '.join(filter(None, [
        last_assistant.get('title', ''),
        last_assistant.get('content', ''),
        last_assistant.get('detail', ''),
    ]))
    norm = normalize_question(raw_text)

    topic: dict[str, Any] = {
        'type': None,
        'month_reference': None,
        'was_expenses': False,
        'was_collections': False,
    }

    month_ref = extract_month_reference(norm)
    if month_ref:
        topic['month_reference'] = month_ref

    if question_has_any(norm, ['gasto', 'egreso', 'cobro', 'ingreso', 'reporte', 'cierre', 'mensual', 'operativo']):
        topic['type'] = 'report'
        topic['was_expenses'] = question_has_any(norm, ['gasto', 'gastos', 'egreso', 'operativo'])
        topic['was_collections'] = question_has_any(norm, ['cobro', 'cobros', 'ingreso', 'ingresos', 'recaud'])
    elif question_has_any(norm, ['pago', 'abono', 'historial', 'movimiento']):
        topic['type'] = 'payments'
    elif question_has_any(norm, ['factura', 'balance', 'saldo', 'deuda', 'pendient']):
        topic['type'] = 'account'
    elif question_has_any(norm, ['apartamento', 'apartamento', 'vinculad', 'inmueble']):
        topic['type'] = 'units'
    elif question_has_any(norm, ['contacto', 'telefono', 'correo', 'administracion']):
        topic['type'] = 'contact'

    return topic if topic['type'] else None


def extract_month_reference(question: str) -> Optional[dict]:
    import re
    from datetime import datetime, timedelta

    normalized_question = normalize_question(question)
    now = datetime.now()

    if any(fragment in normalized_question for fragment in ['este mes', 'mes actual', 'mes en curso', 'reporte actual']):
        return {
            'label': f"{MONTH_NAMES[now.month]} {now.year}",
            'reference_date': now.strftime('%Y-%m-%d'),
            'period_mode': 'current_month_to_date',
        }

    if any(fragment in normalized_question for fragment in ['mes pasado', 'mes anterior', 'ultimo mes']):
        previous_month_anchor = (now.replace(day=1) - timedelta(days=1))
        return {
            'label': f"{MONTH_NAMES[previous_month_anchor.month]} {previous_month_anchor.year}",
            'reference_date': now.strftime('%Y-%m-%d'),
            'period_mode': 'previous_month',
        }

    year_match = re.search(r'(20\d{2})', normalized_question)
    year_value = int(year_match.group(1)) if year_match else datetime.now().year
    for month_name, month_number in MONTH_LOOKUP.items():
        if month_name in normalized_question:
            reference_month = month_number + 1
            reference_year = year_value
            if reference_month == 13:
                reference_month = 1
                reference_year += 1
            return {
                'label': f"{MONTH_NAMES[month_number]} {year_value}",
                'reference_date': f"{reference_year}-{reference_month:02d}-01",
                'period_mode': 'previous_month',
            }
    return None


# ──────────────────────────────────────────────
# Construcción de payloads de respuesta
# ──────────────────────────────────────────────

def build_help_payload(
    title: str,
    body: str,
    detail: str = '',
    tone: str = 'primary',
    link_url: str | None = None,
    link_label: str | None = None,
) -> dict[str, str | None]:
    return {
        'tone': tone,
        'title': title,
        'body': body,
        'detail': detail,
        'link_url': link_url,
        'link_label': link_label,
    }


def build_account_help_answer(normalized_question: str, context: dict) -> dict[str, str | None]:
    totals = context['resident_totals']
    pending_preview = list(context.get('pending_preview') or [])
    pending_count = int(totals.get('pending_invoices') or 0)
    pending_balance = totals.get('balance') or 0

    if pending_count == 0:
        body = 'No tienes balance pendiente ni facturas vencidas en este momento.'
        detail = (
            f"Pagos registrados: {format_currency(totals.get('total_paid'))}. "
            'Tu cuenta se encuentra al dia en los apartamentos vinculados.'
        )
        tone = 'success'
    else:
        body = (
            f"Tu cuenta mantiene {pending_count} factura(s) pendiente(s) por "
            f"{format_currency(pending_balance)}."
        )
        detail_parts = [
            f"Pagos registrados: {format_currency(totals.get('total_paid'))}."
        ]
        if pending_preview:
            detail_parts.append(
                'Pendientes recientes: ' + '; '.join(
                    f"{invoice.get('description') or 'Factura'} "
                    f"(Apto {invoice.get('apartment_number') or invoice.get('unit_id') or 'N/D'})"
                    for invoice in pending_preview[:3]
                )
            )
        detail = ' '.join(detail_parts)
        tone = 'warning'

    invoice_specific = question_has_any(
        normalized_question,
        ['factura', 'facturas', 'recibo', 'recibos', 'pendient', 'vencid', 'por pagar'],
    )
    balance_specific = question_has_any(
        normalized_question,
        ['saldo', 'balance', 'deuda', 'adeud', 'debo', 'mora', 'cuenta'],
    )
    if invoice_specific and not balance_specific:
        title = 'Estado de facturas pendientes'
    elif balance_specific and not invoice_specific:
        title = 'Balance actual de tu cuenta'
    else:
        title = 'Estado actual de tu cuenta'

    return build_help_payload(
        title=title, body=body, detail=detail, tone=tone,
        link_url=url_for('resident_billing_overview'),
        link_label='Ir a Facturas y pagos',
    )


def build_payments_help_answer(context: dict) -> dict[str, str | None]:
    recent_payments = list(context.get('recent_payments') or [])
    if not recent_payments:
        return build_help_payload(
            title='Pagos recientes',
            body='Todavia no hay pagos registrados en tus apartamentos vinculados.',
            detail='Cuando registres pagos, aqui podras resumir los movimientos mas recientes y revisar el historial.',
            tone='info',
            link_url=url_for('resident_billing_overview'),
            link_label='Abrir historial de pagos',
        )

    recent_total = sum(float(payment.get('amount') or 0) for payment in recent_payments[:3])
    latest_payment = recent_payments[0]
    detail = 'Movimientos recientes: ' + '; '.join(
        f"{format_short_date(payment.get('paid_date'))}: "
        f"{format_currency(payment.get('amount'))} "
        f"via {(payment.get('method') or 'Sin especificar')}"
        for payment in recent_payments[:3]
    )
    if latest_payment.get('invoice_desc'):
        detail += f". Ultimo concepto: {latest_payment['invoice_desc']}"

    return build_help_payload(
        title='Pagos recientes',
        body=(
            f"Tus {len(recent_payments[:3])} pago(s) mas recientes suman "
            f"{format_currency(recent_total)}. El ultimo fue "
            f"{format_currency(latest_payment.get('amount'))} el "
            f"{format_short_date(latest_payment.get('paid_date'))}."
        ),
        detail=detail, tone='primary',
        link_url=url_for('resident_billing_overview'),
        link_label='Ver historial de pagos',
    )


def build_units_help_answer(context: dict) -> dict[str, str | None]:
    resident_units = list(context.get('resident_units') or [])
    if not resident_units:
        return build_help_payload(
            title='Apartamentos vinculados',
            body='No se encontraron apartamentos vinculados a tu usuario en este momento.',
            detail='Si esperabas ver un apartamento aqui, revisa con administracion la vinculacion del residente.',
            tone='warning',
            link_url=url_for('resident_balances'),
            link_label='Volver al portal',
        )

    apartment_numbers = [
        str(unit.get('apartment_number') or unit.get('unit_id') or 'N/D') for unit in resident_units
    ]
    detail = 'Balance por apartamento: ' + '; '.join(
        f"Apto {unit.get('apartment_number') or unit.get('unit_id') or 'N/D'} "
        f"{format_currency(unit.get('balance'))}"
        for unit in resident_units[:4]
    )
    return build_help_payload(
        title='Tus apartamentos vinculados',
        body=(
            f"Tienes {len(resident_units)} apartamento(es) vinculada(s): "
            f"{', '.join(apartment_numbers[:6])}."
        ),
        detail=detail, tone='info',
        link_url=url_for('resident_balances'),
        link_label='Ver resumen por apartamento',
    )


def build_report_help_answer(
    normalized_question: str,
    context: dict,
    wants_breakdown: bool = False,
    inherited_month: Optional[dict] = None,
    inherited_expenses: bool = False,
    inherited_collections: bool = False,
) -> dict[str, str | None]:
    from datetime import datetime
    import reports as financial_reports

    month_reference = extract_month_reference(normalized_question) or inherited_month
    wants_expenses = question_has_any(normalized_question, ['gasto', 'gastos', 'egreso', 'egresos', 'costo']) or inherited_expenses
    wants_collections = question_has_any(normalized_question, ['cobro', 'cobros', 'ingreso', 'ingresos', 'recaud']) or inherited_collections
    wants_balance = question_has_any(normalized_question, ['saldo', 'balance', 'cierre', 'resultado'])

    if not month_reference:
        latest_report = context['report_months'][0] if context.get('report_months') else None
        if not latest_report:
            return build_help_payload(
                title='Reportes mensuales',
                body='Todavia no hay reportes financieros publicados para tus consultas.',
                detail='Cuando existan cierres mensuales, podras revisarlos desde la seccion Reportes.',
                tone='info',
                link_url=url_for('resident_reports'),
                link_label='Abrir Reportes',
            )
        month_reference = {
            'label': latest_report['label'],
            'reference_date': latest_report['ref_date'],
            'period_mode': 'previous_month',
        }

    reference_dt = datetime.strptime(month_reference['reference_date'], '%Y-%m-%d')
    period_mode = month_reference.get('period_mode', 'previous_month')
    report_data = financial_reports.get_monthly_financial_report_data(
        reference_dt=reference_dt, period_mode=period_mode,
    )
    report_url = url_for(
        'reports.monthly_preview_pdf',
        reference_date=month_reference['reference_date'],
        period_mode=period_mode,
    )

    if wants_expenses and not wants_collections and not wants_balance:
        if wants_breakdown:
            expense_items = report_data.get('expenses') or []
            if expense_items:
                by_cat: dict[str, float] = {}
                for item in expense_items:
                    cat = item.get('category') or 'Sin categoría'
                    by_cat[cat] = by_cat.get(cat, 0) + float(item.get('amount') or 0)
                lines = [f"- {cat}: {format_currency(total)}" for cat, total in sorted(by_cat.items(), key=lambda x: -x[1])]
                breakdown_detail = 'Desglose por categoría: ' + ' | '.join(lines[:8])
            else:
                breakdown_detail = 'No hay ítems de gasto registrados para ese período.'
        else:
            breakdown_detail = (
                f"Cobros reportados: {format_currency(report_data.get('total_collections'))}. "
                f"Balance de cierre: {format_currency(report_data.get('closing_balance'))}."
            )
        return build_help_payload(
            title=f"Gastos de {month_reference['label']}",
            body=f"Los gastos operativos publicados fueron {format_currency(report_data.get('total_expenses'))}.",
            detail=breakdown_detail, tone='primary',
            link_url=report_url, link_label='Abrir reporte mensual',
        )

    if wants_collections and not wants_expenses and not wants_balance:
        if wants_breakdown:
            collection_items = report_data.get('collections') or []
            if collection_items:
                by_cat: dict[str, float] = {}
                for item in collection_items:
                    cat = item.get('category') or item.get('payment_method') or 'Sin categoría'
                    by_cat[cat] = by_cat.get(cat, 0) + float(item.get('amount') or 0)
                lines = [f"- {cat}: {format_currency(total)}" for cat, total in sorted(by_cat.items(), key=lambda x: -x[1])]
                coll_detail = 'Desglose por categoría: ' + ' | '.join(lines[:8])
            else:
                coll_detail = 'No hay cobros registrados para ese período.'
        else:
            coll_detail = (
                f"Gastos: {format_currency(report_data.get('total_expenses'))}. "
                f"Balance de cierre: {format_currency(report_data.get('closing_balance'))}."
            )
        return build_help_payload(
            title=f"Cobros de {month_reference['label']}",
            body=f"Los cobros publicados para ese periodo fueron {format_currency(report_data.get('total_collections'))}.",
            detail=coll_detail, tone='primary',
            link_url=report_url, link_label='Ver PDF del reporte',
        )

    if wants_balance and month_reference:
        return build_help_payload(
            title=f"Balance del reporte de {month_reference['label']}",
            body=f"El balance de cierre publicado fue {format_currency(report_data.get('closing_balance'))}.",
            detail=(
                f"Cobros: {format_currency(report_data.get('total_collections'))}. "
                f"Gastos: {format_currency(report_data.get('total_expenses'))}."
            ),
            tone='primary', link_url=report_url, link_label='Ver PDF del reporte',
        )

    return build_help_payload(
        title=f"Resumen del reporte de {month_reference['label']}",
        body=(
            f"El cierre publicado muestra balance "
            f"{format_currency(report_data.get('closing_balance'))}, "
            f"cobros {format_currency(report_data.get('total_collections'))} "
            f"y gastos {format_currency(report_data.get('total_expenses'))}."
        ),
        detail='Puedes abrir el PDF para revisar el detalle completo del periodo.',
        tone='primary', link_url=report_url, link_label='Abrir reporte mensual',
    )


def build_contact_help_answer(context: dict) -> dict[str, str | None]:
    company_info = context['company_info']
    contact_lines = []
    if company_info.get('phone'):
        contact_lines.append(f"Telefono: {company_info['phone']}")
    if company_info.get('email'):
        contact_lines.append(f"Correo: {company_info['email']}")
    if company_info.get('name'):
        contact_lines.insert(0, f"Contacto principal: {company_info['name']}")
    return build_help_payload(
        title='Contacto de administracion',
        body='Puedes comunicarte con la administracion usando los datos registrados en el portal.',
        detail=' | '.join(contact_lines) if contact_lines else 'La administracion no tiene informacion de contacto completa en este momento.',
        tone='info',
        link_url=url_for('resident_help'),
        link_label='Ver centro de ayuda',
    )


def build_capabilities_help_answer(context: dict) -> dict[str, str | None]:
    totals = context['resident_totals']
    company_info = context.get('company_info') or {}
    admin_contact = company_info.get('phone') or company_info.get('email') or ''
    contact_hint = f" Si necesitas algo fuera de mi alcance, contacta a la administración ({admin_contact})." if admin_contact else ' Si necesitas algo fuera de mi alcance, contacta a la administración.'
    return build_help_payload(
        title='¿En qué puedo ayudarte?',
        body=(
            'Puedo responder sobre tu saldo, facturas pendientes, pagos, apartamentos vinculados, '
            'reportes mensuales, perfil y contraseña.' + contact_hint
        ),
        detail=(
            f"Tu cuenta: {format_currency(totals.get('balance'))} pendiente, "
            f"{int(totals.get('pending_invoices') or 0)} factura(s), "
            f"{int(totals.get('apartments') or 0)} apartamento(s)."
        ),
        tone='info',
        link_url=url_for('resident_balances'),
        link_label='Abrir resumen del portal',
    )


# ──────────────────────────────────────────────
# Motor de respuestas (rule-based)
# ──────────────────────────────────────────────

def build_help_answer(question: str, context: dict, thread: Optional[list] = None) -> Optional[dict]:
    normalized_q = normalize_question(question)
    if not normalized_q:
        return None

    wants_profile = question_has_any(normalized_q, ['foto', 'perfil', 'avatar', 'imagen', 'editar perfil', 'actualizar perfil', 'mis datos'])
    wants_password = question_has_any(normalized_q, ['contrasen', 'clave', 'password', 'cambiar acceso', 'credencial'])
    wants_account = question_has_any(normalized_q, ['saldo', 'balance', 'deuda', 'adeud', 'debo', 'pendient', 'por pagar', 'vencid', 'mora', 'factura', 'recibo', 'cuenta'])
    wants_payments = question_has_any(normalized_q, ['pago', 'pagos', 'abono', 'abonos', 'historial', 'movimiento', 'movimientos', 'pagado', 'transfer', 'deposit'])
    wants_units = question_has_any(normalized_q, ['apartamento', 'apartamentos', 'apto', 'unidad', 'unidades', 'vinculad', 'inmueble', 'inmuebles', 'propiedad'])
    wants_reports = bool(extract_month_reference(normalized_q)) or question_has_any(normalized_q, ['reporte', 'reportes', 'informe', 'informes', 'mensual', 'gasto', 'gastos', 'egreso', 'egresos', 'cobro', 'cobros', 'ingreso', 'ingresos'])
    wants_contact = question_has_any(normalized_q, ['telefono', 'correo', 'email', 'contact', 'administracion', 'soporte', 'oficina', 'whatsapp'])
    wants_capabilities = question_has_any(normalized_q, ['que puedes', 'que informacion', 'que sabes', 'que puedo preguntar', 'como me puedes ayudar', 'ayuda del portal'])

    sections = []

    if wants_profile:
        sections.append(build_help_payload(
            title='Actualizar foto o perfil',
            body='Puedes actualizar tu foto, nombre y telefono desde Mi Perfil dentro del portal.',
            detail='Abre el editor de perfil, carga la imagen y guarda los cambios.',
            tone='primary',
            link_url=url_for('auth.edit_profile'),
            link_label='Abrir Mi Perfil',
        ))

    if wants_password:
        sections.append(build_help_payload(
            title='Cambiar contrasena',
            body='El cambio de contrasena se realiza desde la opcion de seguridad del portal.',
            detail='Debes confirmar tu contrasena actual antes de guardar la nueva.',
            tone='warning',
            link_url=url_for('auth.change_password'),
            link_label='Cambiar contrasena',
        ))

    if wants_units:
        sections.append(build_units_help_answer(context))
    if wants_payments:
        sections.append(build_payments_help_answer(context))
    if wants_account:
        sections.append(build_account_help_answer(normalized_q, context))
    if wants_reports:
        sections.append(build_report_help_answer(normalized_q, context))
    if wants_contact:
        sections.append(build_contact_help_answer(context))
    if wants_capabilities and not sections:
        sections.append(build_capabilities_help_answer(context))

    # ── Follow-up inference ────────────────────────────────────────
    if not sections and thread and is_followup_question(normalized_q):
        last_topic = extract_last_assistant_topic(thread)
        if last_topic:
            if last_topic['type'] == 'report':
                sections.append(build_report_help_answer(
                    normalized_q, context, wants_breakdown=True,
                    inherited_month=last_topic.get('month_reference'),
                    inherited_expenses=last_topic.get('was_expenses', False),
                    inherited_collections=last_topic.get('was_collections', False),
                ))
            elif last_topic['type'] == 'payments':
                sections.append(build_payments_help_answer(context))
            elif last_topic['type'] == 'account':
                sections.append(build_account_help_answer(normalized_q, context))
            elif last_topic['type'] == 'units':
                sections.append(build_units_help_answer(context))
            elif last_topic['type'] == 'contact':
                sections.append(build_contact_help_answer(context))

    if not sections:
        return build_capabilities_help_answer(context)

    if len(sections) == 1:
        return sections[0]

    detail_parts = [section.get('detail') for section in sections[:3] if section.get('detail')]
    tone = 'warning' if any(s.get('tone') == 'warning' for s in sections) else sections[0].get('tone', 'primary')
    primary_link = next((s for s in sections if s.get('link_url')), sections[0])
    return build_help_payload(
        title='Resumen de tu consulta',
        body=' '.join(s.get('body', '') for s in sections[:3] if s.get('body')),
        detail=' | '.join(detail_parts),
        tone=tone,
        link_url=primary_link.get('link_url'),
        link_label=primary_link.get('link_label') or 'Abrir detalle',
    )


# ──────────────────────────────────────────────
# Thread (hilo de conversación en sesión)
# ──────────────────────────────────────────────

def sanitize_help_text(value: Any, max_length: int = 700) -> str:
    if not value:
        return ""
    val_str = str(value).strip()
    return val_str if len(val_str) <= max_length else val_str[:max_length - 3].rstrip() + '...'


def _thread_key() -> str:
    return f"resident_help_thread_{current_user.id}"


def serialize_help_message(message: dict[str, Any]) -> dict[str, str]:
    role = 'assistant' if message.get('role') == 'assistant' else 'user'
    return {
        'role': role,
        'title': sanitize_help_text(message.get('title'), 120),
        'content': sanitize_help_text(message.get('content'), 4000),
        'detail': sanitize_help_text(message.get('detail'), 280),
        'tone': sanitize_help_text(message.get('tone'), 24) or ('primary' if role == 'assistant' else 'secondary'),
        'source': sanitize_help_text(message.get('source'), 24) or ('rules' if role == 'assistant' else 'user'),
        'link_url': str(message.get('link_url') or '')[:500],
        'link_label': sanitize_help_text(message.get('link_label'), 60),
    }


def get_help_thread() -> list[dict[str, str]]:
    raw_thread = session.get(_thread_key()) or []
    if not isinstance(raw_thread, list):
        return []
    return [
        serialize_help_message(item)
        for item in raw_thread[-8:]
        if isinstance(item, dict)
    ]


def store_help_thread(thread: list[dict[str, Any]]):
    session[_thread_key()] = [
        serialize_help_message(item)
        for item in thread[-8:]
        if isinstance(item, dict)
    ]
    session.modified = True


def clear_help_thread():
    session.pop(_thread_key(), None)
    session.modified = True


# ──────────────────────────────────────────────
# Integración IA (OpenAI-compatible)
# ──────────────────────────────────────────────

def ai_enabled() -> bool:
    cfg = current_app.config
    return bool(
        cfg.get('RESIDENT_AI_CHAT_ENABLED')
        and cfg.get('RESIDENT_AI_API_KEY')
    )


def _build_ai_context_text(question: str, context: dict, deterministic_answer: Optional[dict]) -> str:
    from datetime import datetime
    import reports as financial_reports

    totals = context.get('resident_totals') or {}
    company_info = context.get('company_info') or {}
    report_months = context.get('report_months') or []
    pending_preview = context.get('pending_preview') or []
    
    # Combinar preguntas anteriores para entender el contexto de tiempo en seguimientos
    thread = context.get('resident_help_thread') or []
    recent_user_messages = [msg.get('content', '') for msg in thread[-3:] if msg.get('role') == 'user']
    recent_user_messages.append(question)
    combined_question = " ".join(recent_user_messages).lower()
    
    month_reference = extract_month_reference(combined_question)
    
    if not month_reference:
        last_topic = extract_last_assistant_topic(thread)
        if last_topic and last_topic.get('month_reference'):
            month_reference = last_topic['month_reference']

    lines = [
        f"Residente: {current_user.full_name or current_user.username}",
        f"Balance actual: {format_currency(totals.get('balance'))}",
        f"Pagos registrados: {format_currency(totals.get('total_paid'))}",
        f"Facturas pendientes: {int(totals.get('pending_invoices') or 0)}",
        f"Unidades vinculadas: {int(totals.get('apartments') or 0)}",
    ]

    resident_units = context.get('resident_units') or []
    if resident_units:
        lines.append('Resumen por unidad:')
        for unit in resident_units[:4]:
            apartment_number = unit.get('apartment_number') or unit.get('unit_id') or 'N/D'
            lines.append(
                f"- Apto {apartment_number}: balance {format_currency(unit.get('balance'))}, "
                f"pagado {format_currency(unit.get('total_paid'))}, "
                f"facturas pendientes {int(unit.get('pending_invoices') or 0)}"
            )

    if pending_preview:
        lines.append('Facturas pendientes recientes:')
        for invoice in pending_preview[:3]:
            lines.append(
                f"- {invoice.get('description') or 'Factura'} | Apto {invoice.get('apartment_number') or invoice.get('unit_id') or 'N/D'} | "
                f"Monto {format_currency(invoice.get('remaining') or invoice.get('amount'))} | "
                f"Vence {invoice.get('due_date') or 'sin fecha'}"
            )

    if report_months:
        lines.append("Reportes historicos disponibles: " + ", ".join(month['label'] for month in report_months[:4]))

    if month_reference:
        try:
            reference_dt = datetime.strptime(month_reference['reference_date'], '%Y-%m-%d')
            report_data = financial_reports.get_monthly_financial_report_data(
                reference_dt=reference_dt, period_mode='previous_month',
            )
            lines.append(
                f"Reporte consultado {month_reference['label']}: "
                f"Ingresos Operacionales {format_currency(report_data.get('total_collections'))}, "
                f"Otros Ingresos {format_currency(report_data.get('other_income', 0))}, "
                f"Gastos Operacionales {format_currency(report_data.get('total_expenses'))}, "
                f"Otros Gastos {format_currency(report_data.get('other_expenses', 0))}, "
                f"Balance de cierre {format_currency(report_data.get('closing_balance'))}."
            )
            
            expenses_summary = report_data.get('operating_expenses_detail', [])
            if expenses_summary:
                lines.append(f"Resumen de Gastos por Categoría ({month_reference['label']}):")
                for cat in expenses_summary:
                    lines.append(
                        f"  - {cat.get('category') or 'Gasto'}: {format_currency(cat.get('total') or 0)}"
                    )
                    
            expenses = report_data.get('expenses', [])
            if expenses:
                lines.append(f"Detalle individual de Gastos Operacionales ({month_reference['label']}):")
                for exp in expenses:
                    lines.append(
                        f"  - {exp.get('category') or 'Gasto'}: {exp.get('description') or ''} "
                        f"({format_currency(exp.get('amount') or 0)})"
                    )
            
            other_expenses = report_data.get('other_expenses_detail', [])
            if other_expenses:
                lines.append(f"Detalle de Otros Gastos ({month_reference['label']}):")
                for exp in other_expenses:
                    lines.append(
                        f"  - {exp.get('category') or 'Gasto'}: {format_currency(exp.get('total') or exp.get('amount') or 0)}"
                    )
        except Exception as exc:
            current_app.logger.warning(f"No se pudo preparar contexto de reporte para residente: {exc}")

    if question_has_any(combined_question, ['por mes', 'meses', 'acumulado', 'historico', 'tabla']):
        lines.append("\n--- DATOS HISTÓRICOS (Últimos 6 meses disponibles) ---")
        for r_month in report_months[:6]:
            try:
                ref_dt = datetime.strptime(r_month['ref_date'], '%Y-%m-%d')
                r_data = financial_reports.get_monthly_financial_report_data(
                    reference_dt=ref_dt, period_mode='previous_month',
                )
                lines.append(f"Resumen de {r_month['label']}:")
                exp_summary = r_data.get('operating_expenses_detail', [])
                if exp_summary:
                    for cat in exp_summary:
                        lines.append(f"  - Categoria '{cat.get('category')}': {format_currency(cat.get('total') or 0)}")
                
                exp_indiv = r_data.get('expenses', [])
                if exp_indiv:
                    lines.append(f"Detalle de {r_month['label']}:")
                    for exp in exp_indiv:
                        lines.append(f"  - {exp.get('description') or exp.get('category')}: {format_currency(exp.get('amount') or 0)}")
            except Exception as e:
                current_app.logger.warning(f"Error cargando historico de {r_month}: {e}")
        lines.append("--------------------------------------------------\n")

    if company_info:
        contact_chunks = []
        if company_info.get('name'):
            contact_chunks.append(f"Contacto: {company_info['name']}")
        if company_info.get('phone'):
            contact_chunks.append(f"Telefono: {company_info['phone']}")
        if company_info.get('email'):
            contact_chunks.append(f"Correo: {company_info['email']}")
        if contact_chunks:
            lines.append(' | '.join(contact_chunks))

    if deterministic_answer:
        lines.append('Respuesta validada por las reglas actuales del portal:')
        lines.append(f"- Titulo: {deterministic_answer.get('title') or 'Sin titulo'}")
        lines.append(f"- Cuerpo: {deterministic_answer.get('body') or ''}")
        if deterministic_answer.get('detail'):
            lines.append(f"- Detalle: {deterministic_answer['detail']}")

    return "\n".join(lines)


def _build_ai_answer(
    question: str,
    context: dict,
    thread: list[dict[str, str]],
    deterministic_answer: Optional[dict],
) -> Optional[dict]:
    if not ai_enabled():
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        current_app.logger.error("google-generativeai is not installed")
        return None

    cfg = current_app.config
    genai.configure(api_key=cfg['RESIDENT_AI_API_KEY'])
    
    context_block = _build_ai_context_text(question, context, deterministic_answer)
    system_instruction = (
        'Eres el asistente virtual del portal residencial Toscana. Tu nombre es "Asistente Toscana". '
        'REGLAS ESTRICTAS:\n'
        '1. Responde SOLO con la información proporcionada en el contexto. NUNCA inventes datos ni montos.\n'
        '2. Sé conversacional y amable, como un chat de WhatsApp. Usa Markdown: **negritas**, listas con -, tablas con |\n'
        '3. NO uses títulos formales como "Respuesta del asistente". Sé natural y directo.\n'
        '4. Cuando te pidan desglose o detalle, usa los datos de gastos/cobros del contexto para listarlos en tablas si es apropiado.\n'
        '5. Si te piden un GRÁFICO (de tendencia, distribución, etc), DEBES usar código Mermaid. Envuelve el código en un bloque ```mermaid ... ```. Usa "pie" para distribución y "xychart-beta" para tendencias.\n'
        '6. Si la pregunta es un seguimiento ("y esos?", "dame más", "explícame"), referénciate al mensaje anterior.\n'
        '7. Si NO tienes la información para responder, dilo claramente y sugiere contactar a la administración.\n'
        '8. Responde en español dominicano formal pero cercano. Máximo 6 frases a menos que listen datos o gráficos.\n\n'
        f'CONTEXTO VERIFICADO DEL RESIDENTE:\n{context_block}'
    )

    try:
        # Usamos el modelo Gemini
        model_name = cfg.get('RESIDENT_AI_MODEL') or 'gemini-2.5-flash'
        if 'gpt' in model_name: 
            model_name = 'gemini-2.5-flash' # fallback if the env still has gpt-4
            
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        
        # Construir historial de chat para Gemini
        history = []
        for item in thread:
            role = 'model' if item.get('role') == 'assistant' else 'user'
            content_parts = []
            if role == 'model' and item.get('title'):
                content_parts.append(item['title'])
            if item.get('content'):
                content_parts.append(item['content'])
            if item.get('detail'):
                content_parts.append(item['detail'])
            
            content = "\n".join(content_parts).strip()
            if content:
                history.append({"role": role, "parts": [content]})
                
        chat = model.start_chat(history=history)
        response = chat.send_message(question)
        
        ai_text = sanitize_help_text(response.text, 4000)
        if not ai_text:
            return None
            
    except Exception as exc:
        current_app.logger.warning(f"Asistente IA residente (Gemini) falló: {exc}")
        return None

    answer_title = 'Respuesta del asistente Toscana IA'
    if deterministic_answer and deterministic_answer.get('title') != 'Pregunta lista para responderse':
        answer_title = deterministic_answer.get('title') or answer_title

    answer_detail = 'Respuesta generada con IA usando tu contexto validado y los reportes publicados.'
    if deterministic_answer and deterministic_answer.get('detail'):
        answer_detail = deterministic_answer['detail']

    return {
        'source': 'ai',
        'tone': (deterministic_answer or {}).get('tone') or 'primary',
        'title': answer_title,
        'body': ai_text,
        'detail': answer_detail,
        'link_url': (deterministic_answer or {}).get('link_url'),
        'link_label': (deterministic_answer or {}).get('link_label'),
    }


def compose_help_answer(question: str, context: dict, thread: list[dict[str, str]]) -> Optional[dict]:
    deterministic_answer = build_help_answer(question, context, thread=thread)
    ai_answer = _build_ai_answer(question, context, thread, deterministic_answer)
    return ai_answer or deterministic_answer


def help_answer_to_message(answer: Optional[dict]) -> Optional[dict[str, str]]:
    if not answer:
        return None
    return serialize_help_message({
        'role': 'assistant',
        'title': answer.get('title'),
        'content': answer.get('body'),
        'detail': answer.get('detail'),
        'tone': answer.get('tone'),
        'source': answer.get('source') or 'rules',
        'link_url': answer.get('link_url'),
        'link_label': answer.get('link_label'),
    })


# ──────────────────────────────────────────────
# Contexto para las páginas del portal
# ──────────────────────────────────────────────

def build_report_months() -> list[dict]:
    """Genera el histórico de reportes mensuales completos visibles para residentes."""
    from datetime import datetime

    months = []
    now = datetime.now()
    oldest_date_str = None
    try:
        with db.get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT MIN(issued_date) FROM invoices")
            min_inv = cur.fetchone()[0]
            cur.execute("SELECT MIN(paid_date) FROM payments")
            min_pay = cur.fetchone()[0]

        dates = []
        if min_inv:
            dates.append(min_inv[:7])
        if min_pay:
            dates.append(min_pay[:7])
        if dates:
            oldest_date_str = min(dates)
    except Exception as e:
        current_app.logger.error(f"Error finding start of operations for reports list: {e}")

    for offset in range(1, 7):
        month_value = now.month - offset
        year_value = now.year
        while month_value <= 0:
            month_value += 12
            year_value -= 1

        month_key = f"{year_value}-{month_value:02d}"
        if oldest_date_str and month_key < oldest_date_str:
            continue

        reference_year = year_value
        reference_month = month_value + 1
        if reference_month == 13:
            reference_month = 1
            reference_year += 1

        months.append({
            'label': f"{MONTH_NAMES[month_value]} {year_value}",
            'ref_date': f"{reference_year}-{reference_month:02d}-01",
            'period_key': month_key,
        })

    return months


def get_common_context() -> dict:
    linked_apartments = residents.list_linked_apartments_for_user(
        current_user.id, fallback_email=current_user.email,
    )
    resident_summary = residents.get_resident_statement_summary_for_user(
        current_user.id, fallback_email=current_user.email,
    )
    return {
        'apartments': linked_apartments,
        'resident_summary': resident_summary,
        'resident_totals': resident_summary['totals'],
        'resident_units': resident_summary['apartments'],
        'company_info': company.get_company_info() or {},
        'report_months': build_report_months(),
    }


def build_balances_context() -> dict:
    context = get_common_context()
    context.update({
        'pending_preview': residents.list_resident_invoices_for_user(
            current_user.id, fallback_email=current_user.email,
            paid=False, limit=4,
        ),
    })
    return context


def build_evolution_context() -> dict:
    from datetime import datetime

    context = get_common_context()
    invoices = residents.list_resident_invoices_for_user(
        current_user.id, fallback_email=current_user.email,
    )
    payment_history: dict[str, Any] = residents.get_resident_payment_history_for_user(
        current_user.id, fallback_email=current_user.email, limit=None,
    )
    payment_items = list(payment_history.get('items') or [])

    trend_keys = []
    trend_labels = []
    trend_invoiced = {}
    trend_paid = {}
    now = datetime.now()

    for offset in range(5, -1, -1):
        month_value = now.month - offset
        year_value = now.year
        while month_value <= 0:
            month_value += 12
            year_value -= 1
        key = f"{year_value}-{month_value:02d}"
        trend_keys.append(key)
        trend_labels.append(f"{MONTH_SHORT_NAMES[month_value]} {year_value}")
        trend_invoiced[key] = 0.0
        trend_paid[key] = 0.0

    for invoice in invoices:
        month_key = (invoice.get('issued_date') or '')[:7]
        if month_key in trend_invoiced:
            trend_invoiced[month_key] += float(invoice.get('amount') or 0)

    for payment in payment_items:
        month_key = (payment.get('paid_date') or '')[:7]
        if month_key in trend_paid:
            trend_paid[month_key] += float(payment.get('amount') or 0)

    context.update({
        'trend_labels': trend_labels,
        'trend_invoiced_values': [trend_invoiced[key] for key in trend_keys],
        'trend_paid_values': [trend_paid[key] for key in trend_keys],
        'status_distribution_labels': ['Pendiente', 'Pagado'],
        'status_distribution_values': [
            float(context['resident_totals'].get('balance') or 0),
            float(context['resident_totals'].get('total_paid') or 0),
        ],
        'unit_balance_labels': [
            f"Apto {unit.get('apartment_number') or unit.get('unit_id')}" for unit in context['resident_units']
        ],
        'unit_balance_values': [float(unit.get('balance') or 0) for unit in context['resident_units']],
        'unit_paid_values': [float(unit.get('total_paid') or 0) for unit in context['resident_units']],
        'has_financial_activity': bool(invoices or payment_items),
    })
    return context


def build_billing_context() -> dict:
    context = get_common_context()
    page = max(request.args.get('page', type=int) or 1, 1)
    page_size = 6
    method_filter = (request.args.get('method') or '').strip()
    month_filter = (request.args.get('month') or '').strip()

    payment_history: dict[str, Any] = residents.get_resident_payment_history_for_user(
        current_user.id, fallback_email=current_user.email,
        method=method_filter or None, month=month_filter or None,
        limit=page_size, offset=(page - 1) * page_size,
    )
    payment_items = list(payment_history.get('items') or [])
    payment_total = int(payment_history.get('total') or 0)
    payment_methods = list(payment_history.get('methods') or [])
    payment_months = list(payment_history.get('months') or [])
    total_pages = max(1, (payment_total + page_size - 1) // page_size) if payment_total else 1

    context.update({
        'pending_invoices': residents.list_resident_invoices_for_user(
            current_user.id, fallback_email=current_user.email, paid=False,
        ),
        'payments_history': payment_items,
        'payments_total': payment_total,
        'payments_page': page,
        'payments_total_pages': total_pages,
        'payments_has_prev': page > 1,
        'payments_has_next': page < total_pages,
        'payment_filter_method': method_filter,
        'payment_filter_month': month_filter,
        'payment_filter_methods': payment_methods,
        'payment_filter_months': [format_month_option(mk) for mk in payment_months],
    })
    return context


def build_reports_context() -> dict:
    from datetime import datetime

    context = get_common_context()
    context.update({
        'current_report_url': url_for(
            'reports.monthly_view_html',
            reference_date=datetime.now().strftime('%Y-%m-%d'),
            period_mode='current_month_to_date',
        ),
        'report_months': build_report_months(),
    })
    return context


def build_help_context(question: str = '', thread: Optional[list[dict[str, str]]] = None) -> dict:
    context = get_common_context()
    resident_help_thread = thread if thread is not None else get_help_thread()
    _ai_enabled = ai_enabled()
    recent_payment_history: dict[str, Any] = residents.get_resident_payment_history_for_user(
        current_user.id, fallback_email=current_user.email, limit=3,
    )
    latest_answer = next(
        (message for message in reversed(resident_help_thread) if message.get('role') == 'assistant'),
        None,
    )
    context.update({
        'pending_preview': residents.list_resident_invoices_for_user(
            current_user.id, fallback_email=current_user.email,
            paid=False, limit=3,
        ),
        'recent_payments': list(recent_payment_history.get('items') or []),
        'resident_help_question': question,
        'resident_help_answer': latest_answer,
        'resident_help_thread': resident_help_thread,
        'resident_ai_enabled': _ai_enabled,
        'resident_ai_status_label': 'IA conectada' if _ai_enabled else 'Asistente guiado',
        'resident_ai_status_detail': (
            'Usa un modelo externo con contexto validado del portal y reportes publicados.'
            if _ai_enabled
            else 'Responde con logica del portal y datos verificados hasta que configures la IA externa.'
        ),
        'resident_help_suggestions_label': 'Ejemplos de preguntas' if _ai_enabled else 'Ejemplos que el portal ya responde bien',
        'resident_help_suggestions_hint': (
            'Puedes escribir cualquier pregunta sobre tu cuenta o los reportes; estas tarjetas son solo ideas.'
            if _ai_enabled
            else 'Ahora mismo estas sugerencias coinciden con las categorias soportadas sin IA externa.'
        ),
        'resident_help_suggestions': (
            [
                'Explicame mi balance actual.',
                'Resumeme mis pagos mas recientes.',
                'Tengo deuda activa este mes?',
                'Que dice el ultimo reporte del residencial?',
                'Como contacto a la administracion?',
                'Donde cambio mi foto o mi clave?',
            ]
            if _ai_enabled
            else [
                'Donde puedo actualizar mi foto de perfil?',
                'Cuantas facturas pendientes tengo?',
                'Cual es mi saldo actual?',
                'Cuales fueron los gastos de abril 2026?',
                'Cual fue el balance del reporte de mayo 2026?',
                'Como contacto a la administracion?',
            ]
        ),
    })
    return context


def render_resident_page(template_name: str, section: str, section_context: dict):
    context = dict(section_context)
    context['resident_active_section'] = section
    return render_template(template_name, **context)
