# -*- coding: utf-8 -*-
"""
Teste: cria 1 alerta com o campo x_studio_funcionario preenchido.
"""
import os, sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loginOdoo.conexao import criar_conexao

conn = criar_conexao()

# Pegar um fundidor qualquer (primeiro da lista Fundição)
depts = conn.search_read('hr.department', dominio=[['name', 'ilike', 'fundi']], campos=['id'], limite=1)
fund = conn.search_read('hr.employee', dominio=[['department_id', '=', depts[0]['id']]], campos=['id', 'name', 'barcode', 'job_title'], limite=1, ordem='name')

# Pegar um motivo de NC
reasons = conn.search_read('quality.reason', dominio=[['name', '=', 'Bolhas']], campos=['id', 'name'], limite=1)

# Pegar a equipe
teams = conn.search_read('quality.alert.team', dominio=[['name', '=', 'Qualidade Fundição']], campos=['id'], limite=1)

agora = datetime.now()
data_hoje = agora.strftime("%Y-%m-%d")
hora = agora.strftime("%H:%M")

fundidor = fund[0]
reason = reasons[0]
team_id = teams[0]['id']

titulo = f"[{data_hoje} {hora}] {fundidor['name']} - {reason['name']}"

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
        f"Data da inspeção: {data_hoje} {hora}\n"
        f"Não conformidade: {reason['name']}"
    ),
}

alert_id = conn.criar('quality.alert', vals)
print(f"Alerta criado com sucesso! ID: {alert_id}")
print(f"Título: {titulo}")
print(f"Funcionário ID: {fundidor['id']} ({fundidor['name']})")
print(f"Verifique em: https://eletroceramica.odoo.com/odoo/quality/2/action-801")
