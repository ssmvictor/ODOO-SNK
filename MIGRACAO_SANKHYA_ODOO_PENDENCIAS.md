# Pendencias de Migracao Sankhya -> Odoo

Este documento resume o que ainda e recomendado migrar para completar a operacao no Odoo.

## Prioridades Recomendadas

1. **Vendedores (Salesperson)**
- Origem: cadastros/flags de vendedor no Sankhya.
- Destino: `res.users` / vendedor nos documentos de venda.
- Motivo: hoje os parceiros podem ter tag de vendedor, mas o fluxo comercial no Odoo usa usuario vendedor.

2. **Condicoes de Pagamento**
- Origem: regras e prazos de pagamento.
- Destino: `account.payment.term`.
- Motivo: influencia faturamento, financeiro e vencimentos automaticamente.

3. **Tabelas de Preco**
- Origem: regras de preco por cliente/grupo/produto.
- Destino: `product.pricelist` e regras de precificacao.
- Motivo: garante orcamento/pedido com preco correto.

4. **Fiscal Completo (Brasil)**
- Origem: CFOP, CST, NCM, regras de ICMS/IPI/PIS/COFINS.
- Destino: campos fiscais e localizacao Brasil no Odoo.
- Motivo: necessario para emissao fiscal correta e conformidade.

5. **Enderecos por Parceiro (Entrega/Cobranca)**
- Origem: enderecos e tipos de endereco.
- Destino: contatos filhos do parceiro (`res.partner`) com tipo.
- Motivo: evita retrabalho e erro operacional em pedido e faturamento.

6. **Contatos por Parceiro**
- Origem: pessoas de contato (comprador, financeiro, etc.).
- Destino: contatos filhos em `res.partner`.
- Motivo: melhora processo comercial, cobranca e comunicacao.

7. **Pedidos em Aberto**
- Origem: pedidos de venda/compra pendentes no Sankhya.
- Destino: documentos abertos no Odoo.
- Motivo: continuidade operacional na virada do sistema.

8. **Titulos Financeiros em Aberto**
- Origem: contas a receber/pagar abertas.
- Destino: financeiro/contabil no Odoo.
- Motivo: manter saldo e cobranca consistentes no go-live.

9. **Rastreabilidade de Estoque (alem do saldo)**
- Origem: lotes, series, localizacao e historico minimo.
- Destino: modelos de estoque do Odoo (lote/serie/movimentacao, conforme necessidade).
- Motivo: suporte a auditoria e operacao diaria.

10. **Estruturas Contabeis/Gerenciais**
- Origem: centro de custo, contas e classificacoes gerenciais.
- Destino: plano/estrutura contabil e analitica no Odoo.
- Motivo: preservar visao gerencial e integridade contabil.

## Ordem Sugerida de Execucao

1. Vendedores  
2. Condicoes de Pagamento  
3. Tabelas de Preco  
4. Fiscal Completo  
5. Enderecos e Contatos  
6. Pedidos em Aberto  
7. Titulos Financeiros em Aberto  
8. Rastreabilidade de Estoque  
9. Estruturas Contabeis/Gerenciais

## Criterio Minimo de Aceite por Etapa

- Dados carregados sem erro critico.
- Amostra validada no Odoo com usuarios-chave.
- Reprocessamento idempotente (rodar novamente sem duplicar).
- Evidencia de reconciliacao (contagem/origem x destino).
