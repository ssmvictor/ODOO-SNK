import sys
from pathlib import Path
sys.path.append(str(Path('.').resolve()))
try:
    from loginOdoo.conexao import criar_conexao
    conn = criar_conexao()
    conn.atualizar('res.company', 2, {'name': 'ONIX (ARCHIVED)', 'vat': False, 'company_registry': False})
    print("Company 2 renamed to free up the unique name.")
except Exception as e:
    print(f"Error: {e}")
