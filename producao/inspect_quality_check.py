# -*- coding: utf-8 -*-
"""
Investiga os modelos de quality.check e quality.point do Odoo
para entender como configurar inspeções por fundidor.
"""
import os, sys, json

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao

def main():
    conn = criar_conexao()
    odoo = conn._odoo

    result = {}

    # 1. Verificar campos do quality.check
    try:
        fields = odoo.env['quality.check'].fields_get()
        important_fields = {}
        for fname, finfo in fields.items():
            if fname.startswith('_') or fname in ('create_uid', 'write_uid', 'create_date', 'write_date', 'message_ids', 'activity_ids'):
                continue
            important_fields[fname] = {
                'type': finfo.get('type'),
                'string': finfo.get('string'),
                'required': finfo.get('required', False),
                'relation': finfo.get('relation', ''),
            }
        result['quality_check_fields'] = important_fields
    except Exception as e:
        result['quality_check_error'] = str(e)

    # 2. Verificar campos do quality.point
    try:
        fields = odoo.env['quality.point'].fields_get()
        important_fields = {}
        for fname, finfo in fields.items():
            if fname.startswith('_') or fname in ('create_uid', 'write_uid', 'create_date', 'write_date', 'message_ids', 'activity_ids'):
                continue
            important_fields[fname] = {
                'type': finfo.get('type'),
                'string': finfo.get('string'),
                'required': finfo.get('required', False),
                'relation': finfo.get('relation', ''),
            }
        result['quality_point_fields'] = important_fields
    except Exception as e:
        result['quality_point_error'] = str(e)

    # 3. Verificar quality.check existentes
    try:
        checks = conn.search_read('quality.check', campos=['id', 'name', 'quality_state', 'point_id', 'team_id'], limite=10)
        result['existing_checks'] = checks
    except Exception as e:
        result['existing_checks_error'] = str(e)

    # 4. Verificar quality.point existentes
    try:
        points = conn.search_read('quality.point', campos=['id', 'name', 'title', 'test_type_id', 'team_id', 'product_ids'], limite=10)
        result['existing_points'] = points
    except Exception as e:
        result['existing_points_error'] = str(e)

    # 5. Verificar test_type options
    try:
        test_types = conn.search_read('quality.point.test_type', campos=['id', 'name', 'technical_name'], limite=50)
        result['test_types'] = test_types
    except Exception as e:
        result['test_types_error'] = str(e)

    with open(os.path.join(current_dir, 'quality_check_inspect.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print("Resultado salvo em quality_check_inspect.json")

if __name__ == "__main__":
    main()
