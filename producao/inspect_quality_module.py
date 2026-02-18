# -*- coding: utf-8 -*-
"""
Inspeciona o Odoo para verificar:
1. Se o módulo 'quality' está instalado
2. Departamento "Fundição" existente
3. Funcionários no setor Fundição
4. Campos disponíveis em quality.alert (se houver)
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich.console import Console
from rich.table import Table

console = Console()


def main():
    conn = criar_conexao()

    # 1. Verificar módulo quality
    console.print("\n[bold cyan]═══ MÓDULOS DE QUALIDADE ═══[/bold cyan]")
    quality_modules = conn.search_read(
        'ir.module.module',
        dominio=[['name', 'in', ['quality', 'quality_control', 'quality_mrp']]],
        campos=['name', 'shortdesc', 'state'],
        limite=20
    )
    if quality_modules:
        for m in quality_modules:
            status = "[green]INSTALADO[/green]" if m['state'] == 'installed' else f"[yellow]{m['state']}[/yellow]"
            console.print(f"  {m['name']:25} {status}  ({m['shortdesc']})")
    else:
        console.print("  [red]Nenhum módulo de qualidade encontrado[/red]")

    # 2. Verificar departamento Fundição
    console.print("\n[bold cyan]═══ DEPARTAMENTO FUNDIÇÃO ═══[/bold cyan]")
    depts = conn.search_read(
        'hr.department',
        dominio=[['name', 'ilike', 'fundi']],
        campos=['id', 'name', 'complete_name'],
        limite=10
    )
    if depts:
        for d in depts:
            console.print(f"  ID: {d['id']} | Nome: {d['name']} | Completo: {d.get('complete_name', '')}")
    else:
        console.print("  [yellow]Nenhum departamento 'Fundição' encontrado (será criado)[/yellow]")

    # 3. Listar todos os departamentos existentes
    console.print("\n[bold cyan]═══ TODOS OS DEPARTAMENTOS ═══[/bold cyan]")
    all_depts = conn.search_read(
        'hr.department',
        campos=['id', 'name'],
        limite=100,
        ordem='name'
    )
    for d in all_depts:
        console.print(f"  ID: {d['id']} | {d['name']}")
    console.print(f"  Total: {len(all_depts)}")

    # 4. Listar funcionários existentes
    console.print("\n[bold cyan]═══ FUNCIONÁRIOS EXISTENTES ═══[/bold cyan]")
    employees = conn.search_read(
        'hr.employee',
        campos=['id', 'name', 'barcode', 'department_id', 'job_title'],
        limite=500,
        ordem='name'
    )
    table = Table(title=f"Funcionários ({len(employees)} total)")
    table.add_column("ID", style="dim")
    table.add_column("Badge", style="cyan")
    table.add_column("Nome", style="white")
    table.add_column("Departamento", style="green")
    table.add_column("Cargo", style="yellow")
    for e in employees:
        dept_name = e['department_id'][1] if e.get('department_id') else "-"
        table.add_row(
            str(e['id']),
            str(e.get('barcode', '-')),
            e['name'],
            dept_name,
            e.get('job_title', '-') or '-'
        )
    console.print(table)

    # 5. Se quality instalado, listar campos
    installed = [m['name'] for m in quality_modules if m['state'] == 'installed']
    if installed:
        console.print("\n[bold cyan]═══ CAMPOS quality.alert ═══[/bold cyan]")
        try:
            fields = conn.executar("quality.alert", "fields_get", args=[[]])
            for fname, fprops in sorted(fields.items()):
                ftype = fprops.get('type', '?')
                fstring = fprops.get('string', '')
                console.print(f"  {fname:35} {ftype:15} {fstring}")
        except Exception as e:
            console.print(f"  [red]Erro ao inspecionar quality.alert: {e}[/red]")

        console.print("\n[bold cyan]═══ CAMPOS quality.check ═══[/bold cyan]")
        try:
            fields = conn.executar("quality.check", "fields_get", args=[[]])
            for fname, fprops in sorted(fields.items()):
                ftype = fprops.get('type', '?')
                fstring = fprops.get('string', '')
                console.print(f"  {fname:35} {ftype:15} {fstring}")
        except Exception as e:
            console.print(f"  [red]Erro ao inspecionar quality.check: {e}[/red]")

    # 6. Verificar se quality.reason existe (motivos de não conformidade)
    if installed:
        console.print("\n[bold cyan]═══ MOTIVOS DE QUALIDADE (quality.reason) ═══[/bold cyan]")
        try:
            reasons = conn.search_read(
                'quality.reason',
                campos=['id', 'name'],
                limite=100
            )
            if reasons:
                for r in reasons:
                    console.print(f"  ID: {r['id']} | {r['name']}")
            else:
                console.print("  [yellow]Nenhum motivo cadastrado[/yellow]")
        except Exception as e:
            console.print(f"  [yellow]Modelo quality.reason não disponível: {e}[/yellow]")

        # Quality teams
        console.print("\n[bold cyan]═══ EQUIPES DE QUALIDADE ═══[/bold cyan]")
        try:
            teams = conn.search_read(
                'quality.alert.team',
                campos=['id', 'name'],
                limite=100
            )
            if teams:
                for t in teams:
                    console.print(f"  ID: {t['id']} | {t['name']}")
            else:
                console.print("  [yellow]Nenhuma equipe cadastrada[/yellow]")
        except Exception as e:
            console.print(f"  [yellow]Modelo quality.alert.team não disponível: {e}[/yellow]")


if __name__ == "__main__":
    main()
