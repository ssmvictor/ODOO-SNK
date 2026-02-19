#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Produtos: Sankhya (TGFPRO) → Odoo (product.template).

Lê os produtos ativos do Sankhya via SQL (``DbExplorerSP.executeQuery``)
e cria ou atualiza os registros correspondentes no modelo
``product.template`` do Odoo 19 Enterprise.

Fluxo:
    1. Autentica no Sankhya via OAuth2 e executa ``loginSNK/sql/produtos.sql``.
    2. Conecta ao Odoo via OdooRPC.
    3. Para cada produto: faz upsert baseado no ``default_code`` (CODPROD).

Mapeamento principal:
    - CODPROD       → default_code  (chave do upsert)
    - DESCRPROD     → name
    - REFFORN       → barcode
    - PESOBRUTO     → weight
    - CODVOL        → uom_id / uom_po_id
    - USOPROD       → type / is_storable  (R → consu/True, S → service/False)
    - NCM           → ncm / l10n_br_ncm_id  (se campo disponível no Odoo)
    - MARCA         → product_brand_id / x_marca  (se campo disponível)
    - CODLOCALPADRAO → x_local_padrao_id  (se campo disponível)

Uso::

    python Produtos/sincronizar_produtos.py
"""

from __future__ import annotations


import os
import sys
from pathlib import Path
from typing import Any, Optional

# Adicionar raiz do projeto ao sys.path para permitir execução direta
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv

from sankhya_sdk.auth.oauth_client import OAuthClient
from sankhya_sdk.http import SankhyaSession, GatewayClient

from loginOdoo.conexao import (
    OdooConexao,
    criar_conexao as criar_conexao_odoo,
    OdooConfigError,
    OdooConnectionError,
)

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import print as rprint


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

# Carregar .env da raiz do projeto
load_dotenv(PROJECT_ROOT / ".env")

# Credenciais Sankhya
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_BASE_URL = os.getenv("SANKHYA_AUTH_BASE_URL", "https://api.sankhya.com.br")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_TOKEN", "")

# Caminho do SQL
SQL_PATH = PROJECT_ROOT / "loginSNK" / "sql" / "produtos.sql"

console = Console()
_UOM_CACHE: dict[str, int | None] = {}
_UOM_NAO_ENCONTRADAS: set[str] = set()
_FIELDS_CACHE: dict[str, dict[str, Any]] = {}
_BRAND_CACHE: dict[str, int | None] = {}
_LOCAL_CACHE: dict[str, int | None] = {}

# ========== SANKHYA: LEITURA ==========


def criar_gateway_client() -> GatewayClient:
    """Autentica no Sankhya via OAuth2 e retorna um ``GatewayClient`` pronto.

    Lê as credenciais das variáveis de ambiente ``SANKHYA_CLIENT_ID``,
    ``SANKHYA_CLIENT_SECRET``, ``SANKHYA_TOKEN`` e ``SANKHYA_AUTH_BASE_URL``.

    Returns:
        Instância de ``GatewayClient`` autenticada.

    Raises:
        RuntimeError: Se ``SANKHYA_CLIENT_ID`` ou ``SANKHYA_CLIENT_SECRET``
            não estiverem definidos no ``.env``.
    """
    oauth = OAuthClient(base_url=SANKHYA_BASE_URL, token=SANKHYA_X_TOKEN)

    if not SANKHYA_CLIENT_ID or not SANKHYA_CLIENT_SECRET:
        raise RuntimeError(
            "SANKHYA_CLIENT_ID e SANKHYA_CLIENT_SECRET devem estar definidos no .env"
        )

    oauth.authenticate(SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET)
    session = SankhyaSession(oauth_client=oauth, base_url=SANKHYA_BASE_URL)
    return GatewayClient(session)


def carregar_sql(caminho: Path) -> str:
    """Lê e retorna o conteúdo de um arquivo SQL.

    Args:
        caminho: Caminho absoluto ou relativo para o arquivo ``.sql``.

    Returns:
        Conteúdo do arquivo como string (sem espaços nas extremidades).

    Raises:
        FileNotFoundError: Se o arquivo não existir no caminho informado.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {caminho}")

    sql = caminho.read_text(encoding="utf-8").strip()
    console.print(f"📄 SQL carregado de: {caminho.name}")
    return sql


