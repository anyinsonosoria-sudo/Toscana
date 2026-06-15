import sys

def fix_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # We want to delete from line 1676 to 1870 (inclusive)
    # Note: lists are 0-indexed, so line 1676 is index 1675.
    start_index = 1675
    end_index = 1870
    
    # Verify the lines before deleting to be absolutely safe
    if "# Variable para verificar disponibilidad de senders" in lines[start_index]:
        # Delete the slice
        del lines[start_index:end_index]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print("SUCCESS: File fixed.")
    else:
        print("ERROR: Line 1676 does not match expected content. Did not modify.")

if __name__ == "__main__":
    fix_file('blueprints/billing.py')
