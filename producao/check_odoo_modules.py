import os
import sys
import json

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def check_modules():
    try:
        conn = criar_conexao()
        
        print("\n--- Checking for Reporting Modules ---")
        modules = conn.search_read(
            'ir.module.module',
            dominio=[['name', 'in', ['spreadsheet', 'spreadsheet_dashboard', 'documents_spreadsheet', 'board']]],
            campos=['name', 'shortdesc', 'state']
        )
        for m in modules:
            print(f"  {m['name']:25} {m['state']} ({m['shortdesc']})")
            
        print("\n--- Checking if there are custom fields in hr.employee for production/quality ---")
        fields = conn.executar("hr.employee", "fields_get", args=[[]])
        interesting = {k: v['string'] for k, v in fields.items() if k.startswith('x_')}
        print(f"Custom employee fields: {json.dumps(interesting, indent=2)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_modules()
