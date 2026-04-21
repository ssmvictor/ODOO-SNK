# Troubleshooting — ODOO-SNK

Solucoes para erros comuns e boas praticas de seguranca.

---

## Erros Comuns

| Erro | Solucao |
|------|---------|
| `ModuleNotFoundError: odoorpc` | `pip install odoorpc` |
| `ModuleNotFoundError: sankhya_sdk` | `pip install -r requirements.txt` |
| `ModuleNotFoundError: flask` | `pip install flask` (para `app_inspecao.py`) |
| `SANKHYA_CLIENT_ID nao configurado` | Preencha o `.env` com as credenciais |
| `Access Denied` (Odoo) | Verifique `ODOO_EMAIL` e `ODOO_SENHA` |
| `database does not exist` | Verifique `ODOO_DB` |
| `Wrong value for type` | Use `product`, `consu` ou `service` (Odoo 18) |
| `Connection refused` | Verifique se o servidor esta acessivel |
| `Arquivo SQL nao encontrado` | Verifique o caminho em `loginSNK/sql/` |
| `Credenciais Sankhya nao encontradas` | Verifique `SANKHYA_CLIENT_ID` e `SANKHYA_CLIENT_SECRET` no `.env` |
| `Missing Oracle environment variables` | Configure `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE_NAME`, etc. no `.env` |
| `Nao foi possivel localizar stock.warehouse` | Verifique se o modulo `stock` esta instalado no Odoo |
| `action_apply_inventory` falhou | O Odoo pode usar `apply_inventory` — o script tenta automaticamente o fallback |
| `stock` modulo uninstalled | Instale o modulo Inventario no Odoo antes de sincronizar estoque/locais |
| `quality.alert` nao encontrado | Verifique se o modulo de Qualidade esta instalado no Odoo |

---

## Checklist de Diagnostico

Se um script falhar sem mensagem clara, verifique:

1. **Variaveis de ambiente** — rode `python loginOdoo/conexao.py` e `python loginSNK/conexao.py` para testar as conexoes isoladamente
2. **Dependencias instaladas** — `pip install -r requirements.txt`
3. **Arquivo `.env`** — certifique-se de que existe e esta preenchido corretamente (nao confundir com `.env.example`)
4. **Ordem de execucao** — estoque depende de produtos e locais; consulte [quickstart.md](quickstart.md)
5. **Permissoes no Odoo** — o usuario configurado precisa ter acesso de leitura/escrita nos modelos sincronizados
6. **Modulos instalados no Odoo** — use `python verificar_modulos_odoo.py` para listar modulos ativos
7. **Modulo stock** — os scripts de estoque e locais requerem o modulo `stock` (Inventario) instalado

---

## Status Atual dos Modulos

Com base na ultima verificacao (20/04/2026):

| Modulo | Status |
|--------|--------|
| `product` | ✅ Instalado |
| `sale` | ✅ Instalado |
| `purchase` | ✅ Instalado |
| `stock` | ❌ Nao instalado |
| `hr` | ✅ Instalado |
| `l10n_br_fiscal` | ✅ Instalado |

> Para atualizar: `python verificar_modulos_odoo.py`

---

## Seguranca

- **Nunca versione** o `.env` com credenciais reais
- Use `.env.example` como modelo para novos ambientes
- Prefira HTTPS em producao para as conexoes com Odoo e Sankhya
- Todos os scripts validam variaveis obrigatorias antes de executar
- Revise periodicamente as permissoes do usuario de integracao no Odoo e no Sankhya
- Rotacione tokens OAuth2 do Sankhya conforme a politica da empresa
