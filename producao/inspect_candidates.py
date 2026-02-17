import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich import print

def inspect_candidates():
    try:
        conn = criar_conexao()
        
        # Search for products with 'CRU' in name
        print("\n[bold]Searching for products with '(CRU)' in name:[/bold]")
        products = conn.search_read(
            'product.template', 
            dominio=[['name', 'ilike', '(CRU)']], 
            campos=['id', 'name', 'weight', 'uom_id']
        )
        
        if products:
            print(f"Found {len(products)} products.")
            for p in products[:10]: # List first 10
                print(f" - {p['name']} (Weight: {p['weight']} kg)")
        else:
            print("[red]No products found with '(CRU)'[/red]")

    except Exception as e:
        print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    inspect_candidates()
