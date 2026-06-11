import re

with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'def dashboard(' in line or 'def health_check(' in line or 'def _register_error_handlers(' in line:
        print(f"Line {i+1}: {line.strip()}")
