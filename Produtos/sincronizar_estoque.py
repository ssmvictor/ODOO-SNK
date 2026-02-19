#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Estoque: Sankhya (TGFEST) → Odoo (stock.quant).

Lê os saldos de estoque do Sankhya via SQL (``DbExplorerSP.executeQuery``)
e ajusta as quantidades no modelo ``stock.quant`` do Odoo 19 Enterprise.

Pré-requisitos:
    - Produtos já sincronizados via ``sincronizar_produtos.py``
      (os produtos são localizados pelo ``default_code``).
    - Locais de estoque já sincronizados via ``sincronizar_locais.py``
      (os locais são localizados pelo ``barcode`` = CODLOCAL).

Fluxo:
    1. Autentica no Sankhya e executa ``loginSNK/sql/estoque.sql``.
    2. Conecta ao Odoo e pré-carrega mapa de produtos em cache.
    3. Para cada registro: faz upsert em ``stock.quant`` e aplica
       ``action_apply_inventory`` (com fallback para ``apply_inventory``).

Mapeamento:
    - CODPROD  → product_id   (via default_code em product.product)
    - CODLOCAL → location_id  (via barcode em stock.location)
    - ESTOQUE  → inventory_quantity

Uso::

    python Produtos/sincronizar_estoque.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

# Adicionar raiz do projeto ao sys.path para permitir execução direta
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# Imports
from dotenv import load_dotenv
from sankhya_sdk.auth.oauth_client import OAuthClient
from sankhya_sdk.http import SankhyaSession, GatewayClient
from loginOdoo.conexao import OdooConexao, criar_conexao as criar_conexao_odoo, OdooConfigError, OdooConnectionError
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn


def configurar_saida_utf8() -> None:
    """Força a codificação UTF-8 nos streams ``stdout`` e ``stderr``.

    Necessário no Windows para evitar erros de encoding ao exibir
    emojis e caracteres especiais via ``rich``.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


configurar_saida_utf8()

# Carregar .env
load_dotenv(PROJECT_ROOT / ".env")

console = Console()

# Constantes
SQL_PATH = PROJECT_ROOT / "loginSNK" / "sql" / "estoque.sql"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_BASE_URL = os.getenv("SANKHYA_AUTH_BASE_URL", "https://api.sankhya.com.br")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_TOKEN", "")

def criar_gateway_client() -> GatewayClient:
    """Autentica no Sankhya via OAuth2 e retorna um ``GatewayClient`` pronto.

    Returns:
        Instância de ``GatewayClient`` autenticada.

    Raises:
        RuntimeError: Se as credenciais Sankhya não estiverem no ``.env``.
    """
    oauth = OAuthClient(base_url=SANKHYA_BASE_URL, token=SANKHYA_X_TOKEN)
    if not SANKHYA_CLIENT_ID or not SANKHYA_CLIENT_SECRET:
        raise RuntimeError("Credenciais Sankhya não encontradas no .env")
    oauth.authenticate(SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET)
    session = SankhyaSession(oauth_client=oauth, base_url=SANKHYA_BASE_URL)
    return GatewayClient(session)

def carregar_sql(caminho: Path) -> str:
    """Lê e retorna o conteúdo de um arquivo SQL.

    Args:
        caminho: Caminho para o arquivo ``.sql``.

    Returns:
        Conteúdo do arquivo como string (sem espaços nas extremidades).

    Raises:
        FileNotFoundError: Se o arquivo não existir no caminho informado.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {caminho}")
    return caminho.read_text(encoding="utf-8").strip()

def buscar_dados_sankhya(client: GatewayClient, sql: str) -> list[dict[str, Any]]:
    """Executa o SQL no Sankhya via ``DbExplorerSP.executeQuery`` e retorna os registros.

    Args:
        client: ``GatewayClient`` já autenticado.
        sql:    Consulta SQL a executar.

    Returns:
        Lista de dicionários com os dados retornados pelo Sankhya.

    Raises:
        Exception: Se a resposta indicar erro.
    """
    response = client.execute_service("DbExplorerSP.executeQuery", {"sql": sql})
    if not GatewayClient.is_success(response):
        raise Exception(GatewayClient.get_error_message(response))
    
    body = response.get("responseBody", {})
    fields = body.get("fieldsMetadata", [])
    rows = body.get("rows", [])
    col_names = [f["name"] for f in fields]
    return [dict(zip(col_names, row)) for row in rows]

