# Troubleshooting — ODOO-SNK

Solucoes para erros comuns e boas praticas de seguranca.

---

## Erros Comuns

| Erro | Solucao |
|------|---------|
| `ModuleNotFoundError: odoorpc` | `pip install odoorpc` |
| `ModuleNotFoundError: sankhya_sdk` | `pip install -r requirements.txt` |
| `SANKHYA_CLIENT_ID nao configurado` | Preencha o `.env` com as credenciais |
| `Access Denied` (Odoo) | Verifique `ODOO_EMAIL` e `ODOO_SENHA` |
| `database does not exist` | Verifique `ODOO_DB` |
| `Wrong value for type` | Use `consu`, `service` ou `combo` |
| `Connection refused` | Verifique se o servidor esta acessivel |
| `Arquivo SQL nao encontrado` | Verifique o caminho em `loginSNK/sql/` |
| `Credenciais Sankhya nao encontradas` | Verifique `SANKHYA_CLIENT_ID` e `SANKHYA_CLIENT_SECRET` no `.env` |
| `Missing Oracle environment variables` | Configure `ORACLE_HOST`, `ORACLE_PORT`, `ORACLE_SERVICE_NAME`, etc. no `.env` |
| `Nao foi possivel localizar stock.warehouse` | Verifique se o Odoo possui ao menos um deposito configurado |
| `action_apply_inventory` falhou | O Odoo pode usar `apply_inventory` — o script tenta automaticamente o fallback |

---

## Checklist de Diagnostico

Se um script falhar sem mensagem clara, verifique:

1. **Variaveis de ambiente** — rode `python loginOdoo/conexao.py` e `python loginSNK/conexao.py` para testar as conexoes isoladamente
2. **Dependencias instaladas** — `pip install -r requirements.txt`
3. **Arquivo `.env`** — certifique-se de que existe e esta preenchido corretamente (nao confundir com `.env.example`)
4. **Ordem de execucao** — estoque depende de produtos e locais; consulte [quickstart.md](quickstart.md)
5. **Permissoes no Odoo** — o usuario configurado precisa ter acesso de leitura/escrita nos modelos sincronizados
6. **Modulos instalados no Odoo** — use `python verificar_modulos_odoo.py` para listar modulos ativos

---

## Seguranca

- **Nunca versione** o `.env` com credenciais reais
- Use `.env.example` como modelo para novos ambientes
- Prefira HTTPS em producao para as conexoes com Odoo e Sankhya
- Todos os scripts validam variaveis obrigatorias antes de executar
- Revise periodicamente as permissoes do usuario de integracao no Odoo e no Sankhya
- Rotacione tokens OAuth2 do Sankhya conforme a politica da empresa
