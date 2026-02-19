# -*- coding: utf-8 -*-
"""
Setup do Setor de Fundição no Odoo
===================================
Configura os recursos necessários para o setor de fundição/louças no Odoo:

1. Verifica ou cria o departamento "Fundição/louças".
2. Lista os fundidores já cadastrados no departamento.
3. Cadastra os motivos de não conformidade (``quality.reason``) específicos
   da fundição definidos na lista :data:`NAO_CONFORMIDADES`.
4. Cria a equipe de qualidade "Qualidade Fundição" (``quality.alert.team``).
5. Salva o resultado em ``producao/setup_fundicao_result.json``.

Uso::

    python producao/setup_fundicao.py
"""

import os
import sys
import json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao, OdooConexao
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# =============================================
# CONFIGURAÇÃO: Não conformidades da Fundição
# Adicione ou remova itens conforme necessário
# =============================================
NAO_CONFORMIDADES = [
    "Bolhas",
    "Trincas",
    "Deformação",
    "Porosidade",
    "Dimensão fora do padrão",
    "Rachadura",
    "Manchas",
    "Quebra no desmolde",
    "Peça incompleta",
    "Rebarbas",
    "Espessura irregular",
    "Acabamento rugoso",
]

DEPT_NAME = "Fundição/louças"  # Nome do departamento já existente no Odoo


def get_or_create_department(conn: OdooConexao, name: str) -> int:
    """Busca ou cria o departamento ``hr.department`` pelo nome.

    Tenta primeiro a busca exata pelo nome. Se não encontrar, faz uma busca
    parcial com ``ilike 'fundi'`` para localizar o departamento de fundição
    mesmo com nome ligeiramente diferente. Se nenhuma busca encontrar resultado,
    cria o departamento com o nome fornecido.

    Args:
        conn: Conexão autenticada com o Odoo.
        name: Nome do departamento a buscar ou criar.

    Returns:
        ID inteiro do ``hr.department`` encontrado ou criado.
    """
    depts = conn.search_read(
        'hr.department',
        dominio=[['name', '=', name]],
        campos=['id', 'name'],
        limite=1
    )
    if depts:
        dept_id = depts[0]['id']
        console.print(f"  [green]Departamento encontrado:[/green] {name} (ID: {dept_id})")
        return dept_id
    
    # Tenta busca parcial
    depts = conn.search_read(
        'hr.department',
        dominio=[['name', 'ilike', 'fundi']],
        campos=['id', 'name'],
        limite=5
    )
    if depts:
        dept_id = depts[0]['id']
        console.print(f"  [green]Departamento encontrado (parcial):[/green] {depts[0]['name']} (ID: {dept_id})")
        return dept_id
    
    # Criar novo
    dept_id = conn.criar('hr.department', {'name': name})
    console.print(f"  [cyan]Departamento criado:[/cyan] {name} (ID: {dept_id})")
    return dept_id


def list_fundidores(conn: OdooConexao, dept_id: int) -> list:
    """Lista todos os funcionários do departamento de fundição.

    Args:
        conn:    Conexão autenticada com o Odoo.
        dept_id: ID do ``hr.department`` do setor de fundição.

    Returns:
        Lista de dicionários com os campos ``id``, ``name``, ``barcode``,
        ``job_title`` e ``active`` dos funcionários do departamento.
    """
    employees = conn.search_read(
        'hr.employee',
        dominio=[['department_id', '=', dept_id]],
        campos=['id', 'name', 'barcode', 'job_title', 'active'],
        limite=500,
        ordem='name'
    )
    return employees


def setup_quality_reasons(conn: OdooConexao, reasons: list[str]) -> dict[str, int]:
    """Cadastra os motivos de não conformidade em ``quality.reason``.

    Para cada nome na lista ``reasons``, verifica se já existe um motivo com
    esse nome (comparação case-insensitive). Se existir, reutiliza; se não,
    cria um novo registro.

    Args:
        conn:    Conexão autenticada com o Odoo.
        reasons: Lista de nomes de motivos de não conformidade a cadastrar.

    Returns:
        Dicionário ``{nome_motivo: id}`` com todos os motivos processados.
    """
    result = {}
    
    # Buscar motivos existentes
    existing = conn.search_read(
        'quality.reason',
        campos=['id', 'name'],
        limite=200
    )
    existing_map = {r['name'].strip().lower(): r['id'] for r in existing}
    
    for reason_name in reasons:
        key = reason_name.strip().lower()
        if key in existing_map:
            result[reason_name] = existing_map[key]
            console.print(f"  [dim]Motivo já existe:[/dim] {reason_name} (ID: {existing_map[key]})")
        else:
            new_id = conn.criar('quality.reason', {'name': reason_name})
            result[reason_name] = new_id
            console.print(f"  [green]Motivo criado:[/green] {reason_name} (ID: {new_id})")
    
    return result


def get_or_create_quality_team(conn: OdooConexao, team_name: str) -> int:
    """Busca ou cria uma equipe de qualidade (``quality.alert.team``).

    Args:
        conn:      Conexão autenticada com o Odoo.
        team_name: Nome exato da equipe de qualidade.

    Returns:
        ID inteiro do ``quality.alert.team`` encontrado ou criado.
    """
    teams = conn.search_read(
        'quality.alert.team',
        dominio=[['name', '=', team_name]],
        campos=['id'],
        limite=1
    )
    if teams:
        team_id = teams[0]['id']
        console.print(f"  [green]Equipe encontrada:[/green] {team_name} (ID: {team_id})")
        return team_id
    
    team_id = conn.criar('quality.alert.team', {'name': team_name})
    console.print(f"  [cyan]Equipe criada:[/cyan] {team_name} (ID: {team_id})")
    return team_id


