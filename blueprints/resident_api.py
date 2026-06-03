import logging
from typing import Optional

from flask import Blueprint, jsonify, request, url_for, g
from flask_login import current_user

import models
import residents
import resident_auth
import user_model
from blueprints import billing
from extensions import csrf, limiter


logger = logging.getLogger(__name__)

resident_api_bp = Blueprint('resident_api', __name__, url_prefix='/api/resident')
PUBLIC_ENDPOINTS = {'resident_api.auth_login', 'resident_api.auth_refresh'}


def _json_error(message: str, status_code: int):
    return jsonify({'success': False, 'error': message}), status_code


def _is_truthy(value) -> bool:
    return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}


def _get_request_user():
    api_user = getattr(g, 'resident_api_user', None)
    if api_user is not None:
        return api_user
    if current_user.is_authenticated:
        return current_user
    return None


def _extract_bearer_token() -> Optional[str]:
    auth_header = request.headers.get('Authorization', '').strip()
    if not auth_header:
        return None
    scheme, _, token = auth_header.partition(' ')
    if scheme.lower() != 'bearer' or not token:
        return None
    return token.strip()


def _get_allowed_unit_ids(include_invited: bool = False, user=None):
    request_user = user or _get_request_user()
    if request_user is None:
        return set()
    return residents.get_allowed_unit_ids_for_user(
        request_user.id,
        fallback_email=request_user.email,
        include_invited=include_invited,
    )


def _build_profile_payload(user=None) -> dict:
    request_user = user or _get_request_user()
    linked_apartments = residents.list_linked_apartments_for_user(
        request_user.id,
        fallback_email=request_user.email,
        include_invited=True,
    )
    pending_invitations = residents.list_pending_invitations_for_user(request_user.id)
    return {
        'id': request_user.id,
        'username': request_user.username,
        'email': request_user.email,
        'full_name': request_user.full_name,
        'phone': getattr(request_user, 'phone', None),
        'role': request_user.role,
        'apartment_count': len(linked_apartments),
        'pending_invitation_count': len(pending_invitations),
    }


def _serialize_apartment(apartment: dict) -> dict:
    payload = {
        'id': apartment.get('id'),
        'number': apartment.get('number'),
        'resident_name': apartment.get('resident_name'),
        'resident_email': apartment.get('resident_email'),
        'resident_phone': apartment.get('resident_phone'),
        'floor': apartment.get('floor'),
        'notes': apartment.get('notes'),
        'status': apartment.get('status', 'active'),
        'is_primary': bool(apartment.get('is_primary')),
    }
    if payload['status'] == 'active':
        payload['statement_pdf_url'] = url_for('resident_api.statement_pdf', unit_id=payload['id'])
    return payload


def _serialize_invitation(invitation: dict) -> dict:
    return {
        'unit_id': invitation.get('unit_id'),
        'apartment_number': invitation.get('apartment_number'),
        'resident_name': invitation.get('resident_name'),
        'resident_email': invitation.get('resident_email'),
        'status': invitation.get('status'),
        'invitation_code': invitation.get('invitation_code'),
        'invited_at': invitation.get('invited_at'),
        'is_primary': bool(invitation.get('is_primary')),
    }


def _serialize_invoice(invoice: dict) -> dict:
    return {
        'id': invoice.get('id'),
        'unit_id': invoice.get('unit_id'),
        'apartment_number': invoice.get('apartment_number'),
        'description': invoice.get('description'),
        'amount': invoice.get('amount'),
        'issued_date': invoice.get('issued_date'),
        'due_date': invoice.get('due_date'),
        'paid': bool(invoice.get('paid')),
        'total_paid': invoice.get('total_paid'),
        'remaining': invoice.get('remaining'),
        'pdf_url': url_for('resident_api.invoice_pdf', invoice_id=invoice.get('id')),
    }


def _serialize_payment(payment: dict) -> dict:
    return {
        'id': payment.get('id'),
        'invoice_id': payment.get('invoice_id'),
        'invoice_desc': payment.get('invoice_desc'),
        'invoice_total': payment.get('invoice_total'),
        'apartment_number': payment.get('apt_number'),
        'amount': payment.get('amount'),
        'paid_date': payment.get('paid_date'),
        'method': payment.get('method'),
        'notes': payment.get('notes'),
        'receipt_url': url_for('billing.view_receipt_pdf', payment_id=payment.get('id')),
    }


