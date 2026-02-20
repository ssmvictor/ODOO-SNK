import os
import sys
import json

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def probe_odoo():
    try:
        conn = criar_conexao()
        
        # 1. Look for production records on 2026-02-18
        print("\n--- Searching mrp.production (2026-02-18) ---")
        # Try different date fields if date_planned_start doesn't work
        productions = conn.search_read(
            'mrp.production',
            dominio=[['date_planned_start', '>=', '2026-02-18 00:00:00'], 
                    ['date_planned_start', '<=', '2026-02-18 23:59:59']],
            campos=['name', 'product_id', 'qty_producing', 'product_qty', 'state'],
            limite=5
        )
        print("mrp.production results:")
        print(json.dumps(productions, indent=2))

        # 2. Look for quality alerts for ADEILSON
        print("\n--- Searching quality.alert for ADEILSON ---")
        employees = conn.search_read('hr.employee', dominio=[['name', 'ilike', 'ADEILSON']], campos=['id', 'name'])
        if employees:
            emp_id = employees[0]['id']
            print(f"Found Employee: {employees[0]['name']} (ID: {emp_id})")
            alerts = conn.search_read(
                'quality.alert',
                dominio=[['x_studio_funcionario', '=', emp_id]],
                campos=['name', 'reason_id', 'create_date', 'description'],
                limite=5
            )
            print("quality.alert results:")
            print(json.dumps(alerts, indent=2))
        else:
            print("Employee ADEILSON not found")

        # 3. Check for any model that might contain "production" or "fundicao"
        print("\n--- Searching for production related models ---")
        models = conn.executar('ir.model', 'search_read', args=[['|', ['model', 'ilike', 'prod'], ['model', 'ilike', 'fund']], ['model', 'name']])
        print(f"Found {len(models)} models matching 'prod' or 'fund'")
        # Only print first 20
        for m in models[:20]:
            print(f"  {m['model']}: {m['name']}")

    except Exception as e:
        print(f"Error during probe: {e}")

if __name__ == "__main__":
    probe_odoo()
