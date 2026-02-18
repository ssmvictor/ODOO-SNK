# -*- coding: utf-8 -*-
"""
Verifica os campos do quality.alert, incluindo o novo campo Funcionário
adicionado via Studio.
"""
import os, sys, json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def main():
    conn = criar_conexao()
    odoo = conn._odoo

    # Buscar todos os campos que contêm "employee" ou "funcionario" ou "x_"
    fields = odoo.env['quality.alert'].fields_get()
    
    custom_fields = {}
    employee_fields = {}
    
    for fname, finfo in fields.items():
        # Campos customizados (Studio cria com prefixo x_)
        if fname.startswith('x_'):
            custom_fields[fname] = {
                'type': finfo.get('type'),
                'string': finfo.get('string'),
                'relation': finfo.get('relation', ''),
                'required': finfo.get('required', False),
            }
        # Campos com "employee" no nome
        if 'employee' in fname.lower() or 'funcionario' in fname.lower():
            employee_fields[fname] = {
                'type': finfo.get('type'),
                'string': finfo.get('string'),
                'relation': finfo.get('relation', ''),
                'required': finfo.get('required', False),
            }
    
    print("=== CAMPOS CUSTOMIZADOS (x_) ===")
    print(json.dumps(custom_fields, indent=2, ensure_ascii=False))
    
    print("\n=== CAMPOS EMPLOYEE/FUNCIONÁRIO ===")
    print(json.dumps(employee_fields, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
