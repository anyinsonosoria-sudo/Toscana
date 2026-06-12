import os
import sys

# Add the project directory to sys.path
sys.path.insert(0, r"c:\Users\anyinson.osoria\OneDrive - PC Precision Engineering\Desktop\Toscana\Toscana")

from app import app
from db import get_db

with app.test_client() as client:
    # We need to bypass login or mock it.
    # We can mock the flask_login.current_user!
    with client.session_transaction() as sess:
        # Flask-Login uses '_user_id' in session
        sess['_user_id'] = '1'
        sess['_fresh'] = True
    
    # Let's mock the user loader just in case, or we assume user 1 exists.
    # If user 1 is not a resident, we can just patch current_user.
    
    # Actually, the easiest way to test Jinja output without DB dependencies:
    with app.app_context():
        from services.resident_help import build_report_months
        from flask import render_template
        
        # We only care about the report_months loop!
        months = build_report_months()
        html = render_template('resident_reports.html', 
            current_user=type('User', (), {'full_name': 'Test', 'username': 'test', 'id': 1, 'email': 'test@test.com'}),
            apartments=[],
            total_pending=0,
            total_paid=0,
            company_info={},
            report_months=months,
            current_report_url='/test_current_report_url'
        )
        with open("c:\\Users\\anyinson.osoria\\OneDrive - PC Precision Engineering\\Desktop\\Toscana\\Toscana\\dump.html", "w", encoding="utf-8") as f:
            f.write(html)
print("Dumped HTML!")
