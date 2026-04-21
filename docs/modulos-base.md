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
produto_id = conexao.criar('product.template', {'name': 'Produto X', 'type': 'product'})

# Atualizar registro
conexao.atualizar('product.template', produto_id, {'list_price': 99.90})

# Excluir registro
conexao.excluir('product.template', produto_id)

# Executar metodo arbitrario
campos_info = conexao.executar('product.template', 'fields_get')
```

### Classes e funcoes principais

| Classe / Funcao | Descricao |
|----------------|-----------| 
| `OdooConfig` | Dataclass com credenciais de conexao |
| `OdooConexao` | Gerencia conexao e operacoes CRUD |
| `carregar_configuracao()` | Le credenciais do `.env` |
| `criar_conexao()` | Cria e retorna conexao ja autenticada |
| `OdooError` | Excecao base para erros do modulo |
| `OdooConfigError` | Excecao: variaveis de ambiente ausentes |
| `OdooConnectionError` | Excecao: falha na conexao |

### Metodos de OdooConexao

| Metodo | Descricao |
|--------|-----------|
| `conectar()` | Abre conexao JSON-RPC e autentica |
| `search_read(modelo, dominio, campos, limite, offset, ordem)` | Busca registros com filtros |
| `criar(modelo, valores)` | Cria novo registro, retorna ID |
| `atualizar(modelo, ids, valores)` | Atualiza um ou mais registros |
| `excluir(modelo, ids)` | Remove um ou mais registros |
| `executar(modelo, metodo, args, kwargs)` | Executa metodo arbitrario via RPC |
| `obter_versao()` | Consulta versao do servidor Odoo |

### Propriedades de OdooConexao

| Propriedade | Descricao |
|-------------|-----------|
| `conectado` | Se a conexao esta ativa (`bool`) |
| `uid` | User ID apos autenticacao |
| `odoo` | Instancia OdooRPC nativa (uso avancado) |
| `config` | Configuracao utilizada |

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

# Verificar status
print(conexao.autenticado)  # True
```

### Classes e funcoes principais

| Classe / Funcao | Descricao |
|----------------|-----------| 
| `SankhyaConfig` | Dataclass com credenciais OAuth2 |
| `SankhyaConexao` | Gerencia autenticacao e sessao |
| `carregar_configuracao_sankhya()` | Le credenciais do `.env` |
| `criar_conexao_sankhya()` | Cria e retorna conexao ja autenticada |
| `SankhyaError` | Excecao base para erros do modulo |
| `SankhyaConfigError` | Excecao: variaveis de ambiente ausentes |
| `SankhyaAuthError` | Excecao: falha na autenticacao OAuth2 |

### Variaveis de ambiente necessarias

```env
SANKHYA_CLIENT_ID=seu_client_id
SANKHYA_CLIENT_SECRET=seu_client_secret
SANKHYA_TOKEN=seu_token_proprietario
```

> **Nota:** A URL base da API (`https://api.sankhya.com.br`) e usada como padrao. Para sobrescrever, configure `SANKHYA_AUTH_BASE_URL` no `.env`.

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
| `verificar_modulos_odoo.py` | Lista todos os modulos instalados no Odoo e verifica modulos especificos |
| `check_companies.py` | Consulta empresas cadastradas no Odoo (ID, nome, CNPJ) |
| `delete_company.py` | Utilitario para renomear/arquivar empresa no Odoo |

```bash
python inspect_odoo.py
python verificar_modulos_odoo.py
python check_companies.py
```
