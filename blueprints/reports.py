"""
Blueprint para Reportes (Reports)
Análisis financiero y cuentas por cobrar
"""
import logging
from datetime import datetime
from pathlib import Path

from flask import Blueprint, render_template, request, jsonify, send_file, flash, redirect, url_for
from flask_login import login_required, current_user

from utils.decorators import permission_required, admin_required, audit_log
from extensions import cache
import reports
import customization
from company import get_company_info
from senders import generate_monthly_financial_report_html

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/reportes')


def _parse_reference_date(raw_value: str):
    raw_value = (raw_value or '').strip()
    if not raw_value:
        return None

    try:
        return datetime.strptime(raw_value, '%Y-%m-%d')
    except ValueError:
        return None


def _resolve_period_mode(raw_value: str) -> str:
    period_mode = (raw_value or 'previous_month').strip().lower()
    if period_mode not in {'previous_month', 'current_month_to_date'}:
        return 'previous_month'
    return period_mode


def _resolve_preview_request(raw_reference_date: str, raw_period_mode: str):
    period_mode = _resolve_period_mode(raw_period_mode)
    reference_dt = _parse_reference_date(raw_reference_date)

    if raw_reference_date and reference_dt is None:
        reference_dt = datetime.now()
        selected_reference_date = reference_dt.strftime('%Y-%m-%d')
        if period_mode == 'current_month_to_date':
            date_error = 'La fecha indicada no es válida. Se mostró el mes actual a la fecha de hoy.'
        else:
            date_error = 'La fecha indicada no es válida. Se mostró el mes anterior a la fecha actual.'
    else:
        reference_dt = reference_dt or datetime.now()
        selected_reference_date = reference_dt.strftime('%Y-%m-%d')
        date_error = None

    return reference_dt, selected_reference_date, period_mode, date_error


@reports_bp.route('/')
@login_required
@permission_required('reportes.view')
@cache.cached(timeout=60, query_string=True)
def list():
    """Vista principal de reportes y análisis"""
    try:
        # Obtener parámetros de filtro
        top_clients_metric = request.args.get('top_clients_metric', 'sales')
        receivable_filter = request.args.get('receivable_filter', 'all')
        
        # Resumen financiero
        summary = reports.get_financial_summary()
        
        # Ventas por período
        sales_by_period = reports.get_sales_by_period('month')
        
        # Clientes principales
        sales_by_client = reports.get_sales_by_client(limit=15)
        
        # Servicios más vendidos
        sales_by_service = reports.get_sales_by_service(limit=15)
        
        # Cuentas por cobrar
        if receivable_filter == 'all':
            accounts_receivable = reports.get_accounts_receivable()
        elif receivable_filter == '30':
            accounts_receivable = reports.get_overdue_accounts(days=30)
        elif receivable_filter == '60':
            accounts_receivable = reports.get_overdue_accounts(days=60)
        elif receivable_filter == '90':
            accounts_receivable = reports.get_overdue_accounts(days=90)
        else:
            accounts_receivable = reports.get_accounts_receivable()
        
        # Calcular montos de cuentas vencidas (usar balance real, no total factura)
        overdue_30 = sum([inv.get('balance', inv.get('total', 0)) for inv in reports.get_overdue_accounts(days=30)])
        overdue_60 = sum([inv.get('balance', inv.get('total', 0)) for inv in reports.get_overdue_accounts(days=60)])
        overdue_90 = sum([inv.get('balance', inv.get('total', 0)) for inv in reports.get_overdue_accounts(days=90)])
        
    except Exception as e:
        logger.error(f"Error in reports.list: {e}")
        summary = {}
        sales_by_period = []
        sales_by_client = []
        sales_by_service = []
        accounts_receivable = []
        overdue_30 = 0
        overdue_60 = 0
        overdue_90 = 0
    
    # Get customization settings
    try:
        custom_settings = customization.get_settings_with_defaults()
    except:
        custom_settings = {}
    
    return render_template("reports.html",
                         summary=summary,
                         sales_by_period=sales_by_period,
                         sales_by_client=sales_by_client,
                         sales_by_service=sales_by_service,
                         accounts_receivable=accounts_receivable,
                         overdue_30=overdue_30,
                         overdue_60=overdue_60,
                         overdue_90=overdue_90,
                         monthly_preview_reference_date=datetime.now().strftime('%Y-%m-%d'),
                         customization=custom_settings)