def buscar_produtos_sankhya(client: GatewayClient, sql: str) -> list[dict[str, Any]]:
    """Executa o SQL informado via ``DbExplorerSP.executeQuery`` e retorna os produtos.

    Transforma o resultado (``fieldsMetadata`` + ``rows``) em uma lista de
    dicionários com os nomes das colunas como chaves.

    Args:
        client: ``GatewayClient`` já autenticado.
        sql:    Consulta SQL a executar (deve retornar colunas da TGFPRO).

    Returns:
        Lista de dicionários, um por produto retornado pelo Sankhya.

    Raises:
        Exception: Se a resposta do Sankhya indicar erro (``is_success`` = False).
    """
    console.print(Panel("🔍 Executando SQL no Sankhya...", style="cyan"))

    with console.status("[bold green]Consultando API Sankhya...", spinner="dots"):
        response = client.execute_service(
            service_name="DbExplorerSP.executeQuery",
            request_body={"sql": sql},
        )

    if not GatewayClient.is_success(response):
        error_msg = GatewayClient.get_error_message(response)
        console.print(f"[bold red]❌ Erro ao executar SQL:[/bold red] {error_msg}")
        raise Exception(f"Erro ao executar SQL: {error_msg}")

    body = response.get("responseBody", {})
    fields_metadata = body.get("fieldsMetadata", [])
    rows = body.get("rows", [])

    column_names = [field["name"] for field in fields_metadata]
    registros = [dict(zip(column_names, row)) for row in rows]

    console.print(f"[bold green]✅ {len(registros)} produto(s) encontrado(s) no Sankhya[/bold green]")
    return registros


# ========== MAPEAMENTO SANKHYA → ODOO ==========


def resolver_uom_odoo(conexao_odoo: OdooConexao, codvol: str) -> int | None:
    """Resolve o ``CODVOL`` do Sankhya para o ID de ``uom.uom`` no Odoo.

    Realiza busca exata por nome (case-insensitive). Utiliza cache local
    (``_UOM_CACHE``) para evitar chamadas repetidas à API. Quando o nome
    retornar mais de um resultado, a unidade é considerada ambígua e o
    produto será sincronizado sem alterar a unidade de medida.

    Args:
        conexao_odoo: Conexão autenticada com o Odoo.
        codvol:       Código de volume/unidade do Sankhya (ex: ``'UN'``, ``'KG'``).

    Returns:
        ID inteiro da ``uom.uom`` correspondente, ou ``None`` se não encontrada
        ou ambígua.
    """
    original = str(codvol or "").strip()
    if not original:
        return None

    chave = original.upper()
    if chave in _UOM_CACHE:
        return _UOM_CACHE[chave]

    dominios: list[list[list[str]]] = [
        [["name", "=", original]],
    ]
    if original != chave:
        dominios.append([["name", "=", chave]])

    uom_id: int | None = None
    for dominio in dominios:
        res = conexao_odoo.search_read("uom.uom", dominio, ["id", "name"], limite=2, ordem="id asc")
        if len(res) == 1:
            uom_id = int(res[0]["id"])
            break
        if len(res) > 1:
            console.print(
                f"[bold yellow]⚠ UoM ambigua para CODVOL='{original}' "
                "(mais de um resultado exato). Produto sera sincronizado sem alterar unidade.[/bold yellow]"
            )
            uom_id = None
            break

    _UOM_CACHE[chave] = uom_id
    return uom_id


