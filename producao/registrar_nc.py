# -*- coding: utf-8 -*-
"""
Registrar Não Conformidade (NC) na Fundição
=============================================
Cria um alerta de qualidade (``quality.alert``) no Odoo para registrar
erros/defeitos durante a produção no setor de Fundição.

Modos de uso:

- **Interativo** (sem argumentos): apresenta menus para selecionar motivo,
  fundidor, título, descrição e prioridade.
- **Direto** (com ``--titulo`` e ``--motivo``): registra a NC diretamente
  via linha de comando, sem interação.
- **Listagem** (com ``--listar``): exibe as últimas NCs registradas.

Uso interativo::

    python producao/registrar_nc.py

Uso direto::

    python producao/registrar_nc.py --titulo "Bolhas na peça X" --motivo "Bolhas" --prioridade 2

Listar NCs::

    python producao/registrar_nc.py --listar
"""

import os
import sys
import argparse

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao, OdooConexao
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt

console = Console()


def get_quality_reasons(conn: OdooConexao) -> list[dict]:
    """Busca todos os motivos de não conformidade cadastrados (``quality.reason``).

    Args:
        conn: Conexão autenticada com o Odoo.

    Returns:
        Lista de dicionários com ``id`` e ``name`` dos motivos, ordenados por nome.
    """
    return conn.search_read(
        'quality.reason',
        campos=['id', 'name'],
        limite=200,
        ordem='name'
    )


def get_quality_team(conn: OdooConexao, team_name: str = "Qualidade Fundição") -> int:
    """Busca a equipe de qualidade da Fundição (``quality.alert.team``).

    Tenta busca por ``ilike team_name``. Se não encontrar, utiliza qualquer
    equipe disponível como fallback.

    Args:
        conn:      Conexão autenticada com o Odoo.
        team_name: Nome (parcial) da equipe a buscar. Padrão: ``'Qualidade Fundição'``.

    Returns:
        ID inteiro da equipe encontrada, ou ``0`` se nenhuma equipe existir.
    """
    teams = conn.search_read(
        'quality.alert.team',
        dominio=[['name', 'ilike', team_name]],
        campos=['id', 'name'],
        limite=1
    )
    if teams:
        return teams[0]['id']
    
    # Fallback: Main Quality Team
    teams = conn.search_read(
        'quality.alert.team',
        campos=['id', 'name'],
        limite=1
    )
    return teams[0]['id'] if teams else 0


def get_employees_fundicao(conn: OdooConexao) -> list[dict]:
    """Busca os funcionários do setor de Fundição (``hr.employee``).

    Localiza o departamento cujo nome contém ``'fundi'`` (case-insensitive)
    e retorna todos os funcionários vinculados a ele.

    Args:
        conn: Conexão autenticada com o Odoo.

    Returns:
        Lista de dicionários com ``id``, ``name`` e ``barcode`` dos funcionários,
        ordenados por nome. Retorna lista vazia se o departamento não for encontrado.
    """
    depts = conn.search_read(
        'hr.department',
        dominio=[['name', 'ilike', 'fundi']],
        campos=['id'],
        limite=1
    )
    if not depts:
        return []
    
    return conn.search_read(
        'hr.employee',
        dominio=[['department_id', '=', depts[0]['id']]],
        campos=['id', 'name', 'barcode'],
        limite=500,
        ordem='name'
    )


def interactive_mode(conn: OdooConexao):
    """Modo interativo para registrar uma não conformidade passo a passo.

    Exibe os motivos disponíveis e os fundidores do setor, solicita dados
    via prompts ``rich`` (motivo, fundidor, título, descrição, prioridade)
    e cria o ``quality.alert`` no Odoo.

    Args:
        conn: Conexão autenticada com o Odoo.
    """
    console.print("\n[bold cyan]REGISTRAR NÃO CONFORMIDADE - FUNDIÇÃO[/bold cyan]")
    console.print("=" * 50)
    
    # Listar motivos
    reasons = get_quality_reasons(conn)
    console.print("\n[bold]Motivos disponíveis:[/bold]")
    for i, r in enumerate(reasons, 1):
        console.print(f"  {i:2d}. {r['name']}")
    
    # Selecionar motivo
    reason_idx = IntPrompt.ask(
        "\nSelecione o motivo (número)", 
        default=1
    )
    if reason_idx < 1 or reason_idx > len(reasons):
        console.print("[red]Motivo inválido![/red]")
        return
    selected_reason = reasons[reason_idx - 1]
    
    # Listar fundidores
    employees = get_employees_fundicao(conn)
    if employees:
        console.print("\n[bold]Fundidores:[/bold]")
        for i, e in enumerate(employees, 1):
            console.print(f"  {i:2d}. [{e.get('barcode', '-')}] {e['name']}")
        
        emp_idx = IntPrompt.ask(
            "\nSelecione o fundidor (número, 0 para nenhum)", 
            default=0
        )
        selected_employee = employees[emp_idx - 1] if 0 < emp_idx <= len(employees) else None
    else:
        selected_employee = None
    
    # Título
    titulo = Prompt.ask("\nTítulo da NC", default=f"NC Fundição - {selected_reason['name']}")
    
    # Descrição
    descricao = Prompt.ask("Descrição (opcional)", default="")
    
    # Prioridade
    console.print("\nPrioridades: 0=Normal, 1=Baixa, 2=Alta, 3=Muito Alta")
    prioridade = Prompt.ask("Prioridade", choices=["0", "1", "2", "3"], default="1")
    
    # Criar alerta
    team_id = get_quality_team(conn)
    
    vals = {
        'name': titulo,
        'team_id': team_id,
        'reason_id': selected_reason['id'],
        'priority': prioridade,
    }
    
    if descricao:
        vals['description'] = descricao
    
    if selected_employee:
        vals['description'] = (vals.get('description', '') + 
                              f"\nFundidor: {selected_employee['name']} (Badge: {selected_employee.get('barcode', '-')})").strip()
    
    try:
        alert_id = conn.criar('quality.alert', vals)
        console.print(f"\n[bold green]NC registrada com sucesso! ID: {alert_id}[/bold green]")
        console.print(f"  Título: {titulo}")
        console.print(f"  Motivo: {selected_reason['name']}")
        if selected_employee:
            console.print(f"  Fundidor: {selected_employee['name']}")
        console.print(f"  Prioridade: {prioridade}")
    except Exception as e:
        console.print(f"\n[bold red]Erro ao criar NC: {e}[/bold red]")


