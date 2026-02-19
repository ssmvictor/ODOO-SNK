# Modulos de Sincronizacao — ODOO-SNK

Detalhes de cada modulo de sincronizacao: mapeamento de campos, logica de upsert e comandos de execucao.

---

## Produtos

**Arquivo:** `Produtos/sincronizar_produtos.py`

Sincroniza produtos ativos do Sankhya (`TGFPRO`) para o modelo `product.template` do Odoo.

**Mapeamento de campos:**

| TGFPRO (Sankhya) | product.template (Odoo) | Descricao |
|-------------------|------------------------|-----------|
| `CODPROD` | `default_code` | Codigo interno (chave do upsert) |
| `DESCRPROD` | `name` | Nome do produto |
| `REFFORN` | `barcode` | Referencia do fornecedor |
| `PESOBRUTO` | `weight` | Peso bruto |
| `CODVOL` | `uom_id` / `uom_po_id` | Unidade de medida |
| `USOPROD` | `type` / `is_storable` | `R` → `consu` (estocavel), `S` → `service` |
| `NCM` | `ncm` / `l10n_br_ncm_id` | NCM fiscal (se campo disponivel) |
| `MARCA` | `product_brand_id` / `x_marca` | Marca (se campo disponivel) |
| `CODLOCALPADRAO` | `x_local_padrao_id` | Local padrao de estoque (se campo disponivel) |
| — | `list_price` | Fixo: `0.0` (preco definido por tabela de precos) |
| — | `sale_ok` | Fixo: `False` |
| — | `purchase_ok` | Fixo: `True` |

**Logica de upsert:**
- Busca pelo `default_code` (CODPROD)
- Se nao existir: **cria** o produto
- Se existir: **atualiza** nome, peso, barcode, unidade e campos complementares

```bash
python Produtos/sincronizar_produtos.py
```

---

## Estoque

**Arquivo:** `Produtos/sincronizar_estoque.py`

Sincroniza saldos de estoque do Sankhya (`TGFEST`) para o modelo `stock.quant` do Odoo.

> **ATENCAO:** Requer que os produtos (`sincronizar_produtos.py`) e os locais (`sincronizar_locais.py`) ja estejam sincronizados no Odoo.

**Mapeamento de campos:**

| TGFEST (Sankhya) | stock.quant (Odoo) | Descricao |
|------------------|-------------------|-----------|
| `CODPROD` | `product_id` | Produto (via `default_code`) |
| `CODLOCAL` | `location_id` | Local de estoque (via `barcode`) |
| `ESTOQUE` | `inventory_quantity` | Quantidade em estoque |

**Comportamento:**
- Pre-carrega mapa de produtos em cache para performance
- Aplica `action_apply_inventory` apos cada ajuste
- Itens sem produto ou local correspondente no Odoo sao ignorados (contados como "ignorados")

```bash
python Produtos/sincronizar_estoque.py
```

---

## Grupos de Produtos

**Arquivo:** `Produtos/sincronizar_grupos.py`

Sincroniza a estrutura de grupos de produtos do Sankhya (`TGFGRU`) para `product.category` no Odoo, preservando hierarquia pai/filho em dois passos.

**Mapeamento de campos:**

| TGFGRU (Sankhya) | product.category (Odoo) | Descricao |
|------------------|------------------------|-----------|
| `CODGRUPOPROD` | `name` (prefixo `[COD]`) | Codigo do grupo |
| `DESCRGRUPOPROD` | `name` | Descricao do grupo |
| `CODGRUPAI` | `parent_id` | Codigo do grupo pai |
| `GRAU` | `x_grau` (se disponivel) | Nivel hierarquico |

**Etapas de sincronizacao:**
1. **Passo A** — Cria ou atualiza todas as categorias sem vincular `parent_id`
2. **Passo B** — Reconcilia a hierarquia, definindo `parent_id` para cada categoria

```bash
python Produtos/sincronizar_grupos.py
```

---

## Locais de Estoque

**Arquivo:** `Produtos/sincronizar_locais.py`

Sincroniza os locais de estoque do Sankhya (`TGFLOC`) para `stock.location` no Odoo, respeitando hierarquia pai/filho.

**Mapeamento de campos:**

| TGFLOC (Sankhya) | stock.location (Odoo) | Descricao |
|------------------|----------------------|-----------|
| `CODLOCAL` | `barcode` | Codigo do local (chave do upsert) |
| `DESCRLOCAL` | `name` | Descricao do local |
| `CODLOCALPAI` | `location_id` | Local pai na hierarquia |
| `GRAU` | `x_grau` (se disponivel) | Nivel hierarquico |
| — | `usage` | Fixo: `internal` |

**Etapas de sincronizacao:**
1. Locais sao ordenados pelo grau hierarquico antes do processamento
2. **Passo A** — Cria ou atualiza todos os locais com `location_id` apontando para o deposito padrao
3. **Passo B** — Reconcilia a hierarquia real, vinculando `location_id` ao pai correto

```bash
python Produtos/sincronizar_locais.py
```

---

## Parceiros

**Arquivo:** `Parceiros/sincronizar_parceiros.py`

Sincroniza parceiros (clientes, fornecedores, transportadoras, etc.) do Sankhya (`TGFPAR`) para `res.partner` no Odoo.

**Mapeamento principal de campos:**

| TGFPAR (Sankhya) | res.partner (Odoo) | Descricao |
|------------------|--------------------|-----------|
| `CODPARC` | `ref` / `x_sankhya_id` | Codigo do parceiro (chave do upsert) |
| `RAZAOSOCIAL` | `name` | Razao social |
| `NOMEPARC` | `name` (fallback) | Nome do parceiro |
| `TIPPESSOA` | `company_type` / `is_company` | `J`/`E` → empresa, `F` → pessoa fisica |
| `CGC_CPF` | `vat` / `l10n_br_cnpj_cpf` | CNPJ ou CPF |
| `INSCESTADNAUF` | `l10n_br_ie_code` / `x_ie` | Inscricao estadual |
| `NOMEEND` + `NUMEND` | `street` | Logradouro e numero |
| `COMPLEMENTO` / `NOMEBAI` | `street2` | Complemento ou bairro |
| `NOMECID` | `city` | Cidade |
| `CEP` | `zip` | CEP |
| `UF_SIGLA` | `state_id` | Estado (via codigo IBGE) |
| `PAIS_SIGLA` | `country_id` | Pais (via codigo ISO) |
| `EMAIL` | `email` | E-mail |
| `TELEFONE` | `phone` | Telefone |
| `FAX` | `mobile` | Celular |
| `CLIENTE` | `customer_rank` | Flag de cliente |
| `FORNECEDOR` | `supplier_rank` | Flag de fornecedor |
| `ATIVO` | `active` | Status ativo/inativo |

**Papeis mapeados como tags (`category_id`):** `CLIENTE`, `FORNECEDOR`, `VENDEDOR`, `TRANSPORTADORA`, `MOTORISTA`

```bash
python Parceiros/sincronizar_parceiros.py
```