def obter_campos_modelo(conexao_odoo: OdooConexao, modelo: str) -> dict[str, Any]:
    """Retorna os metadados de campos de um modelo Odoo com cache local.

    Chama ``fields_get`` apenas na primeira consulta; nas seguintes, retorna
    o resultado em cache (``_FIELDS_CACHE``).

    Args:
        conexao_odoo: Conexão autenticada com o Odoo.
        modelo:       Nome técnico do modelo (ex: ``'product.template'``).

    Returns:
        Dicionário ``{nome_campo: {type, string, ...}}`` com os metadados.
    """
    if modelo in _FIELDS_CACHE:
        return _FIELDS_CACHE[modelo]
    campos = conexao_odoo.executar(modelo, "fields_get")
    _FIELDS_CACHE[modelo] = campos
    return campos


def _normalizar_ncm(valor: Any) -> str:
    bruto = str(valor or "").strip()
    return "".join(ch for ch in bruto if ch.isdigit())


def resolver_marca_odoo(conexao_odoo: OdooConexao, relation_model: str, nome_marca: str) -> int | None:
    """Busca ou cria uma marca pelo nome para campos ``many2one`` de marca.

    Pesquisa pelo nome exato no modelo informado. Se não encontrar, tenta
    criar o registro. Utiliza cache local (``_BRAND_CACHE``) para evitar
    chamadas repetidas.

    Args:
        conexao_odoo:    Conexão autenticada com o Odoo.
        relation_model:  Modelo do campo many2one (ex: ``'product.brand'``).
        nome_marca:      Nome da marca a buscar ou criar.

    Returns:
        ID inteiro da marca no Odoo, ou ``None`` em caso de falha na criação.
    """
    chave = f"{relation_model}:{nome_marca.strip().upper()}"
    if not nome_marca.strip():
        return None
    if chave in _BRAND_CACHE:
        return _BRAND_CACHE[chave]

    res = conexao_odoo.search_read(
        relation_model,
        [["name", "=", nome_marca.strip()]],
        ["id", "name"],
        limite=1,
    )
    if res:
        marca_id = int(res[0]["id"])
        _BRAND_CACHE[chave] = marca_id
        return marca_id

    try:
        marca_id = int(conexao_odoo.criar(relation_model, {"name": nome_marca.strip()}))
    except Exception as exc:
        console.print(
            f"[bold yellow]⚠ Nao foi possivel criar marca '{nome_marca}' em {relation_model}: {exc}[/bold yellow]"
        )
        marca_id = None

    _BRAND_CACHE[chave] = marca_id
    return marca_id


def resolver_local_odoo_por_barcode(conexao_odoo: OdooConexao, codlocal: Any) -> int | None:
    chave = str(codlocal or "").strip()
    if not chave:
        return None
    if chave in _LOCAL_CACHE:
        return _LOCAL_CACHE[chave]

    res = conexao_odoo.search_read(
        "stock.location",
        [["barcode", "=", chave]],
        ["id"],
        limite=1,
    )
    local_id = int(res[0]["id"]) if res else None
    _LOCAL_CACHE[chave] = local_id
    return local_id


