import os
import sys
import json

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def list_fields():
    try:
        conn = criar_conexao()
        
        print("\n--- Listing fields for mrp.production ---")
        try:
            fields = conn.executar("mrp.production", "fields_get", args=[[]])
            # Filter for interesting fields
            interesting = {k: v['string'] for k, v in fields.items() if any(x in k.lower() or x in v['string'].lower() for x in ['qty', 'prod', 'date', 'emp', 'func', 'x_'])}
            print(json.dumps(interesting, indent=2))
        except Exception as e:
            print(f"Error listing mrp.production fields: {e}")

        print("\n--- Searching for production related models ---")
        try:
            models = conn.executar('ir.model', 'search_read', args=[['|', ['model', 'ilike', 'prod'], ['model', 'ilike', 'mrp']], ['model', 'name']])
            for m in models:
                print(f"  {m['model']}: {m['name']}")
        except Exception as e:
            print(f"Error listing models: {e}")

    except Exception as e:
        print(f"Error during probe: {e}")

if __name__ == "__main__":
    list_fields()
