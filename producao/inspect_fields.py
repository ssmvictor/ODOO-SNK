import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich import print

def inspect_employee_fields():
    try:
        conn = criar_conexao()
        print("[green]Connected![/green]")
        
        # Get fields of hr.employee
        fields = conn.executar("hr.employee", "fields_get", args=[['department_id', 'first_contract_date', 'create_date', 'date_start', 'joining_date']])
        
        print("\n[bold]Related Fields found:[/bold]")
        for field, props in fields.items():
            print(f" - [cyan]{field}[/cyan]: {props.get('string')} ({props.get('type')})")
            
        # Also check department model
        print("\n[bold]Checking Department Model:[/bold]")
        dept_fields = conn.executar("hr.department", "fields_get", args=[['name']])
        for field, props in dept_fields.items():
             print(f" - [cyan]{field}[/cyan]: {props.get('string')} ({props.get('type')})")

    except Exception as e:
        print(f"[red]Error: {e}[/red]")

if __name__ == "__main__":
    inspect_employee_fields()
