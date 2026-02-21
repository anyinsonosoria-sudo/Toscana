"""
Blueprint para Gastos (Expenses)
Gestion de gastos con OCR para recibos
"""
import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from datetime import datetime

from utils.decorators import permission_required, audit_log
from utils.pagination import paginate
from utils.file_validator import validate_upload_file, FileValidationError
from extensions import csrf
from extensions import cache
import expenses
import suppliers
import customization

logger = logging.getLogger(__name__)

expenses_bp = Blueprint('expenses', __name__, url_prefix='/gastos')


@expenses_bp.route('/')
@login_required
@permission_required('gastos.view')
@cache.cached(timeout=60, query_string=True)
def list():
    """Lista todos los gastos con paginación"""
    try:
        exp_list = expenses.list_expenses()
        suppliers_list = suppliers.list_suppliers()
        total = sum(e.get("amount", 0) for e in exp_list)
        custom_settings = customization.get_settings_with_defaults()
        
        # Paginar gastos
        pagination = paginate(exp_list, per_page=20)
        
    except Exception as e:
        logger.error(f"Error loading expenses: {e}")
        exp_list = []
        suppliers_list = []
        total = 0
        custom_settings = {}
        pagination = paginate([], per_page=20)
    
    return render_template("gastos.html", 
                         expenses=pagination.items,
                         pagination=pagination,
                         suppliers=suppliers_list,
                         total_expenses=total,
                         today=datetime.now().strftime("%Y-%m-%d"),
                         customization=custom_settings)


@expenses_bp.route('/add', methods=['POST'])
@login_required
@permission_required('gastos.create')
@audit_log('gastos.crear', 'Gasto registrado')
def add():
    """Agregar nuevo gasto"""
    description = request.form.get("description", "").strip()
    try:
        amount = float(request.form.get("amount", 0))
    except Exception:
        flash("Monto válido requerido.", "error")
        return redirect(url_for("expenses.list"))
    
    if not description or amount <= 0:
        flash("Descripción y monto válido son requeridos.", "error")
        return redirect(url_for("expenses.list"))
    
    category = request.form.get("category", "").strip() or None
    supplier_id = request.form.get("supplier_id", "").strip()
    supplier_id = int(supplier_id) if supplier_id else None
    date = request.form.get("date", "").strip()
    payment_method = request.form.get("payment_method", "").strip() or None
    notes = request.form.get("notes", "").strip() or None
    
    try:
        expenses.add_expense(description, amount, category, supplier_id, date, payment_method, notes)
        flash("Gasto registrado exitosamente.", "success")
        cache.clear()
    except Exception as e:
        flash(f"Error al registrar gasto: {e}", "error")
    
    return redirect(url_for("expenses.list"))


@expenses_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@permission_required('gastos.edit')
@audit_log('gastos.editar', 'Gasto actualizado')
def edit(id):
    """Editar gasto existente"""
    description = request.form.get("description", "").strip()
    try:
        amount = float(request.form.get("amount", 0))
    except Exception:
        flash("Monto válido requerido.", "error")
        return redirect(url_for("expenses.list"))
    
    category = request.form.get("category", "").strip() or None
    supplier_id = request.form.get("supplier_id", "").strip()
    supplier_id = int(supplier_id) if supplier_id else None
    date = request.form.get("date", "").strip()
    payment_method = request.form.get("payment_method", "").strip() or None
    notes = request.form.get("notes", "").strip() or None
    
    try:
        expenses.update_expense(id, description=description, amount=amount, 
                              category=category, supplier_id=supplier_id,
                              date=date, payment_method=payment_method, notes=notes)
        flash("Gasto actualizado exitosamente.", "success")
        cache.clear()
    except Exception as e:
        flash(f"Error al actualizar gasto: {e}", "error")
    
    return redirect(url_for("expenses.list"))


@expenses_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('gastos.delete')
@audit_log('gastos.eliminar', 'Gasto eliminado')
def delete(id):
    """Eliminar gasto"""
    try:
        expenses.delete_expense(id)
        flash("Gasto eliminado exitosamente.", "success")
        cache.clear()
    except Exception as e:
        flash(f"Error al eliminar gasto: {e}", "error")
    
    return redirect(url_for("expenses.list"))


