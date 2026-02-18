# -*- coding: utf-8 -*-
import json

with open(r'c:\SANITARIOS GABRIEL\ODOO-SNK\producao\inspect_odoo_result.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Employees in Fundicao
print('=== FUNDIDORES (Dept Fundicao/loucas ID:9) ===')
fundidores = [e for e in data['employees'] if e.get('department_id') and e['department_id']['id'] == 9]
for e in fundidores:
    print(f"ID:{e['id']:4d} | Badge:{e['barcode']:5s} | {e['name']:40s} | {e.get('job_title','-')}")
print(f'Total fundidores: {len(fundidores)}')

# Key quality.alert fields
print()
print('=== KEY QUALITY.ALERT FIELDS ===')
key_names = ['name', 'title', 'product_id', 'product_tmpl_id', 'lot_id', 'team_id', 
             'user_id', 'tag_ids', 'reason_id', 'priority', 'stage_id', 'description',
             'action_corrective', 'action_preventive', 'workcenter_id', 'company_id']
fields = data.get('quality_alert_fields', {})
for k in key_names:
    if k in fields:
        f = fields[k]
        print(f"{k:30s} {f['type']:15s} {f['string']:30s} req:{f.get('required',False)}")

# Quality reasons and teams
print()
print('=== QUALITY REASONS ===')
for r in data.get('quality_reasons', []):
    print(f"  ID:{r['id']} | {r['name']}")

print()
print('=== QUALITY TEAMS ===')
for t in data.get('quality_teams', []):
    print(f"  ID:{t['id']} | {t['name']}")
