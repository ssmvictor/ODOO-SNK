# -*- coding: utf-8 -*-
"""
Cria alertas de qualidade (quality.alert) para cada tipo de não conformidade
no setor de Fundição, para que apareçam na visão Kanban de Alertas de Qualidade.
"""

import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao
from rich.console import Console

console = Console()

# Não conformidades da Fundição
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

TEAM_NAME = "Qualidade Fundição"


def main():
    conn = criar_conexao()

    # 1. Buscar equipe Qualidade Fundição
    teams = conn.search_read(
        'quality.alert.team',
        dominio=[['name', '=', TEAM_NAME]],
        campos=['id'],
        limite=1
    )
    if not teams:
        print(f"Equipe '{TEAM_NAME}' nao encontrada!")
        return
    team_id = teams[0]['id']
    print(f"Equipe: {TEAM_NAME} (ID: {team_id})")

    # 2. Buscar motivos (quality.reason)
    reasons = conn.search_read(
        'quality.reason',
        campos=['id', 'name'],
        limite=200
    )
    reason_map = {r['name'].strip(): r['id'] for r in reasons}

    # 3. Verificar alertas já existentes na equipe
    existing_alerts = conn.search_read(
        'quality.alert',
        dominio=[['team_id', '=', team_id]],
        campos=['id', 'name'],
        limite=500
    )
    existing_names = {a['name'] for a in existing_alerts}
    print(f"Alertas existentes na equipe: {len(existing_alerts)}")

    # 4. Criar um alerta para cada não conformidade
    created = 0
    for nc_name in NAO_CONFORMIDADES:
        alert_title = f"NC - {nc_name}"

        if alert_title in existing_names:
            print(f"  [SKIP] {alert_title} (ja existe)")
            continue

        vals = {
            'name': alert_title,
            'team_id': team_id,
            'priority': '1',
        }

        # Vincular ao motivo se existir
        if nc_name in reason_map:
            vals['reason_id'] = reason_map[nc_name]

        try:
            alert_id = conn.criar('quality.alert', vals)
            print(f"  [OK] Criado: {alert_title} (ID: {alert_id})")
            created += 1
        except Exception as e:
            print(f"  [ERRO] {alert_title}: {e}")

    print(f"\nTotal criados: {created}")
    print("Acesse: https://eletroceramica.odoo.com/odoo/quality/2/action-801")


if __name__ == "__main__":
    main()
