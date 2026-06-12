import os
import sys

# Add the project directory to sys.path
sys.path.insert(0, r"c:\Users\anyinson.osoria\OneDrive - PC Precision Engineering\Desktop\Toscana\Toscana")

from app import app
from services.resident_help import build_report_months

with app.app_context():
    with app.test_request_context('/dashboard/reportes'):
        context = {
            'current_user': type('User', (), {'full_name': 'Test', 'username': 'test', 'id': 1, 'email': 'test@test.com'}),
            'apartments': [],
            'total_pending': 0,
            'total_paid': 0,
            'company_info': {},
            'report_months': build_report_months(),
            'current_report_url': '/test_current_report_url',
        }
        from flask import render_template
        html = render_template('resident_reports.html', **context)
        with open("rendered_output.html", "w", encoding="utf-8") as f:
            f.write(html)
print("Rendered HTML saved to rendered_output.html")
