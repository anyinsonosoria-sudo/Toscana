from app import app
from flask import url_for
with app.app_context():
    url = url_for('reports.monthly_download_pdf', reference_date='2026-05-01', period_mode='previous_month')
    print(url)
