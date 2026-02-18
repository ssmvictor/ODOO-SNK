# -*- coding: utf-8 -*-
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loginOdoo.conexao import criar_conexao

conn = criar_conexao()

# Buscar alertas recentes da equipe Qualidade Fundição
alerts = conn.search_read(
    'quality.alert',
    dominio=[['team_id', '=', 2]],
    campos=['id', 'name', 'reason_id', 'x_studio_funcionario'],
    limite=10, ordem='id desc'
)

print("=== Últimos 10 alertas - Qualidade Fundição ===\n")
for a in alerts:
    func = a.get('x_studio_funcionario')
    func_name = func[1] if func else 'N/A'
    reason = a.get('reason_id')
    reason_name = reason[1] if reason else 'N/A'
    print(f"ID: {a['id']} | {a['name']}")
    print(f"   Funcionário: {func_name} | Motivo: {reason_name}")
    print()
