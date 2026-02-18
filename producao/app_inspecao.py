# -*- coding: utf-8 -*-
"""
Inspeção de Fundição - Interface Web
======================================
Aplicação Flask para registro de não conformidades por fundidor.
Fluxo visual com checkboxes, data/hora automática.

Uso: python producao/app_inspecao.py
Acesse: http://localhost:5050
"""

import os
import sys
import json
from datetime import datetime

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
from loginOdoo.conexao import criar_conexao, OdooConexao

app = Flask(__name__)

# Conexão global (lazy)
_conn = None

def get_conn() -> OdooConexao:
    global _conn
    if _conn is None or not _conn.conectado:
        _conn = criar_conexao()
    return _conn


def get_fundidores():
    conn = get_conn()
    depts = conn.search_read('hr.department', dominio=[['name', 'ilike', 'fundi']], campos=['id'], limite=1)
    if not depts:
        return []
    return conn.search_read(
        'hr.employee', dominio=[['department_id', '=', depts[0]['id']]],
        campos=['id', 'name', 'barcode', 'job_title'], limite=500, ordem='name'
    )


def get_reasons():
    conn = get_conn()
    return conn.search_read('quality.reason', campos=['id', 'name'], limite=200, ordem='name')


def get_team_id():
    conn = get_conn()
    teams = conn.search_read('quality.alert.team', dominio=[['name', '=', 'Qualidade Fundição']], campos=['id'], limite=1)
    return teams[0]['id'] if teams else 0


def get_recent_alerts(limit=30):
    conn = get_conn()
    team_id = get_team_id()
    return conn.search_read(
        'quality.alert',
        dominio=[['team_id', '=', team_id]],
        campos=['id', 'name', 'reason_id', 'priority', 'stage_id', 'create_date'],
        limite=limit, ordem='create_date desc'
    )


