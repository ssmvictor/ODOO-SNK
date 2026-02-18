import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich import print

def config_bom():
    try:
        conn = criar_conexao()
        
        # 1. Get Products
        # Massa (Raw Material)
        massa = conn.search_read('product.product', dominio=[['default_code', '=', '210000']], campos=['id', 'name', 'uom_id'])
        if not massa:
            print("[red]Error: Massa (210000) not found![/red]")
            return
        massa_id = massa[0]['id']
        massa_uom = massa[0]['uom_id'][0]
        
        # Bacia (Finished Product)
        # Search for all products with '(CRU)'
        products = conn.search_read(
            'product.template', 
            dominio=[['name', 'ilike', '(CRU)']], 
            campos=['id', 'name', 'weight', 'uom_id']
        )
        
        if not products:
            print("[red]No products found with '(CRU)'[/red]")
            return

        print(f"Found {len(products)} products to configure.")

        for p in products:
            product_id = p['id']
            product_weight = p['weight']
            product_uom = p['uom_id'][0]
            product_name = p['name']
            
            print(f"\nProcessing [bold]{product_name}[/bold] (Weight: {product_weight} kg)")
            
            if product_weight <= 0:
                print(f"[yellow]Skipping {product_name}: Weight is 0 or negative![/yellow]")
                continue

            # 2. Check for Existing BoM
            bom = conn.search_read('mrp.bom', dominio=[['product_tmpl_id', '=', product_id]], campos=['id', 'bom_line_ids'])
            
            if bom:
                bom_id = bom[0]['id']
                # Check lines
                lines = conn.search_read('mrp.bom.line', dominio=[['bom_id', '=', bom_id]], campos=['id', 'product_id', 'product_qty'])
                
                massa_line = next((l for l in lines if l['product_id'][0] == massa_id), None)
                
                if massa_line:
                    if massa_line['product_qty'] != product_weight:
                        conn.atualizar('mrp.bom.line', massa_line['id'], {'product_qty': product_weight})
                        print(f"[green]Updated Massa quantity to {product_weight}[/green]")
                    else:
                        print("[green]Massa quantity already correct.[/green]")
                else:
                    # Add line
                    vals = {
                        'bom_id': bom_id,
                        'product_id': massa_id,
                        'product_qty': product_weight,
                        'product_uom_id': massa_uom 
                    }
                    conn.criar('mrp.bom.line', vals)
                    print(f"[green]Added Massa line with quantity {product_weight}[/green]")
                    
            else:
                print("BoM not found. Creating new BoM...")
                # Create BoM
                bom_vals = {
                    'product_tmpl_id': product_id,
                    'product_qty': 1.0,
                    'product_uom_id': product_uom,
                    'type': 'normal'
                }
                bom_id = conn.criar('mrp.bom', bom_vals)
                print(f"Created BoM ID: {bom_id}")
                
                # Add Line
                line_vals = {
                    'bom_id': bom_id,
                    'product_id': massa_id,
                    'product_qty': product_weight,
                    'product_uom_id': massa_uom
                }
                conn.criar('mrp.bom.line', line_vals)
                print(f"[green]Added Massa line with quantity {product_weight}[/green]")

    except Exception as e:
        print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    config_bom()
