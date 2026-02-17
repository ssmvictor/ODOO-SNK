import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich import print

def inspect_products():
    try:
        conn = criar_conexao()
        
        # 1. Search for 'Massa' (210000)
        print("\n[bold]Searching for Raw Material (Massa - 210000):[/bold]")
        massa = conn.search_read(
            'product.product', 
            dominio=[['default_code', '=', '210000']], 
            campos=['id', 'name', 'default_code', 'uom_id']
        )
        if massa:
            print(f"Found: {massa[0]['name']} (ID: {massa[0]['id']}, Code: {massa[0]['default_code']}, UoM: {massa[0]['uom_id']})")
        else:
            print("[red]Massa (210000) NOT FOUND[/red]")

        # 2. Search for 'BACIA CONVENCIONAL ÍRIS (CRU)'
        # Using ILIKE for flexibility
        print("\n[bold]Searching for Finished Product (BACIA CONVENCIONAL ÍRIS (CRU)):[/bold]")
        bacia = conn.search_read(
            'product.template', 
            dominio=[['name', 'ilike', 'BACIA CONVENCIONAL ÍRIS (CRU)']], 
            campos=['id', 'name', 'weight', 'uom_id']
        )
        
        if bacia:
            for p in bacia:
                print(f"Found: {p['name']} (ID: {p['id']}, Weight: {p['weight']}, UoM: {p['uom_id']})")
        else:
            print("[red]Product NOT FOUND[/red]")

    except Exception as e:
        print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    inspect_products()
