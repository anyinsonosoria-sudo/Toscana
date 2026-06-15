import ast

def check_syntax(filename):
    try:
        with open(filename, 'rb') as f:
            source = f.read()
        ast.parse(source, filename=filename)
        print(f"SUCCESS: {filename} has valid syntax.")
        return True
    except SyntaxError as e:
        print(f"SYNTAX ERROR in {filename}:")
        print(f"Line {e.lineno}, offset {e.offset}: {e.text}")
        print(f"Error: {e.msg}")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

import sys
if __name__ == "__main__":
    check_syntax('blueprints/billing.py')
