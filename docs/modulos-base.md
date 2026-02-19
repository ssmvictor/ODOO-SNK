# Modulos Base — ODOO-SNK

Documentacao dos modulos de conexao reutilizaveis: `loginOdoo` e `loginSNK`.

---

## loginOdoo — Conexao com o Odoo

**Arquivo:** `loginOdoo/conexao.py`

Gerencia autenticacao e comunicacao com o Odoo via JSON-RPC (OdooRPC).

### Uso

```python
from loginOdoo.conexao import criar_conexao

# Cria conexao ja autenticada (le credenciais do .env)
conexao = criar_conexao()

# Buscar registros
parceiros = conexao.search_read('res.partner', campos=['name', 'email'], limite=10)

# Criar registro
produto_id = conexao.criar('product.template', {'name': 'Produto X', 'type': 'consu'})

# Atualizar registro
conexao.atualizar('product.template', produto_id, {'list_price': 99.90})

# Excluir registro
conexao.excluir('product.template', produto_id)
```

### Classes e funcoes principais

| Classe / Funcao | Descricao |
|----------------|-----------|
| `OdooConfig` | Dataclass com credenciais de conexao |
| `OdooConexao` | Gerencia conexao e operacoes CRUD |
| `carregar_configuracao()` | Le credenciais do `.env` |
| `criar_conexao()` | Cria e retorna conexao ja autenticada |
| `OdooConfigError` | Excecao: variaveis de ambiente ausentes |
| `OdooConnectionError` | Excecao: falha na conexao |

### Variaveis de ambiente necessarias

```env
ODOO_URL=https://sua-empresa.odoo.com
ODOO_DB=nome_do_banco
ODOO_EMAIL=seu_email@empresa.com
ODOO_SENHA=sua_senha_segura
```

### Testar conexao

```bash
python loginOdoo/conexao.py
```

---

## loginSNK — Conexao com o Sankhya

**Arquivo:** `loginSNK/conexao.py`

Gerencia autenticacao OAuth2 na API Sankhya via SDK.

### Uso

```python
from loginSNK.conexao import criar_conexao_sankhya

# Cria conexao ja autenticada (le credenciais do .env)
conexao = criar_conexao_sankhya()

# Sessao autenticada com auto-refresh de token
session = conexao.session

# Headers para requisicoes manuais
headers = conexao.obter_headers_autorizacao()
```

### Classes e funcoes principais

| Classe / Funcao | Descricao |
|----------------|-----------|
| `SankhyaConfig` | Dataclass com credenciais OAuth2 |
| `SankhyaConexao` | Gerencia autenticacao e sessao |
| `carregar_configuracao_sankhya()` | Le credenciais do `.env` |
| `criar_conexao_sankhya()` | Cria e retorna conexao ja autenticada |
| `SankhyaConfigError` | Excecao: variaveis de ambiente ausentes |
| `SankhyaAuthError` | Excecao: falha na autenticacao OAuth2 |

### Variaveis de ambiente necessarias

```env
SANKHYA_CLIENT_ID=seu_client_id
SANKHYA_CLIENT_SECRET=seu_client_secret
SANKHYA_TOKEN=seu_token_proprietario
SANKHYA_AUTH_BASE_URL=https://api.sankhya.com.br
```

### Testar conexao

```bash
python loginSNK/conexao.py
```

### Exemplo com GatewayClient

Consulte `loginSNK/dbexplorer_EXAMPLE.py` para um exemplo completo de execucao de queries via `DbExplorerSP`.

---

## Utilitarios de Inspecao

| Script | Descricao |
|--------|-----------|
| `inspect_odoo.py` | Inspeciona modelos e campos do Odoo (util para descobrir nomes de campos) |
| `verificar_modulos_odoo.py` | Lista todos os modulos instalados no Odoo |

```bash
python inspect_odoo.py
python verificar_modulos_odoo.py
```
