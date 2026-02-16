from loginOdoo.conexao import criar_conexao
from rich import print

try:
    conn = criar_conexao()
    print("[green]Conectado![/green]")
    
    # Listar TUDO
    fields = conn.executar("product.template", "fields_get")
    print(f"Campos: {list(fields.keys())}")
        
except Exception as e:
    print(f"[red]Erro: {e}[/red]")
