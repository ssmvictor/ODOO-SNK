import os
import sys
import json

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def find_total_fields():
    try:
        conn = criar_conexao()
        
        models = ["quality.alert", "quality.check"]
        for model in models:
            print(f"\n--- Fields for {model} ---")
            fields = conn.executar(model, "fields_get", args=[[]])
            for f, props in fields.items():
                if any(x in f.lower() or x in props.get('string', '').lower() for x in ['total', 'quant', 'produ', 'peca', 'peça', 'total', 'meta']):
                    print(f"  {f:30} | {props.get('string')} ({props.get('type')})")
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    find_total_fields()