def aplicar_campos_complementares(
    conexao_odoo: OdooConexao,
    prod_snk: dict[str, Any],
    dados_odoo: dict[str, Any],
) -> None:
    """Aplica NCM, Marca e Local Padrão em campos disponíveis no Odoo.

    Inspeciona os metadados do modelo ``product.template`` e mapeia os
    campos ``NCM``, ``MARCA`` e ``CODLOCALPADRAO`` do Sankhya para os
    campos corretos do Odoo, com suporte a múltiplas convenções de
    nomenclatura (campos padrão, ``l10n_br_*``, ``x_*``, ``x_studio_*``).

    Args:
        conexao_odoo: Conexão autenticada com o Odoo.
        prod_snk:     Dicionário com os dados do produto vindo do Sankhya.
        dados_odoo:   Dicionário de dados do produto para o Odoo (modificado
                      in-place com os campos complementares encontrados).
    """
    campos_prod = obter_campos_modelo(conexao_odoo, "product.template")

    # NCM
    ncm = _normalizar_ncm(prod_snk.get("NCM"))
    if ncm:
        if "ncm" in campos_prod and campos_prod["ncm"].get("type") in ("char", "text"):
            dados_odoo["ncm"] = ncm
        elif "x_ncm" in campos_prod and campos_prod["x_ncm"].get("type") in ("char", "text"):
            dados_odoo["x_ncm"] = ncm
        elif "x_studio_ncm" in campos_prod and campos_prod["x_studio_ncm"].get("type") in ("char", "text"):
            dados_odoo["x_studio_ncm"] = ncm
        elif "l10n_br_ncm_id" in campos_prod and campos_prod["l10n_br_ncm_id"].get("type") == "many2one":
            rel = str(campos_prod["l10n_br_ncm_id"].get("relation") or "").strip()
            if rel:
                # Tenta localizar NCM por codigo exato
                ncm_res = conexao_odoo.search_read(rel, [["code", "=", ncm]], ["id"], limite=1)
                if ncm_res:
                    dados_odoo["l10n_br_ncm_id"] = int(ncm_res[0]["id"])

    # Marca
    marca = str(prod_snk.get("MARCA") or "").strip()
    if marca:
        if "product_brand_id" in campos_prod and campos_prod["product_brand_id"].get("type") == "many2one":
            rel = str(campos_prod["product_brand_id"].get("relation") or "product.brand")
            marca_id = resolver_marca_odoo(conexao_odoo, rel, marca)
            if marca_id:
                dados_odoo["product_brand_id"] = marca_id
        elif "x_marca" in campos_prod and campos_prod["x_marca"].get("type") in ("char", "text"):
            dados_odoo["x_marca"] = marca
        elif "x_studio_marca" in campos_prod and campos_prod["x_studio_marca"].get("type") in ("char", "text"):
            dados_odoo["x_studio_marca"] = marca

    # Local padrao do Sankhya (CODLOCALPADRAO)
    codlocal_padrao = str(prod_snk.get("CODLOCALPADRAO") or "").strip()
    if codlocal_padrao:
        if "x_codlocal_padrao" in campos_prod and campos_prod["x_codlocal_padrao"].get("type") in ("char", "text"):
            dados_odoo["x_codlocal_padrao"] = codlocal_padrao
        elif "x_studio_codlocal_padrao" in campos_prod and campos_prod["x_studio_codlocal_padrao"].get("type") in ("char", "text"):
            dados_odoo["x_studio_codlocal_padrao"] = codlocal_padrao
        elif "x_local_padrao_id" in campos_prod and campos_prod["x_local_padrao_id"].get("type") == "many2one":
            rel = str(campos_prod["x_local_padrao_id"].get("relation") or "").strip()
            if rel == "stock.location":
                local_id = resolver_local_odoo_por_barcode(conexao_odoo, codlocal_padrao)
                if local_id:
                    dados_odoo["x_local_padrao_id"] = local_id


