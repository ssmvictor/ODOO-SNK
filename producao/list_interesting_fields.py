import os
import sys
import json

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def list_all_fields():
    try:
        conn = criar_conexao()
        
        models = ["quality.alert", "quality.check", "mrp.production"]
        
        for model in models:
            print(f"\n--- Fields for {model} ---")
            try:
                fields = conn.executar(model, "fields_get", args=[[]])
                # Print only custom fields (x_*) or interesting ones
                interesting = {}
                for f, props in fields.items():
                    if f.startswith('x_') or any(x in f.lower() or x in props.get('string', '').lower() for x in ['emp', 'func', 'qty', 'quant', 'produ', 'peça']):
                        interesting[f] = {
                            'type': props.get('type'),
                            'string': props.get('string'),
                            'relation': props.get('relation', '')
                        }
                print(json.dumps(interesting, indent=2))
            except Exception as e:
                print(f"Error listing {model} fields: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_all_fields()