# Cache para evitar busca repetitiva
CACHE_PRODUTOS = {}
CACHE_LOCAIS = {}

def carregar_mapa_produtos_odoo(conexao: OdooConexao, lote: int = 1000) -> dict[str, int]:
    """Pré-carrega um mapa ``{default_code: product_id}`` para ``product.product``.

    Itera em lotes para suportar catálogos grandes, evitando timeout na API.

    Args:
        conexao: Conexão autenticada com o Odoo.
        lote:    Tamanho do lote de registros por chamada. Padrão: ``1000``.

    Returns:
        Dicionário mapeando o código interno do produto ao ID de ``product.product``.
    """
    mapa: dict[str, int] = {}
    offset = 0

    while True:
        produtos = conexao.search_read(
            "product.product",
            [["default_code", "!=", False]],
            ["id", "default_code"],
            limite=lote,
            offset=offset,
        )
        if not produtos:
            break

        for produto in produtos:
            codigo = str(produto.get("default_code", "")).strip()
            if codigo:
                mapa[codigo] = int(produto["id"])

        if len(produtos) < lote:
            break
        offset += lote

    return mapa

def buscar_id_produto(conexao: OdooConexao, codprod: str) -> int | None:
    """Busca o ID de ``product.product`` pelo código interno (``default_code``).

    Consulta primeiro o cache global ``CACHE_PRODUTOS`` (populado por
    :func:`carregar_mapa_produtos_odoo`). Faz chamada à API apenas se o
    produto não estiver em cache (ex: produto recém-criado).

    Args:
        conexao: Conexão autenticada com o Odoo.
        codprod: Código interno do produto (CODPROD no Sankhya).

    Returns:
        ID inteiro do ``product.product``, ou ``None`` se não encontrado.
    """
    if str(codprod) in CACHE_PRODUTOS: return CACHE_PRODUTOS[str(codprod)]
    # Fallback caso não esteja no cache carregado (ex: novos produtos)
    # ATENÇÃO: usa 'limite'
    res = conexao.search_read("product.product", [["default_code", "=", str(codprod)]], ["id"], limite=1)
    if res:
        pid = res[0]["id"]
        CACHE_PRODUTOS[str(codprod)] = pid
        return pid
    return None

def buscar_id_local(conexao: OdooConexao, codlocal: str) -> int | None:
    """Busca o ID de ``stock.location`` pelo código do local (``barcode``).

    Utiliza cache global ``CACHE_LOCAIS`` para evitar chamadas repetidas.

    Args:
        conexao:  Conexão autenticada com o Odoo.
        codlocal: Código do local de estoque do Sankhya (armazenado como ``barcode``).

    Returns:
        ID inteiro do ``stock.location``, ou ``None`` se não encontrado.
    """
    if str(codlocal) in CACHE_LOCAIS: return CACHE_LOCAIS[str(codlocal)]
    # Busca por barcode, usa 'limite'
    res = conexao.search_read("stock.location", [["barcode", "=", str(codlocal)]], ["id"], limite=1)
    if res:
        lid = res[0]["id"]
        CACHE_LOCAIS[str(codlocal)] = lid
        return lid
    return None

