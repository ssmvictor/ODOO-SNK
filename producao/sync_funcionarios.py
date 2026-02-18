import os
import oracledb
from dotenv import load_dotenv
import sys
from rich.console import Console
from rich.table import Table

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao, OdooConexao

# Initialize Console
console = Console()

# Load environment variables
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)

# Oracle Configuration
DB_HOST = os.getenv("ORACLE_HOST")
DB_PORT = os.getenv("ORACLE_PORT")
DB_SERVICE = os.getenv("ORACLE_SERVICE_NAME")
DB_USER = os.getenv("ORACLE_USER")
DB_PASSWORD = os.getenv("ORACLE_PASSWORD")

def get_employees_from_rubi():
    """
    Connects to Oracle and returns employee records.
    """
    if not all([DB_HOST, DB_PORT, DB_SERVICE, DB_USER, DB_PASSWORD]):
        console.print(f"[red]Error: Missing Oracle environment variables using .env at {dotenv_path}[/red]")
        return []

    dsn = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"
    
    try:
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=dsn
        )

        with connection.cursor() as cursor:
            # SQL Query to fetch employees
            sql = """
            SELECT FUN.NUMCAD, FUN.NOMFUN, CCU.NOMCCU AS SETOR, HCC.DATALT, CAR.TITCAR AS CARGO, FUN.SITAFA
              FROM VETORH.R034FUN FUN 
              LEFT JOIN VETORH.R038HCC HCC ON (HCC.NUMCAD = FUN.NUMCAD) AND (HCC.NUMEMP = FUN.NUMEMP) AND
                                         (HCC.TIPCOL = FUN.TIPCOL)
              LEFT JOIN VETORH.R018CCU CCU ON (CCU.NUMEMP = FUN.NUMEMP
                                          AND  CCU.CODCCU = HCC.CODCCU)
              LEFT JOIN VETORH.R024CAR CAR ON (CAR.CODCAR = FUN.CODCAR)
             WHERE FUN.NUMEMP = 11
               AND FUN.TIPCOL = 1
               AND (FUN.SITAFA <> 7 OR TRUNC(FUN.DATAFA) >= '01/01/2026')
             ORDER BY FUN.NUMCAD
            """
            
            cursor.execute(sql)
            
            # Get column names
            columns = [col[0] for col in cursor.description]
            
            # Fetch all rows
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))
            
            return results

    except oracledb.Error as e:
        console.print(f"[bold red]Oracle Error:[/bold red] {e}")
        return []
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        return []
    finally:
        if 'connection' in locals():
            connection.close()

def sync_employees(employees, odoo_conn: OdooConexao):
    """
    Syncs employees to Odoo.
    """
    console.print(f"\n[bold blue]Starting Synchronization of {len(employees)} Employees...[/bold blue]")
    
    table = Table(title="Synchronization Results")
    table.add_column("Badge (NUMCAD)", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Status (Rubi)", style="yellow")
    table.add_column("Action (Odoo)", style="green")
    
    # Cache departments to avoid re-querying
    departments = {}
    
    for emp in employees:
        numcad = str(emp['NUMCAD'])
        nomfun = emp['NOMFUN']
        titcar = emp['CARGO']
        sitafa = emp['SITAFA']
        setor_nome = emp.get('SETOR')
        data_admissao = emp.get('DATALT') # Assuming DATALT is datetime object from Oracle

        # Determine status
        is_active = sitafa != 7
        status_str = "Active" if is_active else "Dismissed"
        
        department_id = False
        if is_active and setor_nome:
            if setor_nome not in departments:
                # Check if department exists
                dept_search = odoo_conn.search_read('hr.department', dominio=[['name', '=', setor_nome]], campos=['id'])
                if dept_search:
                     departments[setor_nome] = dept_search[0]['id']
                else:
                     # Create department
                     new_dept_id = odoo_conn.criar('hr.department', {'name': setor_nome})
                     departments[setor_nome] = new_dept_id
            
            department_id = departments[setor_nome]

        # Search for employee in Odoo by barcode (NUMCAD)
        existing = odoo_conn.search_read(
            'hr.employee',
            dominio=[['barcode', '=', numcad]],
            campos=['id', 'name', 'active', 'job_title', 'department_id']
        )
        
        if existing:
            # Update existing employee
            employee_id = existing[0]['id']
            odoo_active = existing[0]['active']
            
            vals = {}
            action = "Skipped"

            # Check if we need to update status (Archiving/Unarchiving)
            if odoo_active != is_active:
                vals['active'] = is_active
                action = "Archived" if not is_active else "Unarchived"
            
            # Update other fields if active or reactivating
            if is_active:
                if existing[0]['name'] != nomfun:
                   vals['name'] = nomfun
                   action = "Updated Name"
                if existing[0]['job_title'] != titcar:
                   vals['job_title'] = titcar
                   if action == "Skipped": action = "Updated Job"
                   else: action += ", Job"
                
                # Check Department Update
                current_dept_id = existing[0].get('department_id', [False])[0] if existing[0].get('department_id') else False
                if department_id and current_dept_id != department_id:
                    vals['department_id'] = department_id
                    if action == "Skipped": action = "Updated Dept"
                    else: action += ", Dept"

                # Check Admission Date Update (first_contract_date)
                # Convert active Oracle date to string YYYY-MM-DD
                # if data_admissao:
                #     date_str = data_admissao.strftime('%Y-%m-%d')
                #     current_date = existing[0].get('first_contract_date')
                #     if current_date != date_str:
                #         vals['first_contract_date'] = date_str
                #         # Also update date_start if needed? Let's stick to first_contract_date for now as it seems most relevant for admission
                #         if action == "Skipped": action = "Updated Date"
                #         else: action += ", Date"
            
            if vals:
                odoo_conn.atualizar('hr.employee', employee_id, vals)
                if action == "Skipped": 
                    action = "Updated"
            
            table.add_row(numcad, nomfun, status_str, action)
            
        else:
            # Create new employee
            if is_active:
                vals = {
                    'name': nomfun,
                    'job_title': titcar,
                    'barcode': numcad,
                    'active': True
                }
                if department_id:
                    vals['department_id'] = department_id
                # if data_admissao:
                #    vals['first_contract_date'] = data_admissao.strftime('%Y-%m-%d')

                odoo_conn.criar('hr.employee', vals)
                table.add_row(numcad, nomfun, status_str, "Created")
            else:
                table.add_row(numcad, nomfun, status_str, "Ignored (Dismissed & Not Found)")

    console.print(table)

def main():
    # 1. Get employees from Rubi
    employees = get_employees_from_rubi()
    
    if not employees:
        console.print("[yellow]No employees found in Rubi or error occurred.[/yellow]")
        return

    # 2. Connect to Odoo
    try:
        odoo_conn = criar_conexao()
    except Exception as e:
        console.print(f"[bold red]Failed to connect to Odoo: {e}[/bold red]")
        return

    # 3. Sync
    sync_employees(employees, odoo_conn)

if __name__ == "__main__":
    main()