@reports_bp.route('/mensual/preview')
@login_required
@permission_required('reportes.view')
def monthly_preview():
    """Vista previa web del reporte financiero mensual."""
    raw_reference_date = request.args.get('reference_date', '')
    reference_dt, selected_reference_date, period_mode, date_error = _resolve_preview_request(
        raw_reference_date,
        request.args.get('period_mode'),
    )

    report_data = reports.get_monthly_financial_report_data(
        reference_dt=reference_dt,
        period_mode=period_mode,
    )
    company_info = get_company_info() or {}
    recipients = reports.get_monthly_report_recipients()
    email_html = generate_monthly_financial_report_html(
        report_data,
        recipient_name=company_info.get('name') or 'Administración',
        recipient_type='admin',
        company_name=company_info.get('name'),
    )

    return render_template(
        'monthly_report_preview.html',
        report_data=report_data,
        company_info=company_info,
        recipients=recipients,
        email_html=email_html,
        selected_reference_date=selected_reference_date,
        selected_period_mode=period_mode,
        date_error=date_error,
        pdf_preview_url=(
            f"/reportes/mensual/preview.pdf?reference_date={selected_reference_date}"
            f"&period_mode={period_mode}"
        ),
    )


@reports_bp.route('/mensual/send', methods=['POST'])
@login_required
@admin_required
@audit_log('reportes.enviar_mensual', 'Enviar reporte financiero mensual manualmente')
def monthly_send():
    """Permite al administrador disparar manualmente el envío del reporte mensual."""
    raw_reference_date = request.form.get('reference_date', '')
    send_scope = (request.form.get('send_scope') or 'residents').strip().lower()
    reference_dt, selected_reference_date, period_mode, date_error = _resolve_preview_request(
        raw_reference_date,
        request.form.get('period_mode'),
    )

    if date_error:
        flash(date_error, 'warning')

    try:
        admin_only = send_scope == 'admin'
        result = reports.dispatch_monthly_financial_report(
            reference_dt=reference_dt,
            allow_retry_failed=True,
            period_mode=period_mode,
            admin_only=admin_only,
        )
        summary = result.get('summary') or reports.build_monthly_report_dispatch_summary(result)
        flash(summary['message'], summary['category'])
        if summary.get('detail'):
            flash(summary['detail'], summary['category'])
    except Exception as exc:
        logger.exception('Error enviando reporte financiero mensual manual: %s', exc)
        flash(f'Error al enviar el reporte financiero mensual: {exc}', 'error')

    return redirect(
        url_for(
            'reports.monthly_preview',
            reference_date=selected_reference_date,
            period_mode=period_mode,
        )
    )


@reports_bp.route('/mensual/preview.pdf')
@login_required
def monthly_preview_pdf():
    """Genera y devuelve el PDF de vista previa del reporte financiero mensual."""
    # Permitir a residentes o usuarios con el permiso correspondiente
    if current_user.role != 'resident':
        from utils.permissions import check_permission
        if not check_permission(current_user.id, 'reportes.view', current_user.role):
            flash("No tienes permiso para ver este reporte", "warning")
            abort(403)

    reference_dt = _parse_reference_date(request.args.get('reference_date')) or datetime.now()
    period_mode = _resolve_period_mode(request.args.get('period_mode'))
    report_data = reports.get_monthly_financial_report_data(
        reference_dt=reference_dt,
        period_mode=period_mode,
    )
    company_info = get_company_info() or {}

    preview_dir = Path(reports.__file__).resolve().parent / 'static' / 'reports'
    preview_filename = f"monthly_financial_report_preview_{report_data['report_period']}.pdf"
    pdf_path = reports.generate_monthly_financial_report_pdf_file(
        report_data,
        company_info,
        output_path=str(preview_dir / preview_filename),
    )

    return send_file(
        pdf_path,
        mimetype='application/pdf',
        as_attachment=False,
        download_name=preview_filename,
    )


# ========== API ENDPOINTS ==========

@reports_bp.route('/api/sales-by-period')
@login_required
@permission_required('reportes.view')
@cache.cached(timeout=60, query_string=True)
def api_sales_by_period():
    """API para obtener ventas por período"""
    period = request.args.get('period', 'month')
    data = reports.get_sales_by_period(period)
    return jsonify(data)


@reports_bp.route('/api/accounts-receivable')
@login_required
@permission_required('reportes.view')
@cache.cached(timeout=60, query_string=True)
def api_accounts_receivable():
    """API para obtener cuentas por cobrar"""
    filter_type = request.args.get('filter', 'all')
    if filter_type == 'all':
        data = reports.get_accounts_receivable()
    elif filter_type == 'overdue':
        days = request.args.get('days', 30, type=int)
        data = reports.get_overdue_accounts(days=days)
    else:
        data = reports.get_accounts_receivable()
    return jsonify(data)


@reports_bp.route('/api/financial-summary')
@login_required
@permission_required('reportes.view')
@cache.cached(timeout=60, query_string=True)
def api_financial_summary():
    """API para obtener resumen financiero"""
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    data = reports.get_financial_summary(date_from, date_to)
    return jsonify(data)
