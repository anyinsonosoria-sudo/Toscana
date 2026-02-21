"""
Blueprint para Reportes (Reports)
Análisis financiero y cuentas por cobrar
"""
import logging
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required

from utils.decorators import permission_required
from extensions import cache
import reports
import customization

logger = logging.getLogger(__name__)

reports_bp = Blueprint('reports', __name__, url_prefix='/reportes')


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
                         customization=custom_settings)


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
