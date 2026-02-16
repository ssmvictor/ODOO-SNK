#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Produtos: Sankhya (TGFPRO) → Odoo (product.template)

Lê produtos ativos do Sankhya via SQL (DbExplorerSP) e
cria/atualiza no Odoo via OdooRPC.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional

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

# Raiz do projeto (script está em Produtos/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

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

# ========== SANKHYA: LEITURA ==========


def criar_gateway_client() -> GatewayClient:
    """Cria e autentica um GatewayClient Sankhya."""
    oauth = OAuthClient(base_url=SANKHYA_BASE_URL, token=SANKHYA_X_TOKEN)

    if not SANKHYA_CLIENT_ID or not SANKHYA_CLIENT_SECRET:
        raise RuntimeError(
            "SANKHYA_CLIENT_ID e SANKHYA_CLIENT_SECRET devem estar definidos no .env"
        )

    oauth.authenticate(SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET)
    session = SankhyaSession(oauth_client=oauth, base_url=SANKHYA_BASE_URL)
    return GatewayClient(session)


def carregar_sql(caminho: Path) -> str:
    """Carrega conteúdo SQL de um arquivo."""
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {caminho}")

    sql = caminho.read_text(encoding="utf-8").strip()
    console.print(f"📄 SQL carregado de: {caminho.name}")
    return sql


def buscar_produtos_sankhya(client: GatewayClient, sql: str) -> list[dict[str, Any]]:
    """Executa SQL na TGFPRO e retorna lista de dicionários."""
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


def mapear_produto(prod_snk: dict[str, Any]) -> dict[str, Any]:
    """Mapeia campos da TGFPRO para product.template do Odoo.

    Mapeamento:
        CODPROD     → default_code  (código interno)
        DESCRPROD   → name          (nome do produto)
        VLRVENDA    → list_price    (preço de venda)
        REFFORN     → barcode       (referência do fornecedor)
        PESOBRUTO   → weight        (peso)
        CODVOL      → uom (info)    (unidade de medida - apenas log)
        MARCA       → (campo custom ou ignorado)
    """
    codprod = str(prod_snk.get("CODPROD", "")).strip()
    descrprod = str(prod_snk.get("DESCRPROD", "")).strip()

    # Preço de venda
    vlrvenda = prod_snk.get("VLRVENDA")
    preco = float(vlrvenda) if vlrvenda is not None else 0.0

    # Peso bruto
    peso_bruto = prod_snk.get("PESOBRUTO")
    peso = float(peso_bruto) if peso_bruto is not None else 0.0

    # Referência do fornecedor como barcode (se existir)
    refforn = prod_snk.get("REFFORN")
    barcode = str(refforn).strip() if refforn else None

    dados_odoo: dict[str, Any] = {
        "name": descrprod or f"Produto {codprod}",
        "default_code": codprod,
        "list_price": preco,
        "weight": peso,
        "sale_ok": True,
        "purchase_ok": True,
        "type": "consu",  # Odoo 19 API: 'consu' (Mercadorias), 'service', 'combo'
    }


    if barcode:
        dados_odoo["barcode"] = barcode

    return dados_odoo


# ========== ODOO: ESCRITA ==========


def sincronizar_produto(
    conexao_odoo: OdooConexao,
    dados_odoo: dict[str, Any],
) -> tuple[str, int]:
    """Cria ou atualiza produto no Odoo baseado no default_code.

    Returns:
        Tupla (ação, id) onde ação é 'criado' ou 'atualizado'.
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
    """Fluxo principal: Sankhya → Odoo."""
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
    table.add_column("Preço")

    for p in produtos_snk[:5]:
        table.add_row(
            str(p.get("CODPROD")), 
            str(p.get("DESCRPROD", "N/A")), 
            f"R$ {p.get('VLRVENDA', 0):.2f}"
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
                dados_odoo = mapear_produto(prod_snk)
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
