# -*- coding: utf-8 -*-
"""
Limpa os alertas genéricos criados anteriormente (NC - Bolhas, NC - Trincas, etc.)
da equipe Qualidade Fundição.
"""
import os, sys

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def main():
    conn = criar_conexao()

    # Buscar alertas genéricos na equipe Qualidade Fundição
    teams = conn.search_read(
        'quality.alert.team',
        dominio=[['name', '=', 'Qualidade Fundição']],
        campos=['id'], limite=1
    )
    if not teams:
        print("Equipe nao encontrada")
        return

    team_id = teams[0]['id']

    alerts = conn.search_read(
        'quality.alert',
        dominio=[['team_id', '=', team_id], ['name', 'like', 'NC - ']],
        campos=['id', 'name'],
        limite=500
    )

    if not alerts:
        print("Nenhum alerta generico encontrado para limpar.")
        return

    print(f"Encontrados {len(alerts)} alertas genericos para remover:")
    for a in alerts:
        print(f"  ID:{a['id']} | {a['name']}")

    ids = [a['id'] for a in alerts]
    try:
        conn.excluir('quality.alert', ids)
        print(f"Removidos {len(ids)} alertas genericos.")
    except Exception as e:
        print(f"Erro ao excluir: {e}")
        # Tentar arquivar se não pode excluir
        try:
            conn.atualizar('quality.alert', ids, {'active': False})
            print("Alertas arquivados.")
        except Exception as e2:
            print(f"Erro ao arquivar: {e2}")

if __name__ == "__main__":
    main()
