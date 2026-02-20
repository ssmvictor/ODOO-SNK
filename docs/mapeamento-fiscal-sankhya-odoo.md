# Mapeamento Fiscal Sankhya -> Odoo BR

Data: 2026-02-20

## Resumo rapido

No ambiente Odoo atual, os campos fiscais do produto existem no `product.template`, mas quase todos estao vazios.  
Principal erro tecnico no importador atual: uso de `l10n_br_ncm_id` (inexistente) em vez de `l10n_br_ncm_code_id` (campo real).

## Diagnostico atual (Odoo)

Base: 548 produtos com `default_code`.

- `l10n_br_cest_code`: 0 preenchidos
- `l10n_br_ncm_code_id`: 0 preenchidos
- `l10n_br_legal_uom_id`: 0 preenchidos
- `l10n_br_operation_type_sales_id`: 0 preenchidos
- `l10n_br_operation_type_purchases_id`: 0 preenchidos
- `l10n_br_operation_type_pos_id`: 0 preenchidos
- `l10n_br_source_origin`: 0 preenchidos
- `l10n_br_sped_type`: 0 preenchidos
- `l10n_br_use_type`: 0 preenchidos
- `l10n_br_taxable_is`: 548 preenchidos (True)

## De-para Sankhya -> Odoo (campos fiscais)

| Sankhya | Odoo | Observacoes / regra |
|---|---|---|
| `TGFPRO.CODESPECST` ou `TGFPEM.CODESPECST` | `product.template.l10n_br_cest_code` | CEST (7 digitos). |
| `TGFPRO.NCM` | `product.template.l10n_br_ncm_code_id` | many2one para `l10n_br.ncm.code` via `code`; formatar para mascara `####.##.##`. |
| `TGFNCM.UNITRIBUTACAO` (via NCM) | `product.template.l10n_br_legal_uom_id` | many2one para `uom.uom`; usar tabela de conversao de unidade. |
| `TGFPRO.TEMISS` e/ou regra de IS | `product.template.l10n_br_taxable_is` | Boolean; validar regra fiscal com time tributario antes de sobrescrever em massa. |
| `TGFTOP` (venda) | `product.template.l10n_br_operation_type_sales_id` | many2one para `l10n_br.operation.type`; requer tabela de mapeamento TOP -> Operation Type. |
| `TGFTOP` (compra) | `product.template.l10n_br_operation_type_purchases_id` | Idem acima. |
| `TGFTOP` (PDV/cupom fiscal) | `product.template.l10n_br_operation_type_pos_id` | Idem acima. |
| `TGFPRO.ORIGPROD` ou `TGFPEM.ORIGPROD` | `product.template.l10n_br_source_origin` | Selecao Odoo usa codigos `0..8` (mesma logica de origem). |
| `TGFPRO.TIPOITEMSPED` ou `TGFPEM.TIPOITEMSPED` | `product.template.l10n_br_sped_type` | Mapear codigo Sankhya para valores de selecao do Odoo. |
| `TGFPRO.USOPROD` ou `TGFPEM.USOPROD` | `product.template.l10n_br_use_type` | Mapear para `resale`, `use or consumption`, `production`, `fixed assets`, etc. |

## Modulos Odoo BR necessarios (confirmados no ambiente)

- `l10n_br_avatax`
  - Campos: `l10n_br_cest_code`, `l10n_br_ncm_code_id`, `l10n_br_source_origin`, `l10n_br_sped_type`, `l10n_br_use_type`
- `l10n_br_edi_fiscal_reform`
  - Campos: `l10n_br_legal_uom_id`, `l10n_br_operation_type_sales_id`, `l10n_br_operation_type_purchases_id`, `l10n_br_taxable_is`
- `l10n_br_edi_pos_fiscal_reform`
  - Campo: `l10n_br_operation_type_pos_id`
- Modelos auxiliares usados:
  - `l10n_br.ncm.code`
  - `l10n_br.operation.type`

## Causas comuns para nao migrar

1. Campo tecnico incorreto no importador (`l10n_br_ncm_id` vs `l10n_br_ncm_code_id`).
2. NCM sem mascara no ETL e com mascara no Odoo (`85044030` vs `8504.40.30`).
3. Falta de joins fiscais na query de origem (`TGFPEM`, `TGFNCM`, `TGFTOP`).
4. Falha na resolucao de many2one (`ncm`, `uom`, `operation type`).
5. Regras por empresa nao consideradas (dados fiscais em `TGFPEM`).
6. Divergencia de selecoes (SPED/use type/origem) sem tabela de conversao explicita.

## Checklist de validacao da migracao

- Confirmar modulos BR instalados.
- Confirmar carga da tabela `l10n_br.ncm.code`.
- Garantir mascara NCM no lookup de `l10n_br.ncm.code`.
- Validar tabela de conversao unidade tributavel -> `uom.uom`.
- Validar mapeamento de origem (`0..8`).
- Validar mapeamento de SPED (`TIPOITEMSPED`).
- Validar mapeamento de proposito de uso (`USOPROD`).
- Validar tabela TOP -> Operation Type (venda/compra/PDV).
- Executar backfill idempotente e medir preenchimento apos carga.

## Plano de correcao recomendado

1. Ajustar SQL/ETL de produtos para trazer campos fiscais completos:
   - `TGFPRO` + `TGFPEM` + `TGFNCM` + relacao de TOP.
2. Corrigir importador:
   - trocar para `l10n_br_ncm_code_id`;
   - aplicar mascara NCM antes do lookup;
   - incluir mapeamentos CEST, legal UoM, origem, SPED, use type, operation types.
3. Criar tabela de mapeamento de TOP:
   - `CODTIPOPER` Sankhya -> `l10n_br.operation.type` Odoo (sales/purchases/pos).
4. Rodar carga de correcao (somente campos fiscais), com reprocessamento seguro.
5. Validacao funcional com fiscal:
   - produto, pedido, faturamento e emissao.

## Campos custom (apenas se necessario)

Se algum ambiente nao tiver os campos BR:

- Criar no `product.template`:
  - `x_snk_cest`
  - `x_snk_ncm`
  - `x_snk_origem`
  - `x_snk_sped_type`
  - `x_snk_use_type`
- Para operacoes:
  - modelo auxiliar `x_snk_top_map` com chaves Sankhya e relacao para `l10n_br.operation.type`.

## Referencias internas do projeto

- `Produtos/sincronizar_produtos.py`
- `loginSNK/sql/produtos.sql`
- `docs/modulos-sincronizacao.md`
- `docs/sql-queries.md`
