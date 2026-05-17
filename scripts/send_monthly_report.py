"""
Script CLI para validar y despachar el reporte financiero mensual.

Uso rápido en PythonAnywhere:

Prueba directa a un correo concreto sin tocar el log mensual:
  python scripts/send_monthly_report.py --mode direct --recipient-email pinturasselecta@gmail.com --recipient-name "Prueba Residente" --recipient-type resident

Despacho real del flujo mensual usando el log de envíos:
    python scripts/send_monthly_report.py --mode dispatch --admin-only --admin-email invoicetoscana@gmail.com

Vista previa o envío manual del mes actual a la fecha:
    python scripts/send_monthly_report.py --mode direct --period-mode current_month_to_date --reference-date 2026-05-17 --recipient-email admin@correo.com --dry-run
"""

import argparse
import io
import sys
import traceback
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv(BASE_DIR / '.env')

import db
from company import get_company_info
from reports import (
    generate_monthly_financial_report_pdf_file,
    get_monthly_financial_report_data,
    send_previous_month_financial_report,
)
from senders import send_monthly_financial_report_email


def _configure_stdout() -> None:
    if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def _parse_reference_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Fecha inválida '{value}'. Usa formato YYYY-MM-DD."
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Valida o despacha el reporte financiero mensual con salida visible en consola.'
    )
    parser.add_argument(
        '--mode',
        choices=('direct', 'dispatch'),
        default='direct',
        help='direct: envía a un correo específico sin usar el log. dispatch: usa el flujo mensual real con deduplicación.',
    )
    parser.add_argument('--recipient-email', help='Correo de destino para modo direct.')
    parser.add_argument('--recipient-name', default='Destinatario de prueba', help='Nombre mostrado en modo direct.')
    parser.add_argument(
        '--recipient-type',
        choices=('admin', 'resident'),
        default='resident',
        help='Tipo de destinatario en modo direct.',
    )
    parser.add_argument(
        '--period-mode',
        choices=('previous_month', 'current_month_to_date'),
        default='previous_month',
        help='previous_month: mes anterior completo. current_month_to_date: mes actual hasta la fecha indicada.',
    )
    parser.add_argument('--admin-only', action='store_true', help='En modo dispatch, limita el envío al administrador.')
    parser.add_argument('--admin-email', help='Override del correo del administrador en modo dispatch.')
    parser.add_argument('--reference-date', type=_parse_reference_date, help='Fecha base YYYY-MM-DD para calcular el período seleccionado.')
    parser.add_argument('--output-path', help='Ruta del PDF a generar.')
    parser.add_argument('--dry-run', action='store_true', help='Genera el reporte y muestra datos, pero no envía correo.')
    return parser


def _run_direct_mode(args: argparse.Namespace) -> dict:
    if not args.recipient_email:
        raise ValueError('Debes indicar --recipient-email en modo direct.')

    print('[1/4] Inicializando base de datos...', flush=True)
    db.init_db()

    print('[2/4] Calculando reporte mensual...', flush=True)
    report_data = get_monthly_financial_report_data(
        reference_dt=args.reference_date,
        period_mode=args.period_mode,
    )
    company_info = get_company_info() or {}

    print('[3/4] Generando PDF...', flush=True)
    pdf_path = generate_monthly_financial_report_pdf_file(
        report_data,
        company_info,
        output_path=args.output_path,
    )

    result = {
        'mode': 'direct',
        'recipient_email': args.recipient_email,
        'recipient_name': args.recipient_name,
        'recipient_type': args.recipient_type,
        'period_mode': args.period_mode,
        'report_period': report_data['report_period'],
        'period_label': report_data['period_label'],
        'pdf_path': pdf_path,
        'dry_run': args.dry_run,
    }

    if args.dry_run:
        print('[4/4] Dry run activo. No se enviará correo.', flush=True)
        return result

    print(f"[4/4] Enviando correo a {args.recipient_email}...", flush=True)
    subject = send_monthly_financial_report_email(
        args.recipient_email,
        report_data,
        pdf_path,
        recipient_name=args.recipient_name,
        recipient_type=args.recipient_type,
        company_name=company_info.get('name'),
    )
    result['subject'] = subject
    result['sent'] = [args.recipient_email]
    return result


def _run_dispatch_mode(args: argparse.Namespace) -> dict:
    print('[1/2] Inicializando base de datos...', flush=True)
    db.init_db()

    if args.dry_run:
        raise ValueError('El modo dispatch no soporta --dry-run. Usa --mode direct para validar sin enviar.')

    print('[2/2] Ejecutando flujo mensual real...', flush=True)
    return send_previous_month_financial_report(
        reference_dt=args.reference_date,
        output_path=args.output_path,
        admin_only=args.admin_only,
        admin_email_override=args.admin_email,
        period_mode=args.period_mode,
    )


def _result_has_failures(result: dict) -> bool:
    failed = result.get('failed') or []
    if failed:
        return True

    sent = result.get('sent') or []
    skipped = result.get('skipped') or []
    dry_run = bool(result.get('dry_run', False))

    if dry_run:
        return False

    return not sent and not skipped


def main() -> int:
    _configure_stdout()
    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.mode == 'direct':
            result = _run_direct_mode(args)
        else:
            result = _run_dispatch_mode(args)

        print('\nResultado:', flush=True)
        print(result, flush=True)
        if _result_has_failures(result):
            return 1
        return 0
    except Exception as exc:
        print(f"\n[ERROR] {exc}", flush=True)
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())