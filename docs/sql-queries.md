# SQL Queries — ODOO-SNK

Documentacao das queries SQL utilizadas nas sincronizacoes. Todas ficam em `loginSNK/sql/` (Sankhya) e `producao/sql/` (Oracle/Rubi).

---

## Como as Queries sao Carregadas

Os scripts Python leem os arquivos `.sql` em tempo de execucao via `GatewayClient` (`DbExplorerSP.executeQuery`). Para personalizar uma query, basta editar o arquivo `.sql` correspondente — nao e necessario alterar o codigo Python.

Exemplo de carregamento no codigo:

```python
# Caminho tipico de carregamento
sql_path = Path(__file__).parent.parent / "loginSNK" / "sql" / "produtos.sql"
query = sql_path.read_text(encoding="utf-8")
```

---

## Queries do Sankhya (`loginSNK/sql/`)

### produtos.sql — Produtos Ativos

Retorna produtos ativos com filtro por codigo de produto.

```sql
SELECT * FROM TGFPRO PRO
  WHERE PRO.ATIVO = 'S'
  AND substr(PRO.CODPROD, 1, 2) = '20'
  AND substr(PRO.CODPROD, 6, 1) = '1'
```

**Campos retornados principais:** `CODPROD`, `DESCRPROD`, `REFFORN`, `PESOBRUTO`, `CODVOL`, `USOPROD`, `NCM`, `MARCA`, `CODLOCALPADRAO`

**Personalizacoes comuns:**
- Remover o filtro `substr` para sincronizar todos os produtos
- Adicionar filtro por empresa: `AND PRO.CODEMP = 1`
- Adicionar filtro por grupo: `AND PRO.CODGRUPOPROD = '20'`

---

### estoque.sql — Saldo de Estoque

Retorna saldos positivos de estoque, restrito aos produtos da query de produtos.

```sql
SELECT CODEMP, CODLOCAL, CODPROD, ESTOQUE, RESERVADO
FROM TGFEST
WHERE ESTOQUE > 0
  AND TGFEST.CODPROD IN (
    SELECT PRO.CODPROD FROM TGFPRO PRO
      WHERE PRO.ATIVO = 'S'
      AND substr(PRO.CODPROD, 1, 2) = '20'
      AND substr(PRO.CODPROD, 6, 1) = '1'
  )
```

**Personalizacoes comuns:**
- Filtrar por empresa: adicionar `AND CODEMP = 1` na query externa
- Filtrar por local especifico: `AND CODLOCAL IN (1, 2, 5)`
- Incluir estoque zerado: remover `WHERE ESTOQUE > 0`

---

### grupos.sql — Grupos de Produtos

Retorna todos os grupos ativos ordenados por nivel hierarquico.

```sql
SELECT CODGRUPOPROD, DESCRGRUPOPROD, CODGRUPAI, GRAU
FROM TGFGRU
WHERE ATIVO = 'S'
ORDER BY GRAU ASC
```

> A ordenacao por `GRAU ASC` e essencial para garantir que pais sejam criados antes dos filhos.

---

### locais.sql — Locais de Estoque

Retorna todos os locais ativos com hierarquia.

```sql
SELECT CODLOCAL, DESCRLOCAL, CODLOCALPAI, GRAU, ANALITICO
FROM TGFLOC
WHERE ATIVO = 'S'
ORDER BY GRAU, CODLOCAL
```

> A ordenacao por `GRAU, CODLOCAL` garante processamento hierarquico correto.

---

### parceiros.sql — Parceiros com Endereco Completo

Retorna parceiros ativos com joins para logradouro, bairro, cidade, estado e pais.

```sql
SELECT
  PAR.CODPARC,
  PAR.NOMEPARC,
  PAR.RAZAOSOCIAL,
  PAR.CGC_CPF,
  PAR.IDENTINSCESTAD,
  PAR.INSCESTADNAUF,
  PAR.TIPPESSOA,
  PAR.ATIVO,
  PAR.CLIENTE,
  PAR.FORNECEDOR,
  PAR.VENDEDOR,
  PAR.TRANSPORTADORA,
  PAR.MOTORISTA,
  PAR.EMAIL,
  PAR.TELEFONE,
  PAR.FAX,
  PAR.CEP,
  PAR.NUMEND,
  PAR.COMPLEMENTO,
  ENDR.NOMEEND,
  BAI.NOMEBAI,
  CID.NOMECID,
  UFS.UF AS UF_SIGLA,
  UFS.DESCRICAO AS UF_NOME,
  PAI.ABREVIATURA AS PAIS_SIGLA,
  PAI.DESCRICAO AS PAIS_NOME
FROM TGFPAR PAR
LEFT JOIN TSIEND ENDR ON ENDR.CODEND = PAR.CODEND
LEFT JOIN TSIBAI BAI  ON BAI.CODBAI  = PAR.CODBAI
LEFT JOIN TSICID CID  ON CID.CODCID  = PAR.CODCID
LEFT JOIN TSIUFS UFS  ON UFS.CODUF   = CID.UF
LEFT JOIN TSIPAI PAI  ON PAI.CODPAIS = UFS.CODPAIS
WHERE PAR.ATIVO = 'S'
```

**Personalizacoes comuns:**
- Filtrar apenas clientes: `AND PAR.CLIENTE = 'S'`
- Filtrar apenas fornecedores: `AND PAR.FORNECEDOR = 'S'`
- Incluir inativos: remover `WHERE PAR.ATIVO = 'S'`

---

### parceiros_vendedor.sql — Vinculo Parceiro/Vendedor

Retorna parceiros ativos com codigo de vendedor vinculado.

```sql
SELECT
  PAR.CODPARC,
  PAR.CODVEND,
  PAR.ATIVO,
  PAR.CLIENTE,
  PAR.VENDEDOR
FROM TGFPAR PAR
WHERE PAR.CODVEND IS NOT NULL
  AND PAR.ATIVO = 'S'
ORDER BY PAR.CODPARC
```

---

### vendedores.sql — Vendedores com Dados do Parceiro

Retorna vendedores ativos com dados do parceiro associado.

```sql
SELECT
  VEN.CODVEND,
  VEN.APELIDO,
  VEN.EMAIL AS EMAIL_VENDEDOR,
  VEN.ATIVO AS ATIVO_VENDEDOR,
  VEN.TIPVEND,
  VEN.CODPARC,
  PAR.NOMEPARC,
  PAR.RAZAOSOCIAL,
  PAR.EMAIL AS EMAIL_PARCEIRO,
  PAR.CGC_CPF,
  PAR.VENDEDOR,
  PAR.ATIVO AS ATIVO_PARCEIRO
FROM TGFVEN VEN
LEFT JOIN TGFPAR PAR ON PAR.CODPARC = VEN.CODPARC
WHERE VEN.ATIVO = 'S'
```

---

## Query Oracle/Rubi (`producao/sql/`)

### query.sql — Consulta Customizada

```sql
SELECT * FROM GRUPOAEL.SAN001
```

Esta query e de uso especifico do setor de producao. Edite conforme necessidade.

---

## Boas Praticas

- Sempre teste a query diretamente no banco antes de executar o script Python
- Use `WHERE ATIVO = 'S'` para evitar sincronizar registros inativos
- Prefira colunas explicitas (`SELECT col1, col2`) em vez de `SELECT *` em producao para evitar surpresas com colunas novas
- Para queries grandes, adicione `ROWNUM <= 100` temporariamente durante testes