def create_quality_alert(
    conn: OdooConexao,
    title: str,
    team_id: int,
    reason_id: int,
    employee_name: str = "",
    description: str = "",
    priority: str = "1"
) -> int:
    """Cria um alerta de qualidade (``quality.alert``) para registrar uma não conformidade.

    Args:
        conn:          Conexão autenticada com o Odoo.
        title:         Título do alerta (campo ``name``).
        team_id:       ID da equipe de qualidade responsável.
        reason_id:     ID do motivo de não conformidade (``quality.reason``).
        employee_name: Nome do funcionário associado à NC (opcional).
        description:   Descrição detalhada da NC (opcional).
        priority:      Prioridade em string: ``'0'``=Normal, ``'1'``=Baixa,
                       ``'2'``=Alta, ``'3'``=Muito Alta. Padrão: ``'1'``.

    Returns:
        ID inteiro do ``quality.alert`` criado.
    """
    vals = {
        'name': title,
        'team_id': team_id,
        'reason_id': reason_id,
        'priority': priority,
    }
    if description:
        vals['description'] = description
    
    alert_id = conn.criar('quality.alert', vals)
    return alert_id


def main():
    """Ponto de entrada principal do setup da fundição.

    Conecta ao Odoo e executa as quatro etapas de configuração:

    1. Busca ou cria o departamento definido em :data:`DEPT_NAME`.
    2. Lista e exibe os fundidores do departamento.
    3. Cadastra os motivos de NC da lista :data:`NAO_CONFORMIDADES`.
    4. Busca ou cria a equipe de qualidade "Qualidade Fundição".

    Ao final, exibe um resumo e salva o resultado em
    ``producao/setup_fundicao_result.json``.
    """
    console.print(Panel.fit(
        "[bold white]SETUP FUNDIÇÃO - Odoo[/bold white]\n"
        "Departamento, Fundidores e Não Conformidades",
        border_style="blue"
    ))
    
    conn = criar_conexao()
    
    # ═══════════════════════════════════════
    # 1. DEPARTAMENTO FUNDIÇÃO
    # ═══════════════════════════════════════
    console.print("\n[bold cyan]1. DEPARTAMENTO FUNDIÇÃO[/bold cyan]")
    console.print("-" * 40)
    dept_id = get_or_create_department(conn, DEPT_NAME)
    
    # ═══════════════════════════════════════
    # 2. LISTAR FUNDIDORES
    # ═══════════════════════════════════════
    console.print("\n[bold cyan]2. FUNDIDORES NO SETOR[/bold cyan]")
    console.print("-" * 40)
    fundidores = list_fundidores(conn, dept_id)
    
    if fundidores:
        table = Table(title=f"Fundidores - {DEPT_NAME} ({len(fundidores)} funcionários)")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Badge", style="cyan", width=8)
        table.add_column("Nome", style="white", width=40)
        table.add_column("Cargo", style="yellow", width=35)
        
        for emp in fundidores:
            table.add_row(
                str(emp['id']),
                str(emp.get('barcode', '-')),
                emp['name'],
                emp.get('job_title', '-') or '-'
            )
        console.print(table)
    else:
        console.print("  [yellow]Nenhum funcionário encontrado no setor.[/yellow]")
    
    # ═══════════════════════════════════════
    # 3. NÃO CONFORMIDADES (quality.reason)
    # ═══════════════════════════════════════
    console.print("\n[bold cyan]3. NÃO CONFORMIDADES (MOTIVOS)[/bold cyan]")
    console.print("-" * 40)
    reasons = setup_quality_reasons(conn, NAO_CONFORMIDADES)
    
    # ═══════════════════════════════════════
    # 4. EQUIPE DE QUALIDADE FUNDIÇÃO
    # ═══════════════════════════════════════
    console.print("\n[bold cyan]4. EQUIPE DE QUALIDADE[/bold cyan]")
    console.print("-" * 40)
    team_id = get_or_create_quality_team(conn, "Qualidade Fundição")
    
    # ═══════════════════════════════════════
    # 5. RESUMO
    # ═══════════════════════════════════════
    console.print("\n")
    summary = Table(title="RESUMO DA CONFIGURAÇÃO", show_header=False)
    summary.add_column("Item", style="cyan", width=30)
    summary.add_column("Valor", style="green", width=40)
    summary.add_row("Departamento", f"{DEPT_NAME} (ID: {dept_id})")
    summary.add_row("Fundidores cadastrados", str(len(fundidores)))
    summary.add_row("Não conformidades", str(len(reasons)))
    summary.add_row("Equipe de Qualidade", f"Qualidade Fundição (ID: {team_id})")
    console.print(summary)
    
    console.print("\n[bold green]Setup concluído com sucesso![/bold green]")
    console.print("\n[dim]Para registrar uma não conformidade, use:[/dim]")
    console.print("[dim]  python producao/registrar_nc.py[/dim]")
    
    # Salvar resultado em JSON
    output = {
        'departamento': {'id': dept_id, 'name': DEPT_NAME},
        'fundidores': fundidores,
        'nao_conformidades': reasons,
        'equipe_qualidade': {'id': team_id, 'name': 'Qualidade Fundição'},
    }
    out_path = os.path.join(current_dir, 'setup_fundicao_result.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    console.print(f"\n[dim]Resultado salvo em: {out_path}[/dim]")


if __name__ == "__main__":
    main()
