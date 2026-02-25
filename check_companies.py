import sys
from pathlib import Path
sys.path.append(str(Path('.').resolve()))
try:
    from loginOdoo.conexao import criar_conexao
    conn = criar_conexao()
    companies = conn.search_read('res.company', [], ['id', 'name', 'vat', 'company_registry'])
    for c in companies:
        print(f"ID: {c.get('id')} | Name: {c.get('name')} | VAT: {c.get('vat')} | Registry: {c.get('company_registry')}")
except Exception as e:
    print(f"Error: {e}")