# ═══════════════════════════════════════
# HTML TEMPLATE
# ═══════════════════════════════════════
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Inspeção Fundição - Não Conformidades</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-dark: #0f0f1a;
            --bg-card: #1a1a2e;
            --bg-card-hover: #1f1f35;
            --accent: #6c63ff;
            --accent-glow: rgba(108, 99, 255, 0.3);
            --accent-light: #8b83ff;
            --success: #00d97e;
            --success-glow: rgba(0, 217, 126, 0.3);
            --danger: #ff4757;
            --danger-glow: rgba(255, 71, 87, 0.2);
            --warning: #ffa502;
            --text: #e8e8f0;
            --text-dim: #8888a0;
            --border: #2a2a45;
            --checkbox-size: 24px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Inter', sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
        }

        /* Header */
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-bottom: 1px solid var(--border);
            padding: 20px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent) 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header .datetime {
            font-size: 0.9rem;
            color: var(--text-dim);
            background: var(--bg-dark);
            padding: 8px 16px;
            border-radius: 8px;
            font-weight: 500;
        }
        .header .datetime span { color: var(--accent-light); font-weight: 600; }

        /* Nav tabs */
        .nav-tabs {
            display: flex;
            gap: 0;
            background: var(--bg-card);
            border-bottom: 1px solid var(--border);
        }
        .nav-tab {
            padding: 14px 32px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            color: var(--text-dim);
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
            text-decoration: none;
        }
        .nav-tab:hover { color: var(--text); background: var(--bg-card-hover); }
        .nav-tab.active { color: var(--accent-light); border-bottom-color: var(--accent); }

        /* Main container */
        .container { max-width: 1200px; margin: 0 auto; padding: 30px 20px; }

        /* Step indicator */
        .steps {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 30px;
        }
        .step {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
        }
        .step.active { background: var(--accent); color: white; }
        .step.done { background: var(--success); color: white; }
        .step.pending { background: var(--bg-card); color: var(--text-dim); border: 1px solid var(--border); }
        .step-line { width: 30px; height: 2px; background: var(--border); }
        .step-num {
            width: 24px; height: 24px; border-radius: 50%; display: flex;
            align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 700;
        }

        /* Fundidor Grid */
        .fundidor-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 12px;
        }
        .fundidor-card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 20px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .fundidor-card:hover {
            border-color: var(--accent);
            box-shadow: 0 0 20px var(--accent-glow);
            transform: translateY(-2px);
        }
        .fundidor-card.selected {
            border-color: var(--accent);
            background: rgba(108, 99, 255, 0.1);
            box-shadow: 0 0 25px var(--accent-glow);
        }
        .fundidor-avatar {
            width: 44px; height: 44px; border-radius: 10px;
            background: linear-gradient(135deg, var(--accent) 0%, #a78bfa 100%);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.1rem; font-weight: 700; color: white;
            flex-shrink: 0;
        }
        .fundidor-info { flex: 1; min-width: 0; }
        .fundidor-name { font-weight: 600; font-size: 0.85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .fundidor-meta { font-size: 0.75rem; color: var(--text-dim); margin-top: 2px; }

        /* NC Checklist */
        .nc-section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 24px;
            margin-top: 20px;
        }
        .nc-section h2 {
            font-size: 1.1rem; font-weight: 600; margin-bottom: 6px;
        }
        .nc-section .subtitle { font-size: 0.85rem; color: var(--text-dim); margin-bottom: 20px; }

        .nc-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 10px;
        }
        .nc-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 14px 18px;
            background: var(--bg-dark);
            border: 1px solid var(--border);
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            user-select: none;
        }
        .nc-item:hover {
            border-color: var(--danger);
            background: var(--danger-glow);
        }
        .nc-item.checked {
            border-color: var(--danger);
            background: var(--danger-glow);
            box-shadow: 0 0 15px var(--danger-glow);
        }

        .nc-checkbox {
            width: var(--checkbox-size);
            height: var(--checkbox-size);
            border: 2px solid var(--border);
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: all 0.2s;
        }
        .nc-item.checked .nc-checkbox {
            background: var(--danger);
            border-color: var(--danger);
        }
        .nc-item.checked .nc-checkbox::after {
            content: '✓';
            color: white;
            font-weight: 700;
            font-size: 14px;
        }
        .nc-label { font-size: 0.9rem; font-weight: 500; }
        .nc-count {
            margin-left: auto;
            font-size: 0.75rem;
            color: var(--text-dim);
            background: var(--bg-card);
            padding: 2px 8px;
            border-radius: 10px;
        }
        .nc-item.checked .nc-count { background: var(--danger); color: white; }

        /* Submit area */
        .submit-area {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 24px;
            padding-top: 20px;
            border-top: 1px solid var(--border);
        }
        .selected-count {
            font-size: 0.9rem;
            color: var(--text-dim);
        }
        .selected-count span { color: var(--danger); font-weight: 700; font-size: 1.2rem; }

        .btn {
            padding: 12px 32px;
            border: none;
            border-radius: 10px;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--accent) 0%, #8b83ff 100%);
            color: white;
            box-shadow: 0 4px 15px var(--accent-glow);
        }
        .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 20px var(--accent-glow); }
        .btn-primary:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
        .btn-success {
            background: linear-gradient(135deg, var(--success) 0%, #00b368 100%);
            color: white;
        }
        .btn-outline {
            background: transparent;
            color: var(--text-dim);
            border: 1px solid var(--border);
        }
        .btn-outline:hover { border-color: var(--accent); color: var(--accent-light); }
        .btn-nenhuma {
            background: linear-gradient(135deg, var(--success) 0%, #00b368 100%);
            color: white;
            box-shadow: 0 4px 15px var(--success-glow);
        }

        /* Success notification */
        .toast {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 16px 24px;
            border-radius: 12px;
            font-weight: 500;
            font-size: 0.9rem;
            z-index: 1000;
            animation: slideIn 0.3s ease;
            display: none;
        }
        .toast.success { background: var(--success); color: white; }
        .toast.error { background: var(--danger); color: white; }
        @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }

        /* History table */
        .history-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
        }
        .history-table th {
            padding: 12px 16px;
            text-align: left;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-dim);
            border-bottom: 1px solid var(--border);
        }
        .history-table td {
            padding: 12px 16px;
            font-size: 0.85rem;
            border-bottom: 1px solid rgba(42, 42, 69, 0.5);
        }
        .history-table tr:hover td { background: var(--bg-card-hover); }
        .badge {
            padding: 3px 10px;
            border-radius: 6px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .badge-new { background: rgba(108, 99, 255, 0.2); color: var(--accent-light); }

        /* Search */
        .search-box {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid var(--border);
            border-radius: 10px;
            background: var(--bg-dark);
            color: var(--text);
            font-family: 'Inter', sans-serif;
            font-size: 0.9rem;
            margin-bottom: 16px;
            outline: none;
            transition: border-color 0.2s;
        }
        .search-box:focus { border-color: var(--accent); box-shadow: 0 0 10px var(--accent-glow); }
        .search-box::placeholder { color: var(--text-dim); }

        .hidden { display: none !important; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚙️ Inspeção de Fundição</h1>
        <div class="datetime">
            <span id="clock"></span>
        </div>
    </div>

    <div class="nav-tabs">
        <a class="nav-tab active" href="/" id="tab-inspecao">📋 Nova Inspeção</a>
        <a class="nav-tab" href="/historico" id="tab-historico">📊 Histórico</a>
    </div>

    <div class="toast" id="toast"></div>

    <div class="container">
        {% if page == 'inspecao' %}

        <!-- STEP INDICATOR -->
        <div class="steps">
            <div class="step {{ 'active' if not selected_fundidor else 'done' }}" id="step1">
                <div class="step-num">1</div> Selecionar Fundidor
            </div>
            <div class="step-line"></div>
            <div class="step {{ 'active' if selected_fundidor else 'pending' }}" id="step2">
                <div class="step-num">2</div> Marcar Não Conformidades
            </div>
            <div class="step-line"></div>
            <div class="step pending" id="step3">
                <div class="step-num">3</div> Registrar
            </div>
        </div>

        {% if not selected_fundidor %}
        <!-- STEP 1: SELECT FUNDIDOR -->
        <input type="text" class="search-box" placeholder="🔍 Buscar fundidor por nome ou badge..." 
               oninput="filterFundidores(this.value)" autofocus>
        
        <div class="fundidor-grid" id="fundidorGrid">
            {% for f in fundidores %}
            <a href="/inspecao/{{ f.id }}" class="fundidor-card" data-name="{{ f.name }}" data-badge="{{ f.barcode }}">
                <div class="fundidor-avatar">{{ f.name[0] }}</div>
                <div class="fundidor-info">
                    <div class="fundidor-name">{{ f.name }}</div>
                    <div class="fundidor-meta">Badge: {{ f.barcode or '-' }} · {{ f.job_title or '-' }}</div>
                </div>
            </a>
            {% endfor %}
        </div>

        {% else %}
        <!-- STEP 2: CHECK NCS -->
        <div class="nc-section">
            <div style="display:flex; align-items:center; gap:16px; margin-bottom:4px;">
                <a href="/" class="btn btn-outline" style="padding:8px 16px; font-size:0.8rem;">← Voltar</a>
                <div>
                    <h2>{{ selected_fundidor.name }}</h2>
                    <div class="subtitle">Badge: {{ selected_fundidor.barcode or '-' }} · {{ selected_fundidor.job_title or '-' }}</div>
                </div>
            </div>

            <form id="ncForm" method="POST" action="/registrar">
                <input type="hidden" name="fundidor_id" value="{{ selected_fundidor.id }}">
                <input type="hidden" name="fundidor_name" value="{{ selected_fundidor.name }}">
                <input type="hidden" name="fundidor_barcode" value="{{ selected_fundidor.barcode or '' }}">
                <input type="hidden" name="fundidor_job" value="{{ selected_fundidor.job_title or '' }}">

                <div class="nc-grid">
                    {% for r in reasons %}
                    <label class="nc-item" onclick="toggleNC(this, '{{ r.id }}')">
                        <div class="nc-checkbox"></div>
                        <span class="nc-label">{{ r.name }}</span>
                        <input type="checkbox" name="nc_ids" value="{{ r.id }}" class="hidden nc-input">
                    </label>
                    {% endfor %}
                </div>

                <div class="submit-area">
                    <div class="selected-count">
                        <span id="ncCount">0</span> não conformidades selecionadas
                    </div>
                    <div style="display:flex; gap:10px;">
                        <button type="submit" name="action" value="nenhuma" class="btn btn-nenhuma">
                            ✅ Nenhuma NC (OK)
                        </button>
                        <button type="submit" name="action" value="registrar" class="btn btn-primary" id="btnSubmit" disabled>
                            📝 Registrar NCs
                        </button>
                    </div>
                </div>
            </form>
        </div>
        {% endif %}

        {% elif page == 'historico' %}
        <!-- HISTORY -->
        <div class="nc-section">
            <h2>Últimos Registros</h2>
            <div class="subtitle">Alertas de qualidade da equipe Fundição</div>

            <table class="history-table">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Título</th>
                        <th>Motivo</th>
                        <th>Estágio</th>
                        <th>Data</th>
                    </tr>
                </thead>
                <tbody>
                    {% for a in alerts %}
                    <tr>
                        <td style="color: var(--text-dim);">#{{ a.id }}</td>
                        <td>{{ a.name }}</td>
                        <td>{{ a.reason_id[1] if a.reason_id else '-' }}</td>
                        <td><span class="badge badge-new">{{ a.stage_id[1] if a.stage_id else '-' }}</span></td>
                        <td style="color: var(--text-dim);">{{ a.create_date }}</td>
                    </tr>
                    {% endfor %}
                    {% if not alerts %}
                    <tr><td colspan="5" style="text-align:center; color: var(--text-dim); padding:40px;">Nenhum registro ainda</td></tr>
                    {% endif %}
                </tbody>
            </table>
        </div>

        {% elif page == 'sucesso' %}
        <!-- SUCCESS -->
        <div style="text-align:center; padding:60px 0;">
            <div style="font-size:4rem; margin-bottom:20px;">{{ '✅' if ncs_count == 0 else '📝' }}</div>
            <h2 style="margin-bottom:10px;">
                {% if ncs_count == 0 %}
                    Fundidor OK — Nenhuma NC
                {% else %}
                    {{ ncs_count }} NC(s) Registrada(s)!
                {% endif %}
            </h2>
            <p style="color: var(--text-dim); margin-bottom:30px;">
                {{ fundidor_name }} · {{ datetime_str }}
            </p>
            <div style="display:flex; gap:12px; justify-content:center;">
                <a href="/" class="btn btn-primary">📋 Próximo Fundidor</a>
                <a href="/historico" class="btn btn-outline">📊 Ver Histórico</a>
            </div>
        </div>
        {% endif %}
    </div>

    <script>
        // Clock
        function updateClock() {
            const now = new Date();
            const opts = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' };
            document.getElementById('clock').textContent = now.toLocaleDateString('pt-BR', opts);
        }
        updateClock();
        setInterval(updateClock, 1000);

        // Filter fundidores
        function filterFundidores(query) {
            const cards = document.querySelectorAll('.fundidor-card');
            query = query.toLowerCase();
            cards.forEach(card => {
                const name = card.dataset.name.toLowerCase();
                const badge = (card.dataset.badge || '').toLowerCase();
                card.style.display = (name.includes(query) || badge.includes(query)) ? '' : 'none';
            });
        }

        // Toggle NC checkbox
        function toggleNC(el, id) {
            el.classList.toggle('checked');
            const input = el.querySelector('.nc-input');
            input.checked = !input.checked;
            updateCount();
        }

        function updateCount() {
            const checked = document.querySelectorAll('.nc-item.checked').length;
            const counter = document.getElementById('ncCount');
            const btn = document.getElementById('btnSubmit');
            if (counter) counter.textContent = checked;
            if (btn) btn.disabled = checked === 0;
        }

        // Active tab
        if (window.location.pathname.includes('historico')) {
            document.getElementById('tab-inspecao').classList.remove('active');
            document.getElementById('tab-historico').classList.add('active');
        }
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    fundidores = get_fundidores()
    reasons = get_reasons()
    return render_template_string(
        HTML_TEMPLATE,
        page='inspecao',
        fundidores=fundidores,
        reasons=reasons,
        selected_fundidor=None
    )


@app.route('/inspecao/<int:fundidor_id>')
def inspecao(fundidor_id):
    conn = get_conn()
    fundidores = get_fundidores()
    reasons = get_reasons()

    # Find selected fundidor
    selected = None
    for f in fundidores:
        if f['id'] == fundidor_id:
            selected = f
            break

    if not selected:
        return redirect('/')

    return render_template_string(
        HTML_TEMPLATE,
        page='inspecao',
        fundidores=fundidores,
        reasons=reasons,
        selected_fundidor=selected
    )


@app.route('/registrar', methods=['POST'])
def registrar():
    conn = get_conn()
    team_id = get_team_id()

    fundidor_id = request.form.get('fundidor_id')
    fundidor_name = request.form.get('fundidor_name', '')
    fundidor_barcode = request.form.get('fundidor_barcode', '')
    fundidor_job = request.form.get('fundidor_job', '')
    action = request.form.get('action', 'registrar')

    now = datetime.now()
    data_str = now.strftime("%Y-%m-%d")
    hora_str = now.strftime("%H:%M")
    datetime_str = now.strftime("%d/%m/%Y %H:%M")

    nc_ids = request.form.getlist('nc_ids')
    ncs_count = 0

    if action == 'nenhuma' or not nc_ids:
        # Registrar que o fundidor está OK (sem NCs)
        pass
    else:
        # Buscar nomes dos motivos
        reasons = get_reasons()
        reason_map = {str(r['id']): r['name'] for r in reasons}

        for nc_id in nc_ids:
            nc_name = reason_map.get(nc_id, 'Desconhecido')
            titulo = f"[{data_str}] {fundidor_name} - {nc_name}"

            vals = {
                'name': titulo,
                'team_id': team_id,
                'reason_id': int(nc_id),
                'priority': '1',
                'x_studio_funcionario': int(fundidor_id),
                'description': (
                    f"Fundidor: {fundidor_name}\n"
                    f"Badge: {fundidor_barcode}\n"
                    f"Cargo: {fundidor_job}\n"
                    f"Data/Hora da inspeção: {datetime_str}\n"
                    f"Não conformidade: {nc_name}"
                ),
            }
            conn.criar('quality.alert', vals)
            ncs_count += 1

    return render_template_string(
        HTML_TEMPLATE,
        page='sucesso',
        ncs_count=ncs_count,
        fundidor_name=fundidor_name,
        datetime_str=datetime_str,
        fundidores=[], reasons=[], selected_fundidor=None, alerts=[]
    )


@app.route('/historico')
def historico():
    alerts = get_recent_alerts(50)
    return render_template_string(
        HTML_TEMPLATE,
        page='historico',
        alerts=alerts,
        fundidores=[], reasons=[], selected_fundidor=None
    )


if __name__ == '__main__':
    print("=" * 50)
    print("INSPEÇÃO DE FUNDIÇÃO - Interface Web")
    print("=" * 50)
    print("Acesse: http://localhost:5050")
    print("Ctrl+C para parar")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5050, debug=False)
