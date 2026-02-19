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
