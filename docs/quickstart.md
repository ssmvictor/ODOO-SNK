# Quickstart — ODOO-SNK

Guia rapido para instalacao e primeira execucao do projeto.

---

## Requisitos

- **Python** 3.10+
- **Odoo** 18 Enterprise (SaaS ou on-premise)
- **Sankhya** com API Gateway habilitada
- **Oracle** (opcional, para sincronizacao de funcionarios via Rubi)

---

## Instalacao

```bash
git clone <repositorio>
cd ODOO-SNK
pip install -r requirements.txt
cp .env.example .env
# Edite .env com suas credenciais
```

### Dependencias

| Dependencia | Uso |
|-------------|-----|
| `python-dotenv` | Carregamento de variaveis de ambiente |
| `odoorpc` | Comunicacao JSON-RPC com Odoo |
| `sankhya-sdk-python` | Autenticacao OAuth2 e API Gateway Sankhya |
| `rich` | Saida formatada no terminal (tabelas, progresso) |
| `oracledb` | Conexao com banco Oracle (Rubi) |
| `flask` | Interface web para inspecao de fundicao (opcional) |

---

## Configuracao do `.env`

### 1. Criar arquivo `.env`

```bash
cp .env.example .env
```

### 2. Preencher credenciais

```env
# =============================================
# CONEXAO ODOO 18
# =============================================
ODOO_URL=https://sua-empresa.odoo.com
ODOO_DB=nome_do_banco
ODOO_EMAIL=seu_email@empresa.com
ODOO_SENHA=sua_senha_segura

# =============================================
# CONEXAO SANKHYA (OAuth2 via SDK)
# =============================================
# Credenciais obtidas no Portal do Desenvolvedor Sankhya
SANKHYA_CLIENT_ID=seu_client_id
SANKHYA_CLIENT_SECRET=seu_client_secret
SANKHYA_TOKEN=seu_token_proprietario

# =============================================
# CONEXAO ORACLE / RUBI (opcional)
# =============================================
ORACLE_HOST=servidor_oracle
ORACLE_PORT=1521
ORACLE_SERVICE_NAME=nome_do_servico
ORACLE_USER=usuario_oracle
ORACLE_PASSWORD=senha_oracle
```

> **ATENCAO:** Nunca versione o arquivo `.env` com credenciais reais. Use `.env.example` como modelo.

---

## Testar Conexoes

```bash
# Testar conexao com Odoo
python loginOdoo/conexao.py

# Testar conexao com Sankhya
python loginSNK/conexao.py

# Verificar modulos instalados no Odoo
python verificar_modulos_odoo.py
```

---

## Ordem Recomendada de Execucao

Para uma carga inicial completa, execute nesta ordem:

```bash
# 0. Empresa (sincroniza dados da empresa no Odoo)
python Produtos/sincronizar_empresa.py

# 1. Grupos de produtos (categorias)
python Produtos/sincronizar_grupos.py

# 2. Locais de estoque
python Produtos/sincronizar_locais.py

# 3. Produtos (depende de grupos e locais para campos complementares)
python Produtos/sincronizar_produtos.py

# 4. Estoque (depende de produtos e locais)
python Produtos/sincronizar_estoque.py

# 5. Parceiros
python Parceiros/sincronizar_parceiros.py

# 6. Funcionarios (requer conexao Oracle configurada)
python producao/sync_funcionarios.py
```

> **Nota:** O modulo `stock` (Inventario) precisa estar instalado no Odoo para os scripts de estoque e locais funcionarem. Verifique com `python verificar_modulos_odoo.py`.

> **Dica:** Consulte [modulos-sincronizacao.md](modulos-sincronizacao.md) para detalhes de mapeamento de campos de cada modulo.

---

## Proximos Passos

- [Arquitetura](arquitetura.md) — Diagrama de fluxo e modelos do Odoo
- [Modulos de Sincronizacao](modulos-sincronizacao.md) — Detalhes de cada modulo
- [Producao](producao.md) — Scripts do setor de producao
- [Mapeamento Fiscal](mapeamento-fiscal-sankhya-odoo.md) — De-para fiscal Sankhya → Odoo BR
- [SQL Queries](sql-queries.md) — Personalizacao de queries
- [Troubleshooting](troubleshooting.md) — Erros comuns e solucoes
