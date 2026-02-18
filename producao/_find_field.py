# -*- coding: utf-8 -*-
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from loginOdoo.conexao import criar_conexao

conn = criar_conexao()
odoo = conn._odoo
fields = odoo.env['quality.alert'].fields_get()

for k, v in sorted(fields.items()):
    if k.startswith('x_') or 'employee' in k.lower():
        print(f"{k}: string={v.get('string')} | type={v.get('type')} | relation={v.get('relation','')}")
