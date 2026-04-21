# ODOO-SNK — Integracao Sankhya / Rubi → Odoo

Projeto Python para **sincronizacao de dados entre os ERPs Sankhya e Rubi (Oracle) e o Odoo 18 Enterprise**, utilizando o [Sankhya SDK Python](https://github.com/ssmvictor/Sankhya-SDK-python) (OAuth2), [OdooRPC](https://pypi.org/project/OdooRPC/) e `oracledb`.

> [!IMPORTANT]
> **Objetivo**: Migrar e sincronizar dados (empresas, produtos, estoque, parceiros, funcionarios, producao) do Sankhya/Rubi para o Odoo, permitindo operacao hibrida ou transicao gradual entre os sistemas.

---

## Inicio Rapido

```bash
git clone <repositorio>
cd ODOO-SNK
pip install -r requirements.txt
cp .env.example .env
# Edite .env com suas credenciais
```

Ordem recomendada para carga inicial:

```bash
python Produtos/sincronizar_empresa.py
python Produtos/sincronizar_grupos.py
python Produtos/sincronizar_locais.py
python Produtos/sincronizar_produtos.py
python Produtos/sincronizar_estoque.py
python Parceiros/sincronizar_parceiros.py
python producao/sync_funcionarios.py
```

---

## Documentacao

| Documento | Descricao |
|-----------|-----------|
| [Quickstart](docs/quickstart.md) | Instalacao, configuracao do `.env` e ordem de execucao |
| [Arquitetura](docs/arquitetura.md) | Diagrama de fluxo, estrutura do projeto e modelos do Odoo |
| [Modulos de Sincronizacao](docs/modulos-sincronizacao.md) | Mapeamento de campos: Empresas, Produtos, Estoque, Grupos, Locais, Parceiros |
| [Producao](docs/producao.md) | Funcionarios, setup de Fundicao, nao conformidades, qualidade e app web |
| [Modulos Base](docs/modulos-base.md) | API dos modulos `loginOdoo` e `loginSNK` com exemplos de uso |
| [Mapeamento Fiscal](docs/mapeamento-fiscal-sankhya-odoo.md) | De-para fiscal Sankhya → Odoo BR, checklist de migracao |
| [SQL Queries](docs/sql-queries.md) | Queries SQL e guia de personalizacao |
| [Troubleshooting](docs/troubleshooting.md) | Erros comuns, checklist de diagnostico e seguranca |

---

## Modulos Odoo Instalados

O ambiente atual possui **113 modulos instalados**, incluindo:

- Localizacao brasileira completa (`l10n_br_*`)
- Vendas, Compras, Faturamento, Projetos
- RH e Gamificacao
- Marketing por E-mail
- Pesquisas e Planilhas

> **Nota:** O modulo `stock` (Inventario) **nao esta instalado** atualmente. Scripts de estoque e locais requerem sua instalacao.

Para consultar a lista completa: `python verificar_modulos_odoo.py`

---

## Licenca

Projeto de uso interno — Grupo AEL.

---

**Atualizado em:** 20/04/2026
