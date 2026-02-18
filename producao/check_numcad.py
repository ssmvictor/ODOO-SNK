import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def check_numcad():
    try:
        conn = criar_conexao()
        
        # Get 5 active employees
        employees = conn.search_read(
            'hr.employee', 
            dominio=[['active', '=', True]], 
            campos=['name', 'barcode', 'department_id'], 
            limite=5
        )
        
        with open('producao/numcad_result.txt', 'w', encoding='utf-8') as f:
            f.write("Checking NUMCAD (Barcode) in Odoo:\n")
            for emp in employees:
                dept_name = emp['department_id'][1] if emp['department_id'] else "No Dept"
                f.write(f" - Name: {emp['name']}\n")
                f.write(f"   NUMCAD (Barcode): {emp['barcode']}\n")
                f.write(f"   Department: {dept_name}\n")
                f.write("-" * 30 + "\n")
                
        print("Verification complete. Results saved to producao/numcad_result.txt")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_numcad()
