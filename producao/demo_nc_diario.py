# -*- coding: utf-8 -*-
"""
Cria exemplos de registro diário de NC para demonstrar como funciona.
Simula inspeção de 3 fundidores com diferentes NCs.
"""
import os, sys
from datetime import date

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def main():
    conn = criar_conexao()
    data_hoje = date.today().strftime("%Y-%m-%d")

    # Buscar equipe
    teams = conn.search_read('quality.alert.team', dominio=[['name', '=', 'Qualidade Fundição']], campos=['id'], limite=1)
    team_id = teams[0]['id']

    # Buscar motivos
    reasons = conn.search_read('quality.reason', campos=['id', 'name'], limite=200)
    reason_map = {r['name']: r['id'] for r in reasons}

    # Buscar alguns fundidores
    depts = conn.search_read('hr.department', dominio=[['name', 'ilike', 'fundi']], campos=['id'], limite=1)
    dept_id = depts[0]['id']
    fundidores = conn.search_read(
        'hr.employee', dominio=[['department_id', '=', dept_id]],
        campos=['id', 'name', 'barcode', 'job_title'], limite=5, ordem='name'
    )

    # Simular inspeções
    exemplos = [
        # (indice_fundidor, [lista_de_NCs])
        (0, ["Bolhas", "Trincas"]),
        (1, ["Porosidade"]),
        (2, ["Deformação", "Rebarbas", "Manchas"]),
    ]

    created = 0
    for idx, ncs in exemplos:
        if idx >= len(fundidores):
            continue
        f = fundidores[idx]
        for nc_name in ncs:
            reason_id = reason_map.get(nc_name)
            if not reason_id:
                print(f"  Motivo '{nc_name}' nao encontrado, pulando.")
                continue

            titulo = f"[{data_hoje}] {f['name']} - {nc_name}"
            vals = {
                'name': titulo,
                'team_id': team_id,
                'reason_id': reason_id,
                'priority': '1',
                'description': (
                    f"Fundidor: {f['name']}\n"
                    f"Badge: {f.get('barcode', '-')}\n"
                    f"Cargo: {f.get('job_title', '-')}\n"
                    f"Data da inspeção: {data_hoje}\n"
                    f"Não conformidade: {nc_name}"
                ),
            }
            alert_id = conn.criar('quality.alert', vals)
            print(f"  [OK] {titulo} (ID: {alert_id})")
            created += 1

    print(f"\nTotal criados: {created} alertas de exemplo")
    print("Acesse: https://eletroceramica.odoo.com/odoo/quality/2/action-801")

if __name__ == "__main__":
    main()
