import os
import sys
import json

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def search_productivity():
    try:
        conn = criar_conexao()
        
        print("\n--- Searching mrp.workcenter.productivity ---")
        # Search for records in Feb 2026
        records = conn.search_read(
            'mrp.workcenter.productivity',
            dominio=[['date_start', '>=', '2026-02-18 00:00:00']],
            campos=['employee_id', 'workcenter_id', 'date_start', 'duration', 'production_id'],
            limite=10
        )
        print(json.dumps(records, indent=2))

        # Check fields of mrp.workcenter.productivity
        print("\n--- Fields for mrp.workcenter.productivity ---")
        fields = conn.executar('mrp.workcenter.productivity', "fields_get", args=[[]])
        interesting = {k: v['string'] for k, v in fields.items() if any(x in k.lower() or x in v['string'].lower() for x in ['qty', 'quant', 'produ', 'peca', 'peça'])}
        print(json.dumps(interesting, indent=2))

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    search_productivity()
