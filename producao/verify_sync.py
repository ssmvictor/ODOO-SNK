import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich import print

def verify_sync():
    conn = criar_conexao()
    
    # Count active employees
    active_count = len(conn.search_read('hr.employee', dominio=[['active', '=', True]], campos=['id']))
    
    # Count inactive employees
    inactive_count = len(conn.search_read('hr.employee', dominio=[['active', '=', False]], campos=['id']))
    
    # Check a sample employee (e.g., NumCad 11 - assuming it exists or one from the logs if I had them)
    # Let's just list 5 active and 5 inactive to see if they look correct (with barcode)
    
    print(f"\n[bold]Verification Results:[/bold]")
    print(f"Active Employees in Odoo: {active_count}")
    print(f"Inactive Employees in Odoo: {inactive_count}")
    
    print("\n[bold]Sample Active Employees:[/bold]")
    active_sample = conn.search_read('hr.employee', dominio=[['active', '=', True]], campos=['name', 'barcode', 'job_title'], limite=5)
    for emp in active_sample:
        print(f" - {emp['name']} (Badge: {emp['barcode']}) - {emp['job_title']}")

    print("\n[bold]Sample Inactive Employees:[/bold]")
    inactive_sample = conn.search_read('hr.employee', dominio=[['active', '=', False]], campos=['name', 'barcode', 'job_title'], limite=5)
    for emp in inactive_sample:
        print(f" - {emp['name']} (Badge: {emp['barcode']}) - {emp['job_title']}")

if __name__ == "__main__":
    verify_sync()