def mapear_produto(
    prod_snk: dict[str, Any],
    conexao_odoo: OdooConexao,
) -> dict[str, Any]:
    """Converte um registro da TGFPRO para o formato de ``product.template`` do Odoo.

    Mapeamento:
        CODPROD        → default_code  (código interno, chave do upsert)
        DESCRPROD      → name          (nome do produto)
        (fixo 0.0)     → list_price    (preço — definido por tabela de preços)
        REFFORN        → barcode       (referência do fornecedor)
        PESOBRUTO      → weight        (peso bruto)
        CODVOL         → uom_id / uom_po_id (unidade de medida)
        USOPROD        → type / is_storable (``R`` → consu/True, ``S`` → service/False)
        NCM            → ncm / l10n_br_ncm_id (se campo disponível no Odoo)
        MARCA          → product_brand_id / x_marca (se campo disponível)
        CODLOCALPADRAO → x_codlocal_padrao / x_local_padrao_id (se campo disponível)

    Args:
        prod_snk:     Dicionário com os dados do produto vindo do Sankhya.
        conexao_odoo: Conexão autenticada com o Odoo (usada para resolver
                      UoM, marcas e campos complementares).

    Returns:
        Dicionário pronto para ser usado em :func:`sincronizar_produto`.
    """
    codprod = str(prod_snk.get("CODPROD", "")).strip()
    descrprod = str(prod_snk.get("DESCRPROD", "")).strip()

    # Produto nao comercializado: preco fixo zero
    preco = 0.0

    # Peso bruto
    peso_bruto = prod_snk.get("PESOBRUTO")
    peso = float(peso_bruto) if peso_bruto is not None else 0.0

    # Referência do fornecedor como barcode (se existir)
    refforn = prod_snk.get("REFFORN")
    barcode = str(refforn).strip() if refforn else None

    # Unidade padrão (Sankhya CODVOL -> Odoo uom.uom)
    codvol = str(prod_snk.get("CODVOL", "")).strip()
    uom_id = resolver_uom_odoo(conexao_odoo, codvol)

    # Mapeamento para Odoo 19:
    # - type: consu/service/combo
    # - is_storable: controla se o produto movimenta estoque
    usoprod = str(prod_snk.get("USOPROD", "R")).strip().upper()
    tipo_odoo = "consu"
    is_storable = True

    if usoprod == "S":
        tipo_odoo = "service"
        is_storable = False

    dados_odoo = {
        "name": descrprod or f"Produto {codprod}",
        "default_code": codprod,
        "list_price": preco,
        "weight": peso,
        "sale_ok": False,
        "purchase_ok": True,
        "type": tipo_odoo,
        "is_storable": is_storable,
    }


    if barcode:
        dados_odoo["barcode"] = barcode

    if uom_id:
        dados_odoo["uom_id"] = uom_id
        dados_odoo["uom_po_id"] = uom_id
    elif codvol and codvol not in _UOM_NAO_ENCONTRADAS:
        _UOM_NAO_ENCONTRADAS.add(codvol)
        console.print(
            f"[bold yellow]⚠ Unidade não encontrada no Odoo para CODVOL='{codvol}'. "
            "Produto será sincronizado sem alterar unidade.[/bold yellow]"
        )

    aplicar_campos_complementares(conexao_odoo, prod_snk, dados_odoo)

    return dados_odoo


# ========== ODOO: ESCRITA ==========


def sincronizar_produto(
    conexao_odoo: OdooConexao,
    dados_odoo: dict[str, Any],
) -> tuple[str, int]:
    """Cria ou atualiza um produto no Odoo baseado no ``default_code``.

    Busca o produto pelo ``default_code`` (CODPROD). Se não encontrar, cria
    um novo registro. Se encontrar, atualiza todos os campos exceto o próprio
    ``default_code``.

    Args:
        conexao_odoo: Conexão autenticada com o Odoo.
        dados_odoo:   Dicionário de campos mapeados por :func:`mapear_produto`.

    Returns:
        Tupla ``(acao, id)`` onde ``acao`` é ``'criado'`` ou ``'atualizado'``
        e ``id`` é o ID do registro no Odoo.
    """
    modelo = "product.template"
    codigo = dados_odoo["default_code"]

    # Buscar existente
    existentes = conexao_odoo.search_read(
        modelo,
        dominio=[["default_code", "=", codigo]],
        campos=["id"],
        limite=1,
    )

    if existentes:
        # Atualizar
        prod_id = existentes[0]["id"]
        valores_update = {k: v for k, v in dados_odoo.items() if k != "default_code"}
        conexao_odoo.atualizar(modelo, prod_id, valores_update)
        return ("atualizado", prod_id)
    else:
        # Criar
        prod_id = conexao_odoo.criar(modelo, dados_odoo)
        return ("criado", prod_id)


# ========== ORQUESTRAÇÃO ==========


