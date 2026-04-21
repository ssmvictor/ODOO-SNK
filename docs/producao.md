# Producao — ODOO-SNK

Scripts do setor de producao e qualidade, localizados em `producao/`.

---

## Funcionarios

**Arquivo:** `producao/sync_funcionarios.py`

Sincroniza funcionarios do sistema Rubi (banco Oracle) para `hr.employee` no Odoo.

**Origem:** tabelas `VETORH.R034FUN`, `VETORH.R038HCC`, `VETORH.R018CCU`, `VETORH.R024CAR`

| Campo Rubi | hr.employee (Odoo) | Descricao |
|------------|--------------------|-----------| 
| `NUMCAD` | `barcode` | Numero de cracha (chave do upsert) |
| `NOMFUN` | `name` | Nome do funcionario |
| `TITCAR` | `job_title` | Cargo |
| `NOMCCU` | `department_id` | Departamento (criado se nao existir) |
| `SITAFA` | `active` | `7` → arquivado, demais → ativo |

```bash
python producao/sync_funcionarios.py
```

> **Requer:** variaveis `ORACLE_*` configuradas no `.env`. Consulte [quickstart.md](quickstart.md).

---

## Setup Fundicao

**Arquivo:** `producao/setup_fundicao.py`

Configura o setor de Fundicao no Odoo:
- Verifica/cria o departamento de Fundicao
- Lista fundidores cadastrados
- Cadastra motivos de nao conformidade (`quality.reason`)
- Cria equipe de qualidade (`quality.alert.team`)

```bash
python producao/setup_fundicao.py
```

> **Execute este script antes** de usar os scripts de registro de nao conformidades.

---

## App Inspecao (Interface Web)

**Arquivo:** `producao/app_inspecao.py`

Aplicacao **Flask** para registro de nao conformidades por fundidor via interface web. Fornece fluxo visual com checkboxes, data/hora automatica e historico de registros.

**Funcionalidades:**
- Selecao de fundidor com busca por nome/badge
- Checklist visual de motivos de NC
- Registro de alertas de qualidade (`quality.alert`) no Odoo
- Pagina de historico com ultimos registros
- Interface responsiva dark mode

**Fluxo:**
1. Selecionar fundidor do departamento de Fundicao
2. Marcar nao conformidades observadas ou confirmar "Nenhuma NC"
3. Alertas sao criados automaticamente no Odoo

```bash
# Instalar Flask (se necessario)
pip install flask

# Iniciar servidor
python producao/app_inspecao.py
# Acesse: http://localhost:5050
```

> **Requer:** equipe de qualidade e motivos de NC configurados (execute `setup_fundicao.py` antes).

---

## Registrar Nao Conformidade

**Arquivo:** `producao/registrar_nc.py`

Registra alertas de qualidade (`quality.alert`) para o setor de Fundicao de forma interativa ou via argumentos de linha de comando.

```bash
# Modo interativo
python producao/registrar_nc.py

# Modo direto
python producao/registrar_nc.py --titulo "Bolhas na peca X" --motivo "Bolhas" --prioridade 2
```

---

## Registro Diario de NCs

**Arquivo:** `producao/registro_diario_nc.py`

Registra em lote as nao conformidades do dia atual. Util para automacao via agendador de tarefas.

```bash
python producao/registro_diario_nc.py
```

---

## Demo NC Diario

**Arquivo:** `producao/demo_nc_diario.py`

Cria exemplos de registro diario de NC para demonstracao. Simula inspecao de 3 fundidores com diferentes NCs (Bolhas, Trincas, Porosidade, etc.).

```bash
python producao/demo_nc_diario.py
```

---

## Criar Alertas de Qualidade

**Arquivo:** `producao/criar_alertas_nc.py`

Cria alertas de qualidade (`quality.alert`) a partir de uma lista de ocorrencias.

```bash
python producao/criar_alertas_nc.py
```

---

## Limpar Alertas Genericos

**Arquivo:** `producao/limpar_alertas_genericos.py`

Remove alertas de qualidade genericos ou duplicados do Odoo.

```bash
python producao/limpar_alertas_genericos.py
```

---

## Configuracao em Massa de Listas de Materiais

**Arquivo:** `producao/config_bom_massa.py`

Configura em massa as listas de materiais (Bill of Materials) no Odoo para o setor de producao.

```bash
python producao/config_bom_massa.py
```

---

## Consulta Oracle (SAN001)

**Arquivo:** `producao/get_san001.py`

Conecta ao Oracle e retorna registros da tabela `GRUPOAEL.SAN001`. Utilizado para consultas especificas do setor de producao.

```bash
python producao/get_san001.py
```

> **Requer:** variaveis `ORACLE_*` configuradas no `.env`.

---

## Scripts de Verificacao

Utilitarios para validar o estado dos dados apos sincronizacoes.

| Script | Descricao |
|--------|-----------|
| `producao/verify_bom.py` | Verifica integridade das listas de materiais |
| `producao/verify_sync.py` | Verifica resultado de sincronizacoes |
| `producao/verify_alerts.py` | Verifica alertas de qualidade |

```bash
python producao/verify_bom.py
python producao/verify_sync.py
python producao/verify_alerts.py
```

---

## Scripts Auxiliares de Inspecao

Scripts de debug e analise utilizados durante desenvolvimento. Nao fazem parte do fluxo principal.

| Script | Descricao |
|--------|-----------|
| `producao/inspect_odoo_data.py` | Inspeciona dados do Odoo |
| `producao/inspect_quality_module.py` | Inspeciona modulo de qualidade |
| `producao/inspect_bom_products.py` | Inspeciona produtos com BOM |
| `producao/inspect_fields.py` | Inspeciona campos de modelos |
| `producao/delete_tables.py` | Remove produtos-exemplo (Table) |
| `producao/analyze_data.py` | Analise de dados |
