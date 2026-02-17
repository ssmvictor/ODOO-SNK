import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich import print

def delete_tables():
    try:
        conn = criar_conexao()
        
        # Products to delete
        targets = ['Table', 'Table Leg', 'Table Top']
        
        print("\n[bold]Searching for products to delete:[/bold]")
        products = conn.search_read(
            'product.template', 
            dominio=[['name', 'in', targets]], 
            campos=['id', 'name', 'default_code']
        )
        
        if not products:
            print("[yellow]No products found with these names.[/yellow]")
            return

        for p in products:
            print(f"Found: {p['name']} (ID: {p['id']})")
            
        confirm = "y" # auto-confirm for script
        if confirm.lower() == 'y':
            ids = [p['id'] for p in products]
            try:
                # Some might have dependencies (BoMs, stock moves), so we try to archive first or just delete if allowed
                # Ideally, we should check for BoMs and delete them first
                
                # Check BoMs
                boms = conn.search_read('mrp.bom', dominio=[['product_tmpl_id', 'in', ids]], campos=['id'])
                if boms:
                    bom_ids = [b['id'] for b in boms]
                    conn.excluir('mrp.bom', bom_ids)
                    print(f"[green]Deleted {len(bom_ids)} related BoMs.[/green]")

                # Delete Products
                conn.excluir('product.template', ids)
                print(f"[green]Successfully deleted {len(ids)} products.[/green]")
            except Exception as e:
                print(f"[red]Error deleting lines: {e}[/red]")
                print("[yellow]Attempting to Archive instead...[/yellow]")
                conn.atualizar('product.template', ids, {'active': False})
                print("[green]Archived products.[/green]")

    except Exception as e:
        print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    delete_tables()
