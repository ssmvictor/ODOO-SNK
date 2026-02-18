# -*- coding: utf-8 -*-
"""Inspeciona dados do Odoo: modulos qualidade, departamentos, funcionarios."""
import os, sys, json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def main():
    conn = criar_conexao()
    result = {}

    # 1. Quality modules
    mods = conn.search_read(
        'ir.module.module',
        dominio=[['name', 'in', ['quality', 'quality_control', 'quality_mrp']]],
        campos=['name', 'shortdesc', 'state'],
        limite=20
    )
    result['quality_modules'] = mods

    # 2. All departments
    depts = conn.search_read(
        'hr.department', campos=['id', 'name'], limite=100, ordem='name'
    )
    result['departments'] = depts

    # 3. Employees
    emps = conn.search_read(
        'hr.employee',
        campos=['id', 'name', 'barcode', 'department_id', 'job_title'],
        limite=500, ordem='name'
    )
    # Simplify department_id
    for e in emps:
        if e.get('department_id'):
            e['department_id'] = {'id': e['department_id'][0], 'name': e['department_id'][1]}
        else:
            e['department_id'] = None
    result['employees'] = emps
    result['employee_count'] = len(emps)

    # 4. If quality is installed, check quality.alert fields
    installed_quality = [m for m in mods if m.get('state') == 'installed']
    if installed_quality:
        try:
            fields = conn.executar("quality.alert", "fields_get", args=[[]])
            key_fields = {}
            for fname, fprops in fields.items():
                key_fields[fname] = {
                    'type': fprops.get('type'),
                    'string': fprops.get('string'),
                    'required': fprops.get('required', False)
                }
            result['quality_alert_fields'] = key_fields
        except Exception as e:
            result['quality_alert_error'] = str(e)

        try:
            reasons = conn.search_read('quality.reason', campos=['id', 'name'], limite=100)
            result['quality_reasons'] = reasons
        except Exception as e:
            result['quality_reasons_error'] = str(e)

        try:
            teams = conn.search_read('quality.alert.team', campos=['id', 'name'], limite=100)
            result['quality_teams'] = teams
        except Exception as e:
            result['quality_teams_error'] = str(e)

    # Write output
    out_path = os.path.join(current_dir, 'inspect_odoo_result.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"Output saved to {out_path}")

if __name__ == "__main__":
    main()
