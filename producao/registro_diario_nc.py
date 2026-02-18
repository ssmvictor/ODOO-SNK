# -*- coding: utf-8 -*-
"""
Registro Diário de Não Conformidades por Fundidor
===================================================
Registra NCs diárias para cada fundidor do setor Fundição.

Fluxo:
  1. Lista fundidores do setor Fundição/louças
  2. Seleciona o fundidor sendo inspecionado
  3. Mostra tipos de NC disponíveis
  4. Marca as NCs encontradas (múltiplas)
  5. Cria quality.alert para cada NC com nome do fundidor + data
  6. Repete para próximo fundidor ou encerra

Uso: python producao/registro_diario_nc.py
"""

import os
import sys
from datetime import date

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao, OdooConexao
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt, Confirm

console = Console()

TEAM_NAME = "Qualidade Fundição"


def get_fundidores(conn: OdooConexao) -> list[dict]:
    """Busca funcionários do setor Fundição."""
    depts = conn.search_read(
        'hr.department',
        dominio=[['name', 'ilike', 'fundi']],
        campos=['id'], limite=1
    )
    if not depts:
        return []

    return conn.search_read(
        'hr.employee',
        dominio=[['department_id', '=', depts[0]['id']]],
        campos=['id', 'name', 'barcode', 'job_title'],
        limite=500, ordem='name'
    )


def get_reasons(conn: OdooConexao) -> list[dict]:
    """Busca motivos de NC."""
    return conn.search_read(
        'quality.reason', campos=['id', 'name'], limite=200, ordem='name'
    )


def get_team_id(conn: OdooConexao) -> int:
    """Busca ID da equipe Qualidade Fundição."""
    teams = conn.search_read(
        'quality.alert.team',
        dominio=[['name', '=', TEAM_NAME]],
        campos=['id'], limite=1
    )
    return teams[0]['id'] if teams else 0


def show_fundidores_menu(fundidores: list[dict]):
    """Mostra a lista de fundidores."""
    table = Table(title="Fundidores - Fundição/louças", show_lines=False)
    table.add_column("#", style="bold white", width=4, justify="right")
    table.add_column("Badge", style="cyan", width=8)
    table.add_column("Nome", style="white", width=42)
    table.add_column("Cargo", style="yellow", width=32)

    for i, f in enumerate(fundidores, 1):
        table.add_row(
            str(i),
            str(f.get('barcode', '-')),
            f['name'],
            f.get('job_title', '-') or '-'
        )
    console.print(table)


def show_reasons_menu(reasons: list[dict]):
    """Mostra os tipos de NC."""
    console.print("\n[bold]Tipos de Não Conformidade:[/bold]")
    for i, r in enumerate(reasons, 1):
        console.print(f"  [cyan]{i:2d}[/cyan]. {r['name']}")
    console.print(f"  [cyan] 0[/cyan]. [dim]Nenhuma NC (fundidor OK)[/dim]")


def registrar_ncs_fundidor(
    conn: OdooConexao,
    fundidor: dict,
    reasons: list[dict],
    team_id: int,
    data_hoje: str
):
    """Registra NCs para um fundidor específico."""
    console.print(f"\n[bold green]Fundidor: {fundidor['name']} (Badge: {fundidor.get('barcode', '-')})[/bold green]")

    show_reasons_menu(reasons)

    nc_input = Prompt.ask(
        "\n[bold]Quais NCs encontrou? (números separados por vírgula, 0 se nenhuma)[/bold]",
        default="0"
    )

    if nc_input.strip() == "0":
        console.print("[green]  Nenhuma NC registrada - Fundidor OK![/green]")
        return 0

    # Parse seleções
    try:
        indices = [int(x.strip()) for x in nc_input.split(",")]
    except ValueError:
        console.print("[red]  Entrada inválida! Use números separados por vírgula.[/red]")
        return 0

    criados = 0
    for idx in indices:
        if idx < 1 or idx > len(reasons):
            console.print(f"  [red]Número {idx} inválido, ignorado.[/red]")
            continue

        reason = reasons[idx - 1]
        titulo = f"[{data_hoje}] {fundidor['name']} - {reason['name']}"

        vals = {
            'name': titulo,
            'team_id': team_id,
            'reason_id': reason['id'],
            'priority': '1',
            'x_studio_funcionario': fundidor['id'],
            'description': (
                f"Fundidor: {fundidor['name']}\n"
                f"Badge: {fundidor.get('barcode', '-')}\n"
                f"Cargo: {fundidor.get('job_title', '-')}\n"
                f"Data da inspeção: {data_hoje}\n"
                f"Não conformidade: {reason['name']}"
            ),
        }

        try:
            alert_id = conn.criar('quality.alert', vals)
            console.print(f"  [green]✓[/green] {reason['name']} (Alerta ID: {alert_id})")
            criados += 1
        except Exception as e:
            console.print(f"  [red]✗ Erro ao criar {reason['name']}: {e}[/red]")

    return criados


def main():
    data_hoje = date.today().strftime("%Y-%m-%d")

    console.print(Panel.fit(
        f"[bold white]REGISTRO DIÁRIO DE NÃO CONFORMIDADES[/bold white]\n"
        f"Setor: Fundição/louças | Data: [cyan]{data_hoje}[/cyan]",
        border_style="blue"
    ))

    conn = criar_conexao()

    # Carregar dados
    fundidores = get_fundidores(conn)
    if not fundidores:
        console.print("[red]Nenhum fundidor encontrado no setor![/red]")
        return

    reasons = get_reasons(conn)
    if not reasons:
        console.print("[red]Nenhum motivo de NC cadastrado![/red]")
        return

    team_id = get_team_id(conn)
    if not team_id:
        console.print("[red]Equipe 'Qualidade Fundição' não encontrada![/red]")
        return

    total_ncs = 0
    fundidores_inspecionados = 0

    while True:
        console.print("\n" + "=" * 60)
        show_fundidores_menu(fundidores)

        console.print(f"\n[dim]Total já: {fundidores_inspecionados} fundidores inspecionados, {total_ncs} NCs registradas[/dim]")

        escolha = Prompt.ask(
            "\n[bold]Número do fundidor (ou 'sair' para encerrar)[/bold]",
            default="sair"
        )

        if escolha.lower() in ('sair', 's', 'exit', 'q', ''):
            break

        try:
            idx = int(escolha)
        except ValueError:
            console.print("[red]Entrada inválida![/red]")
            continue

        if idx < 1 or idx > len(fundidores):
            console.print(f"[red]Número deve ser entre 1 e {len(fundidores)}[/red]")
            continue

        fundidor = fundidores[idx - 1]
        ncs = registrar_ncs_fundidor(conn, fundidor, reasons, team_id, data_hoje)
        total_ncs += ncs
        fundidores_inspecionados += 1

        if not Confirm.ask("\n[bold]Inspecionar outro fundidor?[/bold]", default=True):
            break

    # Resumo final
    console.print("\n")
    console.print(Panel.fit(
        f"[bold white]RESUMO DO DIA {data_hoje}[/bold white]\n\n"
        f"Fundidores inspecionados: [cyan]{fundidores_inspecionados}[/cyan]\n"
        f"Total de NCs registradas: [{'red' if total_ncs > 0 else 'green'}]{total_ncs}[/{'red' if total_ncs > 0 else 'green'}]",
        border_style="green"
    ))

    console.print("\n[dim]Veja os alertas em: https://eletroceramica.odoo.com/odoo/quality/2/action-801[/dim]")


if __name__ == "__main__":
    main()
