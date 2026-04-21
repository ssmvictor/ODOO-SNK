# Arquitetura — ODOO-SNK

Visao geral da arquitetura de integracao entre Sankhya, Rubi (Oracle) e Odoo 18 Enterprise.

---

## Diagrama de Fluxo

```mermaid
flowchart LR
    subgraph Fontes["Fontes de Dados"]
        SNK["Sankhya ERP\n(API Gateway OAuth2)"]
        ORA["Rubi / Oracle\n(oracledb)"]
    end

    subgraph Script["ODOO-SNK"]
        SDK["Sankhya SDK\n(OAuth2)"]
        GW["GatewayClient\n(DbExplorerSP)"]
        MAP["Mapeamento\nde Campos"]
        RPC["OdooRPC\n(JSON-RPC)"]
    end

    subgraph Odoo["Odoo 18 Enterprise"]
        RC["res.company"]
        PT["product.template"]
        SQ["stock.quant"]
        SL["stock.location"]
        PC["product.category"]
        RP["res.partner"]
        HR["hr.employee"]
        QA["quality.alert"]
    end

    SNK --> SDK --> GW --> MAP --> RPC --> RC
    SNK --> MAP --> RPC --> PT
    SNK --> MAP --> RPC --> SQ
    SNK --> MAP --> RPC --> SL
    SNK --> MAP --> RPC --> PC
    SNK --> MAP --> RPC --> RP
    ORA --> MAP --> RPC --> HR
    RPC --> QA
```

---

## Fluxo Geral de Sincronizacao

1. **Autenticacao** no Sankhya via OAuth2 (client credentials) ou conexao direta ao Oracle
2. **Execucao SQL** via `DbExplorerSP.executeQuery` (Sankhya) ou cursor Oracle (Rubi)
3. **Mapeamento** dos campos da origem para os modelos do Odoo
4. **Upsert** no Odoo — cria o registro se nao existir ou atualiza o existente

---

## Estrutura do Projeto

```
ODOO-SNK/
├── .env                               # Credenciais (NAO versionar!)
├── .gitignore
├── README.md
├── requirements.txt                   # Dependencias Python
├── inspect_odoo.py                    # Inspeciona modelos/campos do Odoo
├── verificar_modulos_odoo.py          # Lista modulos instalados no Odoo
├── check_companies.py                 # Consulta empresas cadastradas no Odoo
├── delete_company.py                  # Utilitario para remover/arquivar empresa
├── limpar_cache.bat                   # Limpa cache de bytecode Python
│
├── docs/                              # Documentacao do projeto
│   ├── arquitetura.md                 # Este arquivo
│   ├── quickstart.md                  # Instalacao e primeira execucao
│   ├── modulos-sincronizacao.md       # Empresas, Produtos, Estoque, Parceiros
│   ├── producao.md                    # Funcionarios, qualidade, NC, app web
│   ├── modulos-base.md               # loginOdoo e loginSNK
│   ├── mapeamento-fiscal-sankhya-odoo.md  # Mapeamento fiscal detalhado
│   ├── troubleshooting.md            # Erros comuns e seguranca
│   └── sql-queries.md                # Personalizacao de queries SQL
│
├── loginOdoo/                         # Modulo de conexao com o Odoo
│   ├── __init__.py
│   └── conexao.py                     # OdooConfig, OdooConexao, criar_conexao()
│
├── loginSNK/                          # Modulo de conexao com o Sankhya
│   ├── __init__.py
│   ├── conexao.py                     # SankhyaConfig, SankhyaConexao (SDK OAuth2)
│   ├── dbexplorer_EXAMPLE.py          # Exemplo de uso do GatewayClient
│   └── sql/
│       ├── empresa.sql                # Query de empresa (TSIEMP)
│       ├── produtos.sql               # Query de produtos (TGFPRO)
│       ├── estoque.sql                # Query de saldo de estoque (TGFEST)
│       ├── grupos.sql                 # Query de grupos de produtos (TGFGRU)
│       ├── locais.sql                 # Query de locais de estoque (TGFLOC)
│       ├── parceiros.sql              # Query de parceiros (TGFPAR)
│       ├── parceiros_vendedor.sql     # Query de parceiros filtrada por vendedor
│       └── vendedores.sql             # Query de vendedores
│
├── Produtos/                          # Sincronizacao de Produtos, Estoque e Empresa
│   ├── __init__.py
│   ├── sincronizar_empresa.py         # TSIEMP → res.company
│   ├── sincronizar_produtos.py        # TGFPRO → product.template
│   ├── sincronizar_estoque.py         # TGFEST → stock.quant
│   ├── sincronizar_grupos.py          # TGFGRU → product.category
│   └── sincronizar_locais.py          # TGFLOC → stock.location
│
├── Parceiros/                         # Sincronizacao de Parceiros
│   ├── __init__.py
│   └── sincronizar_parceiros.py       # TGFPAR → res.partner
│
└── producao/                          # Scripts do setor de Producao/Qualidade
    ├── sync_funcionarios.py           # Rubi (Oracle) → hr.employee
    ├── setup_fundicao.py              # Configuracao inicial do setor de Fundicao
    ├── app_inspecao.py                # Interface web Flask para registro de NCs
    ├── registrar_nc.py                # Registro interativo de nao conformidades
    ├── registro_diario_nc.py          # Registro em lote de NCs diarias
    ├── criar_alertas_nc.py            # Criacao de alertas de qualidade
    ├── demo_nc_diario.py              # Demonstracao de NCs de exemplo
    ├── limpar_alertas_genericos.py    # Remove alertas genericos duplicados
    ├── config_bom_massa.py            # Configuracao em massa de listas de materiais
    ├── verify_bom.py                  # Verifica integridade das listas de materiais
    ├── verify_sync.py                 # Verifica resultado de sincronizacoes
    ├── verify_alerts.py               # Verifica alertas de qualidade
    ├── get_san001.py                  # Consulta dados Oracle (GRUPOAEL.SAN001)
    ├── delete_tables.py               # Remove produtos-exemplo (Table) do Odoo
    ├── inspect_*.py / search_*.py     # Scripts auxiliares de inspecao e debug
    └── sql/                           # Queries SQL para producao
        └── query.sql                  # Query Oracle customizada
```

---

## Modelos do Odoo Utilizados

| Modelo | Descricao |
|--------|-----------|
| `res.company` | Empresas |
| `product.template` | Templates de produtos |
| `product.product` | Variantes de produtos |
| `product.category` | Categorias / grupos de produtos |
| `uom.uom` | Unidades de medida |
| `stock.quant` | Saldos de estoque |
| `stock.location` | Locais de estoque |
| `stock.warehouse` | Depositos |
| `res.partner` | Clientes / Fornecedores / Parceiros |
| `res.country` | Paises |
| `res.country.state` | Estados |
| `hr.employee` | Funcionarios |
| `hr.department` | Departamentos |
| `quality.alert` | Alertas de qualidade / Nao conformidades |
| `quality.alert.team` | Equipes de qualidade |
| `quality.reason` | Motivos de nao conformidade |
| `ir.module.module` | Modulos instalados |
| `l10n_br_fiscal.cnae` | CNAE (empresa) |
| `l10n_br.ncm.code` | Codigos NCM |
| `l10n_br.operation.type` | Tipos de operacao fiscal |

### Tipos de Produto (Odoo 18 API)

| Valor API | Label na UI | Descricao |
|-----------|-------------|-----------|
| `product` | Produto armazenavel | Bens tangiveis com controle de estoque |
| `consu` | Consumivel | Bens sem controle de estoque |
| `service` | Servico | Ofertas intangiveis sem estoque |