def direct_mode(conn: OdooConexao, titulo: str, motivo: str, prioridade: str = "1", descricao: str = ""):
    """Registra uma não conformidade diretamente via argumentos de linha de comando.

    Busca o motivo pelo nome exato (case-insensitive). Se não encontrar,
    lista os motivos disponíveis e encerra sem criar o alerta.

    Args:
        conn:       Conexão autenticada com o Odoo.
        titulo:     Título do alerta de qualidade.
        motivo:     Nome exato do ``quality.reason`` a utilizar.
        prioridade: Prioridade em string (``'0'``–``'3'``). Padrão: ``'1'``.
        descricao:  Descrição opcional da NC.
    """
    # Buscar motivo por nome
    reasons = get_quality_reasons(conn)
    reason_match = [r for r in reasons if r['name'].lower() == motivo.lower()]
    
    if not reason_match:
        console.print(f"[red]Motivo '{motivo}' não encontrado![/red]")
        console.print("Motivos disponíveis:")
        for r in reasons:
            console.print(f"  - {r['name']}")
        return
    
    team_id = get_quality_team(conn)
    
    vals = {
        'name': titulo,
        'team_id': team_id,
        'reason_id': reason_match[0]['id'],
        'priority': prioridade,
    }
    if descricao:
        vals['description'] = descricao
    
    try:
        alert_id = conn.criar('quality.alert', vals)
        console.print(f"[bold green]NC registrada! ID: {alert_id}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Erro: {e}[/bold red]")


def list_ncs(conn: OdooConexao, limit: int = 20):
    """Exibe as últimas NCs registradas em uma tabela ``rich``.

    Args:
        conn:  Conexão autenticada com o Odoo.
        limit: Número máximo de NCs a exibir (padrão: ``20``).
    """
    alerts = conn.search_read(
        'quality.alert',
        campos=['id', 'name', 'reason_id', 'priority', 'stage_id', 'create_date'],
        limite=limit,
        ordem='create_date desc'
    )
    
    if not alerts:
        console.print("[yellow]Nenhuma NC encontrada.[/yellow]")
        return
    
    table = Table(title=f"Últimas {len(alerts)} Não Conformidades")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Título", style="white", width=35)
    table.add_column("Motivo", style="cyan", width=25)
    table.add_column("Prioridade", style="yellow", width=12)
    table.add_column("Estágio", style="green", width=15)
    table.add_column("Data", style="dim", width=20)
    
    priority_map = {'0': 'Normal', '1': 'Baixa', '2': 'Alta', '3': 'Muito Alta'}
    
    for a in alerts:
        reason = a['reason_id'][1] if a.get('reason_id') else '-'
        stage = a['stage_id'][1] if a.get('stage_id') else '-'
        pri = priority_map.get(str(a.get('priority', '0')), str(a.get('priority', '-')))
        table.add_row(
            str(a['id']),
            a.get('name', '-'),
            reason,
            pri,
            stage,
            str(a.get('create_date', '-'))
        )
    
    console.print(table)


def main():
    """Ponto de entrada principal do registro de não conformidades.

    Processa os argumentos de linha de comando e despacha para o modo adequado:

    - ``--listar``: chama :func:`list_ncs`.
    - ``--titulo`` + ``--motivo``: chama :func:`direct_mode`.
    - Sem argumentos: chama :func:`interactive_mode`.

    Conecta ao Odoo antes de chamar qualquer modo.
    """
    parser = argparse.ArgumentParser(description="Registrar Não Conformidade na Fundição")
    parser.add_argument('--titulo', '-t', help='Título da NC')
    parser.add_argument('--motivo', '-m', help='Nome do motivo (quality.reason)')
    parser.add_argument('--prioridade', '-p', default='1', choices=['0', '1', '2', '3'],
                       help='Prioridade: 0=Normal, 1=Baixa, 2=Alta, 3=Muito Alta')
    parser.add_argument('--descricao', '-d', default='', help='Descrição da NC')
    parser.add_argument('--listar', '-l', action='store_true', help='Listar últimas NCs')
    
    args = parser.parse_args()
    
    conn = criar_conexao()
    
    if args.listar:
        list_ncs(conn)
    elif args.titulo and args.motivo:
        direct_mode(conn, args.titulo, args.motivo, args.prioridade, args.descricao)
    else:
        interactive_mode(conn)


if __name__ == "__main__":
    main()