@expenses_bp.route('/upload-recibo', methods=['POST'])
@login_required
@csrf.exempt
@permission_required('gastos.create')
def upload_receipt_ocr():
    """Carga imagen de recibo y extrae info con OCR"""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No se envio archivo", "success": False}), 400
        
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Archivo vacio", "success": False}), 400
        
        # Validacion segura del archivo (extension + magic bytes)
        try:
            file_info = validate_upload_file(file, check_mime=True)
            logger.info(f"Archivo validado: {file_info['safe_filename']}, tipo: {file_info.get('mime_type')}")
        except FileValidationError as e:
            logger.warning(f"Archivo rechazado: {e}")
            return jsonify({"error": str(e), "success": False}), 400
        
        # Procesar con OCR
        from ocr_processing import ReceiptOCR, check_tesseract_available
        
        tesseract_ok, tesseract_msg = check_tesseract_available()
        if not tesseract_ok:
            return jsonify({
                "error": f"Tesseract OCR no disponible: {tesseract_msg}. Instalalo desde https://github.com/UB-Mannheim/tesseract/wiki",
                "success": False
            }), 503
        
        # Procesar imagen
        file_bytes = file.read()
        result = ReceiptOCR.process_image_bytes(file_bytes)
        
        if result.get("error"):
            return jsonify({
                "error": result["error"],
                "raw_text": result.get("raw_text", ""),
                "success": False
            }), 422
        
        # Guardar imagen temporalmente en session para luego usarla en guardado
        # Convertir bytes a base64 para enviar al cliente
        import base64
        file_b64 = base64.b64encode(file_bytes).decode('utf-8')
        
        return jsonify({
            "success": True,
            "description": result.get("description", ""),
            "amount": result.get("amount"),
            "date": result.get("date"),
            "supplier_name": result.get("supplier_name", ""),
            "confidence": result.get("confidence", 0),
            "raw_text": result.get("raw_text", ""),
            "message": f"Información extraída con {result.get('confidence', 0)*100:.0f}% de confianza",
            "receipt_image_b64": file_b64  # Imagen en base64 para enviar al servidor
        }), 200
        
    except Exception as e:
        logger.error(f"Error en OCR: {e}", exc_info=True)
        return jsonify({"error": f"Error procesando recibo: {str(e)}", "success": False}), 500


@expenses_bp.route('/save-with-receipt', methods=['POST'])
@login_required
@permission_required('gastos.create')
@audit_log('gastos.crear', 'Gasto con recibo registrado')
def save_with_receipt():
    """Guarda gasto con imagen de recibo"""
    try:
        description = request.form.get("description", "").strip()
        try:
            amount = float(request.form.get("amount", 0))
        except Exception:
            flash("Monto válido requerido.", "error")
            return redirect(url_for("expenses.list"))
        
        if not description or amount <= 0:
            flash("Descripción y monto válido son requeridos.", "error")
            return redirect(url_for("expenses.list"))
        
        category = request.form.get("category", "").strip() or None
        supplier_id = request.form.get("supplier_id", "").strip()
        supplier_id = int(supplier_id) if supplier_id else None
        date = request.form.get("date", "").strip()
        payment_method = request.form.get("payment_method", "").strip() or None
        notes = request.form.get("notes", "").strip() or None
        
        # Guardar gasto
        expense_id = expenses.add_expense(description, amount, category, supplier_id, date, payment_method, notes)
        
        # Guardar recibo desde imagen base64 si existe
        receipt_image_b64 = request.form.get("receipt_image_b64", "").strip()
        if receipt_image_b64:
            try:
                import base64
                import io
                from PIL import Image
                
                # Decodificar base64
                image_data = base64.b64decode(receipt_image_b64)
                
                # Crear archivo en memoria
                image_file = io.BytesIO(image_data)
                image_file.name = f"receipt_{expense_id}.png"
                
                # Guardar imagen usando la función existente
                receipt_path = expenses.save_receipt_image(image_file, expense_id)
                if receipt_path:
                    expenses.update_expense(expense_id, receipt_path=receipt_path)
            except Exception as e:
                logger.warning(f"Error guardando imagen de recibo: {e}")
                # No interrumpir el flujo si hay error al guardar imagen
        
        # También intentar guardar si viene como archivo
        if "receipt_file" in request.files and request.files["receipt_file"].filename:
            receipt_path = expenses.save_receipt_image(request.files["receipt_file"], expense_id)
            if receipt_path:
                expenses.update_expense(expense_id, receipt_path=receipt_path)
        
        flash("Gasto registrado con éxito.", "success")
        cache.clear()
    except Exception as e:
        flash(f"Error al registrar gasto: {e}", "error")
    
    return redirect(url_for("expenses.list"))