@resident_api_bp.before_request
def require_authenticated_resident():
    if request.endpoint in PUBLIC_ENDPOINTS:
        return None

    if current_user.is_authenticated:
        if current_user.role != 'resident':
            return _json_error('Acceso solo para residentes', 403)
        g.resident_api_user = current_user
        return None

    token = _extract_bearer_token()
    if not token:
        return _json_error('Autenticacion requerida', 401)

    try:
        user, _ = resident_auth.get_user_from_token(token, expected_type='access', required_role='resident')
    except resident_auth.ResidentTokenExpiredError as exc:
        return _json_error(str(exc), 401)
    except resident_auth.ResidentTokenError as exc:
        return _json_error(str(exc), 401)

    g.resident_api_user = user
    return None


@resident_api_bp.route('/auth/login', methods=['POST'])
@csrf.exempt
@limiter.limit('10 per minute')
def auth_login():
    payload = request.get_json(silent=True) or request.form
    identifier = (
        payload.get('identifier')
        or payload.get('username')
        or payload.get('email')
        or ''
    ).strip()
    password = payload.get('password', '')

    if not identifier or not password:
        return _json_error('Usuario/email y contrasena requeridos', 400)

    user = user_model.get_user_by_username(identifier) or user_model.get_user_by_email(identifier)
    if not user or not user.check_password(password):
        return _json_error('Credenciales invalidas', 401)
    if not user.is_active:
        return _json_error('Usuario desactivado', 403)
    if user.role != 'resident':
        return _json_error('Acceso solo para residentes', 403)

    user_model.update_last_login(user.id)
    g.resident_api_user = user

    summary = residents.get_resident_statement_summary_for_user(
        user.id,
        fallback_email=user.email,
    )
    return jsonify({
        'success': True,
        'tokens': resident_auth.issue_token_pair(user),
        'profile': _build_profile_payload(user),
        'totals': summary['totals'],
    })


@resident_api_bp.route('/auth/refresh', methods=['POST'])
@csrf.exempt
@limiter.limit('30 per hour')
def auth_refresh():
    payload = request.get_json(silent=True) or request.form
    refresh_token = (payload.get('refresh_token') or _extract_bearer_token() or '').strip()
    if not refresh_token:
        return _json_error('Refresh token requerido', 400)

    try:
        user, refresh_payload = resident_auth.get_user_from_token(
            refresh_token,
            expected_type='refresh',
            required_role='resident',
            require_active_refresh=True,
        )
    except resident_auth.ResidentTokenExpiredError as exc:
        return _json_error(str(exc), 401)
    except resident_auth.ResidentTokenError as exc:
        return _json_error(str(exc), 401)

    return jsonify({
        'success': True,
        'tokens': resident_auth.issue_token_pair(user, rotate_from_refresh_jti=refresh_payload['jti']),
    })


@resident_api_bp.route('/auth/logout', methods=['POST'])
@csrf.exempt
def auth_logout():
    request_user = _get_request_user()
    payload = request.get_json(silent=True) or request.form
    refresh_token = (payload.get('refresh_token') or '').strip()
    revoke_all = _is_truthy(payload.get('all_sessions') or payload.get('all_devices'))

    if not refresh_token and not revoke_all:
        return _json_error('Refresh token requerido o all_sessions=true', 400)

    revoked_tokens = 0

    if refresh_token:
        try:
            revoked_tokens += resident_auth.revoke_refresh_token(refresh_token, user_id=request_user.id)
        except resident_auth.ResidentTokenError as exc:
            return _json_error(str(exc), 400)

    if revoke_all:
        revoked_tokens += resident_auth.revoke_all_refresh_tokens_for_user(request_user.id)

    return jsonify({
        'success': True,
        'revoked_tokens': revoked_tokens,
    })


@resident_api_bp.route('/profile', methods=['GET'])
def profile():
    request_user = _get_request_user()
    summary = residents.get_resident_statement_summary_for_user(
        request_user.id,
        fallback_email=request_user.email,
    )
    return jsonify({
        'success': True,
        'profile': _build_profile_payload(request_user),
        'totals': summary['totals'],
    })


@resident_api_bp.route('/apartments', methods=['GET'])
def apartments():
    request_user = _get_request_user()
    linked_apartments = residents.list_linked_apartments_for_user(
        request_user.id,
        fallback_email=request_user.email,
        include_invited=True,
    )
    return jsonify({
        'success': True,
        'apartments': [_serialize_apartment(apartment) for apartment in linked_apartments],
    })


@resident_api_bp.route('/invitations', methods=['GET'])
def invitations():
    request_user = _get_request_user()
    invitations = residents.list_pending_invitations_for_user(request_user.id)
    return jsonify({
        'success': True,
        'invitations': [_serialize_invitation(invitation) for invitation in invitations],
    })