def executar_sincronizacao() -> None:
    """Orquestra o fluxo completo de sincronização de produtos Sankhya → Odoo.

    Etapas:
        1. Autentica no Sankhya via OAuth2.
        2. Carrega e executa o SQL de produtos (``loginSNK/sql/produtos.sql``).
        3. Conecta ao Odoo via OdooRPC.
        4. Itera sobre os produtos e chama :func:`mapear_produto` +
           :func:`sincronizar_produto` para cada um, exibindo progresso
           visual via ``rich``.
        5. Exibe resumo final com totais de criados, atualizados e erros.
    """
    console.print(Panel.fit("[bold white]🔄 SINCRONIZAÇÃO DE PRODUTOS: SANKHYA → ODOO[/bold white]", style="bold blue"))

    # 1. Conexão Sankhya
    console.print("\n[bold cyan]📡 [1/4] Conectando ao Sankhya...[/bold cyan]")
    with console.status("[bold green]Autenticando...", spinner="dots"):
        client = criar_gateway_client()
    console.print("[bold green]✅ Sankhya conectado (OAuth2)[/bold green]")

    # 2. Carregar e executar SQL
    console.print("\n[bold cyan]📄 [2/4] Carregando SQL...[/bold cyan]")
    sql = carregar_sql(SQL_PATH)
    try:
        produtos_snk = buscar_produtos_sankhya(client, sql)
    except Exception as e:
         console.print(f"[bold red]❌ Falha na busca Sankhya:[/bold red] {e}")
         return

    if not produtos_snk:
        console.print("\n[bold yellow]⚠️  Nenhum produto para sincronizar. Encerrando.[/bold yellow]")
        return

    # Mostrar preview dos primeiros 5
    console.print("\n[bold white]📋 Preview dos primeiros produtos:[/bold white]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("CODPROD", style="dim")
    table.add_column("Descrição")
    table.add_column("Preço (Odoo)")

    for p in produtos_snk[:5]:
        table.add_row(
            str(p.get("CODPROD")), 
            str(p.get("DESCRPROD", "N/A")), 
            "R$ 0.00"
        )
    console.print(table)
    
    if len(produtos_snk) > 5:
        console.print(f"[italic]... e mais {len(produtos_snk) - 5} produto(s)[/italic]")

    # 3. Conexão Odoo
    console.print("\n[bold cyan]📡 [3/4] Conectando ao Odoo...[/bold cyan]")
    try:
        with console.status("[bold green]Conectando RPC...", spinner="dots"):
            conexao_odoo = criar_conexao_odoo()
        console.print(f"[bold green]✅ Conectado ao Odoo (UID: {conexao_odoo._uid})[/bold green]")
    except (OdooConfigError, OdooConnectionError) as e:
        console.print(f"[bold red]❌ Erro ao conectar ao Odoo:[/bold red] {e}")
        sys.exit(1)

    # 4. Sincronizar
    console.print(f"\n[bold cyan]🔄 [4/4] Sincronizando {len(produtos_snk)} produto(s)...[/bold cyan]\n")

    criados = 0
    atualizados = 0
    erros = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[green]Sincronizando...", total=len(produtos_snk))

        for i, prod_snk in enumerate(produtos_snk, 1):
            codprod = prod_snk.get("CODPROD", "?")
            
            try:
                dados_odoo = mapear_produto(prod_snk, conexao_odoo)
                acao, prod_id = sincronizar_produto(conexao_odoo, dados_odoo)

                if acao == "criado":
                    criados += 1
                else:
                    atualizados += 1
                
                progress.update(task, advance=1, description=f"[green]Processando {codprod} ({acao})")

            except Exception as e:
                erros += 1
                progress.console.print(f"[bold red]❌ Erro em {codprod}:[/bold red] {e}")
                progress.update(task, advance=1)

    # Resumo Final
    summary_table = Table(title="📊 Resumo da Sincronização", show_header=True)
    summary_table.add_column("Status", justify="right")
    summary_table.add_column("Quantidade", justify="right")
    
    summary_table.add_row("[blue]Total Processado[/blue]", str(len(produtos_snk)))
    summary_table.add_row("[green]🆕 Criados[/green]", str(criados))
    summary_table.add_row("[yellow]🔄 Atualizados[/yellow]", str(atualizados))
    summary_table.add_row("[red]❌ Erros[/red]", str(erros))

    console.print(Panel(summary_table, expand=False))


if __name__ == "__main__":
    executar_sincronizacao()
