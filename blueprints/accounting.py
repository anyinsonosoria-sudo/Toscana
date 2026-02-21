"""
Blueprint: Accounting
Manejo de transacciones contables (ingresos y egresos)
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from datetime import datetime

from utils.decorators import role_required, permission_required, audit_log
import accounting
import company as company_mod
import customization

logger = logging.getLogger(__name__)

# Crear blueprint
accounting_bp = Blueprint('accounting', __name__, url_prefix='/contabilidad')


@accounting_bp.route('/')
@login_required
@permission_required('contabilidad.view')
def list():
    """Vista principal de contabilidad"""
    try:
        balance = accounting.get_balance_summary()
        monthly_data = accounting.get_transactions_by_month()
        category_data = accounting.get_transactions_by_category()
        custom_settings = customization.get_settings_with_defaults()
    except Exception as e:
        logger.error(f"Error loading accounting: {e}")
        balance = {"total_income": 0, "total_expenses": 0, "balance": 0}
        monthly_data = []
        category_data = []
        custom_settings = {}
    
    return render_template("contabilidad.html",
                         balance=balance,
                         monthly_data=monthly_data,
                         category_data=category_data,
                         today=datetime.now().strftime("%Y-%m-%d"),
                         customization=custom_settings)


@accounting_bp.route('/add', methods=['POST'])
@login_required
@permission_required('contabilidad.create')
@audit_log('CREATE', 'Crear transacción contable')
def add():
    """Agregar nueva transacción contable"""
    transaction_type = request.form.get("type", "").strip()
    description = request.form.get("description", "").strip()
    
    try:
        amount = float(request.form.get("amount", 0))
    except Exception:
        flash("Monto válido requerido.", "error")
        return redirect(url_for("accounting.list"))
    
    if not transaction_type or transaction_type not in ["income", "expense"]:
        flash("Tipo de transacción válido requerido.", "error")
        return redirect(url_for("accounting.list"))
    
    if not description or amount <= 0:
        flash("Descripción y monto válido son requeridos.", "error")
        return redirect(url_for("accounting.list"))
    
    category = request.form.get("category", "").strip() or None
    reference = request.form.get("reference", "").strip() or None
    date = request.form.get("date", "").strip()
    notes = request.form.get("notes", "").strip() or None
    
    try:
        accounting.add_transaction(
            transaction_type, description, amount, 
            category, reference, date, notes
        )
        flash("Transacción registrada exitosamente.", "success")
    except Exception as e:
        flash(f"Error al registrar transacción: {e}", "error")
    
    return redirect(url_for("accounting.list"))


@accounting_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@permission_required('contabilidad.edit')
@audit_log('UPDATE', 'Editar transacción contable')
def edit(id):
    """Editar transacción existente"""
    transaction_type = request.form.get("type", "").strip()
    description = request.form.get("description", "").strip()
    
    try:
        amount = float(request.form.get("amount", 0))
    except Exception:
        flash("Monto válido requerido.", "error")
        return redirect(url_for("accounting.list"))
    
    category = request.form.get("category", "").strip() or None
    reference = request.form.get("reference", "").strip() or None
    date = request.form.get("date", "").strip()
    notes = request.form.get("notes", "").strip() or None
    
    try:
        accounting.update_transaction(
            id, type=transaction_type, description=description, 
            amount=amount, category=category, reference=reference,
            date=date, notes=notes
        )
        flash("Transacción actualizada exitosamente.", "success")
    except Exception as e:
        flash(f"Error al actualizar transacción: {e}", "error")
    
    return redirect(url_for("accounting.list"))


@accounting_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('contabilidad.delete')
@audit_log('DELETE', 'Eliminar transacción contable')
def delete(id):
    """Eliminar transacción"""
    try:
        accounting.delete_transaction(id)
        flash("Transacción eliminada exitosamente.", "success")
    except Exception as e:
        flash(f"Error al eliminar transacción: {e}", "error")
    
    return redirect(url_for("accounting.list"))


@accounting_bp.route('/estado-resultados')
@login_required
@permission_required('contabilidad.view')
def income_statement():
    """Estado de Resultados (Income Statement / P&L)"""
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        data = accounting.get_income_statement(date_from, date_to)
        company_info = company_mod.get_company_info()
        custom_settings = customization.get_settings_with_defaults()
    except Exception as e:
        logger.error(f"Error loading income statement: {e}")
        data = {'date_from': '', 'date_to': '', 'total_income': 0, 'total_expenses': 0,
                'operating_income': 0, 'operating_income_detail': [],
                'other_income': 0, 'other_income_detail': [],
                'operating_expenses': 0, 'operating_expenses_detail': [],
                'other_expenses': 0, 'other_expenses_detail': [],
                'gross_profit': 0, 'net_income': 0}
        company_info = {}
        custom_settings = {}
    
    return render_template("estado_resultados.html",
                         data=data,
                         company=company_info,
                         customization=custom_settings)


@accounting_bp.route('/flujo-efectivo')
@login_required
@permission_required('contabilidad.view')
def cash_flow():
    """Estado de Flujo de Efectivo (Cash Flow Statement)"""
    try:
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        data = accounting.get_cash_flow_statement(date_from, date_to)
        company_info = company_mod.get_company_info()
        custom_settings = customization.get_settings_with_defaults()
    except Exception as e:
        logger.error(f"Error loading cash flow statement: {e}")
        data = {'date_from': '', 'date_to': '', 'collections': 0, 'collections_by_month': [],
                'operational_payments': 0, 'expenses_by_month': [],
                'net_operating': 0, 'investing_inflows': 0, 'investing_outflows': 0,
                'net_investing': 0, 'financing_inflows': 0, 'financing_inflows_detail': [],
                'financing_outflows': 0, 'financing_outflows_detail': [],
                'net_financing': 0, 'opening_balance': 0, 'net_change': 0, 'closing_balance': 0}
        company_info = {}
        custom_settings = {}
    
    return render_template("flujo_efectivo.html",
                         data=data,
                         company=company_info,
                         customization=custom_settings)
