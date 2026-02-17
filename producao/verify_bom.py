import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich import print

def verify_bom_config():
    try:
        conn = criar_conexao()
        
        # 1. Get All Candidates
        print("\n[bold]Verifying BoM Configuration for '(CRU)' products:[/bold]")
        # Context active_test=False to find archived ones too if that was the case
        # But OdooRPC search_read usually respects context. 
        # Let's just use standard search which implies active=True.
        products = conn.search_read(
            'product.template', 
            dominio=[['name', 'ilike', '(CRU)']], 
            campos=['id', 'name', 'weight', 'active']
        )
        
        print(f"Total Products found: {len(products)}")
        
        massa = conn.search_read('product.product', dominio=[['default_code', '=', '210000']], campos=['id'])
        if not massa:
             print("[red]Massa not found[/red]")
             return
        massa_id = massa[0]['id']

        ok_count = 0
        error_count = 0
        skip_count = 0

        for p in products:
            name = p['name']
            weight = p['weight']
            p_id = p['id']
            
            if weight <= 0:
                print(f"[yellow]SKIP: {name} (Weight: {weight})[/yellow]")
                skip_count += 1
                continue

            # Check BoM
            boms = conn.search_read('mrp.bom', dominio=[['product_tmpl_id', '=', p_id]], campos=['id', 'bom_line_ids'])
            
            if not boms:
                print(f"[red]FAIL: {name} - No BoM found[/red]")
                error_count += 1
                continue
                
            bom_id = boms[0]['id']
            lines = conn.search_read('mrp.bom.line', dominio=[['bom_id', '=', bom_id]], campos=['product_id', 'product_qty'])
            
            massa_line = next((l for l in lines if l['product_id'][0] == massa_id), None)
            
            if massa_line:
                qty = massa_line['product_qty']
                if abs(qty - weight) < 0.001: # Float comparison
                    # print(f"[green]OK:   {name} (Weight: {weight} == BoM: {qty})[/green]")
                    ok_count += 1
                else:
                    print(f"[red]FAIL: {name} (Weight: {weight} != BoM: {qty})[/red]")
                    error_count += 1
            else:
                print(f"[red]FAIL: {name} - BoM exists but 'Massa' line missing[/red]")
                error_count += 1

        print("\n[bold]Summary:[/bold]")
        print(f"Total: {len(products)}")
        print(f"OK:   [green]{ok_count}[/green]")
        print(f"FAIL: [red]{error_count}[/red]")
        print(f"SKIP: [yellow]{skip_count}[/yellow]")

    except Exception as e:
        print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    verify_bom_config()