@resident_api_bp.route('/invitations/activate', methods=['POST'])
@csrf.exempt
def activate_invitation():
    request_user = _get_request_user()
    payload = request.get_json(silent=True) or request.form
    invitation_code = (payload.get('invitation_code') or payload.get('code') or '').strip()
    if not invitation_code:
        return _json_error('Codigo de invitacion requerido', 400)

    try:
        apartment = residents.activate_resident_invitation(
            request_user.id,
            invitation_code,
            resident_email=request_user.email,
            resident_name=request_user.full_name or request_user.username,
        )
    except ValueError as exc:
        return _json_error(str(exc), 400)
    except Exception as exc:
        logger.error(f"Error activating resident invitation: {exc}")
        return _json_error('No se pudo activar la invitacion', 500)

    return jsonify({
        'success': True,
        'apartment': _serialize_apartment(apartment),
        'profile': _build_profile_payload(request_user),
    })


@resident_api_bp.route('/invoices', methods=['GET'])
def invoices():
    request_user = _get_request_user()
    status = (request.args.get('status') or 'all').strip().lower()
    paid_filter: Optional[bool]
    if status == 'all':
        paid_filter = None
    elif status == 'pending':
        paid_filter = False
    elif status == 'paid':
        paid_filter = True
    else:
        return _json_error('Parametro status invalido', 400)

    invoices = residents.list_resident_invoices_for_user(
        request_user.id,
        fallback_email=request_user.email,
        paid=paid_filter,
    )
    return jsonify({
        'success': True,
        'invoices': [_serialize_invoice(invoice) for invoice in invoices],
    })


@resident_api_bp.route('/payments', methods=['GET'])
def payments():
    request_user = _get_request_user()
    method = (request.args.get('method') or '').strip() or None
    month = (request.args.get('month') or '').strip() or None
    limit = request.args.get('limit', type=int)
    offset = request.args.get('offset', type=int) or 0

    if limit is not None and limit <= 0:
        return _json_error('Parametro limit invalido', 400)
    if offset < 0:
        return _json_error('Parametro offset invalido', 400)
    if month and len(month) != 7:
        return _json_error('Parametro month invalido', 400)

    payment_history = residents.get_resident_payment_history_for_user(
        request_user.id,
        fallback_email=request_user.email,
        method=method,
        month=month,
        limit=limit,
        offset=offset,
    )
    payments = list(payment_history.get('items') or [])
    total = int(payment_history.get('total') or 0)

    return jsonify({
        'success': True,
        'payments': [_serialize_payment(payment) for payment in payments],
        'pagination': {
            'limit': limit,
            'offset': offset,
            'returned': len(payments),
            'total': total,
            'has_more': offset + len(payments) < total,
        },
        'filters': {
            'applied': {
                'method': method,
                'month': month,
            },
            'methods': payment_history.get('methods') or [],
            'months': payment_history.get('months') or [],
        },
    })


@resident_api_bp.route('/statement-summary', methods=['GET'])
def statement_summary():
    request_user = _get_request_user()
    summary = residents.get_resident_statement_summary_for_user(
        request_user.id,
        fallback_email=request_user.email,
    )
    apartments = []
    for apartment in summary['apartments']:
        apartment_payload = dict(apartment)
        apartment_payload['statement_pdf_url'] = url_for('resident_api.statement_pdf', unit_id=apartment['unit_id'])
        apartments.append(apartment_payload)

    return jsonify({
        'success': True,
        'summary': {
            'apartments': apartments,
            'totals': summary['totals'],
        },
    })


@resident_api_bp.route('/invoices/<int:invoice_id>/pdf', methods=['GET'])
def invoice_pdf(invoice_id: int):
    request_user = _get_request_user()
    invoice = models.get_invoice_by_id(invoice_id)
    if not invoice:
        return _json_error('Factura no encontrada', 404)
    if invoice.get('unit_id') not in _get_allowed_unit_ids(user=request_user):
        return _json_error('Factura fuera de su alcance', 403)
    return getattr(billing.view_invoice_pdf, '__wrapped__', billing.view_invoice_pdf)(invoice_id)


@resident_api_bp.route('/apartments/<int:unit_id>/statement.pdf', methods=['GET'])
def statement_pdf(unit_id: int):
    request_user = _get_request_user()
    if unit_id not in _get_allowed_unit_ids(user=request_user):
        return _json_error('Apartamento fuera de su alcance', 403)
    return getattr(billing.download_statement_pdf, '__wrapped__', billing.download_statement_pdf)(unit_id)