def atualizar_estoque(conexao: OdooConexao, dados: dict[str, Any]) -> str:
    """Cria ou atualiza um ``stock.quant`` e aplica o ajuste de inventário.

    Localiza o produto pelo ``CODPROD`` e o local pelo ``CODLOCAL``. Se algum
    dos dois não for encontrado, retorna uma string de status sem lançar exceção.
    Após o upsert do ``stock.quant``, chama ``action_apply_inventory``
    (com fallback para ``apply_inventory`` em versões alternativas do Odoo).

    Args:
        conexao: Conexão autenticada com o Odoo.
        dados:   Dicionário com os campos ``CODPROD``, ``CODLOCAL`` e ``ESTOQUE``
                 vindos do Sankhya.

    Returns:
        Uma das strings: ``'criado'``, ``'atualizado'``,
        ``'produto_nao_encontrado'`` ou ``'local_nao_encontrado'``.

    Raises:
        RuntimeError: Se ``action_apply_inventory`` e o fallback ``apply_inventory``
            falharem simultaneamente.
    """
    codprod = dados.get("CODPROD")
    codlocal = dados.get("CODLOCAL")
    estoque = float(dados.get("ESTOQUE", 0.0))
    # reservado = float(dados.get("RESERVADO", 0.0))
    
    # Busca IDs
    pid = buscar_id_produto(conexao, codprod)
    lid = buscar_id_local(conexao, codlocal)
    
    if not pid: return "produto_nao_encontrado"
    if not lid: return "local_nao_encontrado"
    
    # Upsert stock.quant
    modelo = "stock.quant"
    dominio = [["product_id", "=", pid], ["location_id", "=", lid]]
    # usa 'limite'
    quant = conexao.search_read(modelo, dominio, ["id", "inventory_quantity"], limite=1)
    
    vals = {
        "product_id": pid,
        "location_id": lid,
        "inventory_quantity": estoque,
    }
    
    if quant:
        qid = quant[0]["id"]
        conexao.atualizar(modelo, qid, vals)
        acao = "atualizado"
    else:
        qid = conexao.criar(modelo, vals)
        acao = "criado"
        
    # Aplicar inventário; falha aqui deve interromper o item
    erro_apply: Exception | None = None
    try:
        conexao.executar(modelo, "action_apply_inventory", args=[[qid]])
    except Exception as e:
        erro_apply = e
        try:
            # Fallback para versões com nome alternativo do método
            conexao.executar(modelo, "apply_inventory", args=[[qid]])
        except Exception as e2:
            raise RuntimeError(
                f"Falha ao aplicar inventário no quant {qid}: "
                f"action_apply_inventory={erro_apply}; apply_inventory={e2}"
            ) from e2
        
    return acao

def executar() -> None:
    """Ponto de entrada principal da sincronização de estoque.

    Executa o fluxo completo em três etapas:

    1. **Sankhya** — autentica via OAuth2 e executa ``loginSNK/sql/estoque.sql``,
       obtendo os saldos de estoque (CODPROD, CODLOCAL, ESTOQUE).
    2. **Odoo** — conecta e pré-carrega o cache de produtos para performance.
    3. **Sincronização** — para cada registro do Sankhya, chama
       :func:`atualizar_estoque` e exibe barra de progresso com ``rich``.

    Ao final, exibe um painel de resumo com os contadores:
    processados, ignorados (produto ou local não encontrado) e erros.
    """
    console.print(Panel.fit("[bold cyan]📦 Sincronização de Estoque[/bold cyan]"))
    
    # 1. Sankhya
    with console.status("[bold green]Lendo Sankhya..."):
        client = criar_gateway_client()
        sql = carregar_sql(SQL_PATH)
        estoque_snk = buscar_dados_sankhya(client, sql)
    
    console.print(f"[green]✅ {len(estoque_snk)} registros de estoque encontrados no Sankhya.[/green]")
    
    # 2. Odoo
    with console.status("[bold green]Conectando Odoo..."):
        conexao_odoo = criar_conexao_odoo()
    
    # Opcional: Pré-carregar produtos para performance
    with console.status("[bold green]Carregando cache de produtos..."):
        produtos_odoo = carregar_mapa_produtos_odoo(conexao_odoo)
        CACHE_PRODUTOS.update(produtos_odoo)
        
    # 3. Sincronizar
    processados = erros = ignorados = 0
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Sincronizando...", total=len(estoque_snk))
        
        for item in estoque_snk:
            try:
                res = atualizar_estoque(conexao_odoo, item)
                
                if res in ["produto_nao_encontrado", "local_nao_encontrado"]:
                    ignorados += 1
                else:
                    processados += 1
                    
                progress.update(task, advance=1, description=f"[cyan]Item {item.get('CODPROD')}")
                
            except Exception as e:
                erros += 1
                console.print(f"[red]Erro no item {item.get('CODPROD')}: {e}[/red]")
                progress.update(task, advance=1)

    # Resumo
    summary = Table(title="Resumo Estoque")
    summary.add_column("Status"); summary.add_column("Qtd")
    summary.add_row("Processados", str(processados), style="green")
    summary.add_row("Ignorados (Falta Prod/Local)", str(ignorados), style="yellow")
    summary.add_row("Erros", str(erros), style="red")
    console.print(Panel(summary, expand=False))

if __name__ == "__main__":
    executar()
