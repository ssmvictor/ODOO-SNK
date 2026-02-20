import os
import sys
import json

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def search_checks():
    try:
        conn = criar_conexao()
        
        # 1. Find ADEILSON
        employees = conn.search_read('hr.employee', dominio=[['name', 'ilike', 'ADEILSON']], campos=['id', 'name'])
        if not employees:
            print("ADEILSON not found")
            return
        
        emp_id = employees[0]['id']
        print(f"Searching checks for {employees[0]['name']} (ID: {emp_id})")

        # 2. Search quality.check
        checks = conn.search_read(
            'quality.check',
            # dominio=[['employee_id', '=', emp_id]], # Trying with employee_id first
            dominio=['|', ['employee_id', '=', emp_id], ['x_studio_funcionario', '=', emp_id]], # Try both
            campos=['name', 'employee_id', 'x_studio_funcionario', 'qty_passed', 'qty_failed', 'create_date', 'product_id', 'production_id'],
            limite=20
        )
        print("Quality Check Results:")
        print(json.dumps(checks, indent=2))

        # 3. If no checks, maybe it's custom?
        if not checks:
            print("No quality checks found for this employee. Checking quality.alert for totals...")
            alerts = conn.search_read(
                'quality.alert',
                dominio=[['x_studio_funcionario', '=', emp_id]],
                campos=['name', 'description', 'x_studio_quantidade_produzida', 'x_studio_quantidade_ruim'], # Guessing fields based on common Studio names
                limite=10
            )
            print("Quality Alert Results:")
            print(json.dumps(alerts, indent=2))

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    search_checks()
