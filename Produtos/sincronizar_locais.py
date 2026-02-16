#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Locais: Sankhya (TGFLOC) → Odoo (stock.location)
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

# Carregar .env
load_dotenv(PROJECT_ROOT / ".env")

console = Console()

# Constantes
SQL_PATH = PROJECT_ROOT / "loginSNK" / "sql" / "locais.sql"
SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_BASE_URL = os.getenv("SANKHYA_AUTH_BASE_URL", "https://api.sankhya.com.br")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_TOKEN", "")

def criar_gateway_client() -> GatewayClient:
    oauth = OAuthClient(base_url=SANKHYA_BASE_URL, token=SANKHYA_X_TOKEN)
    if not SANKHYA_CLIENT_ID or not SANKHYA_CLIENT_SECRET:
        raise RuntimeError("Credenciais Sankhya não encontradas no .env")
    oauth.authenticate(SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET)
    session = SankhyaSession(oauth_client=oauth, base_url=SANKHYA_BASE_URL)
    return GatewayClient(session)

def carregar_sql(caminho: Path) -> str:
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {caminho}")
    return caminho.read_text(encoding="utf-8").strip()

def buscar_dados_sankhya(client: GatewayClient, sql: str) -> list[dict[str, Any]]:
    response = client.execute_service("DbExplorerSP.executeQuery", {"sql": sql})
    if not GatewayClient.is_success(response):
        raise Exception(GatewayClient.get_error_message(response))
    
    body = response.get("responseBody", {})
    fields = body.get("fieldsMetadata", [])
    rows = body.get("rows", [])
    col_names = [f["name"] for f in fields]
    return [dict(zip(col_names, row)) for row in rows]

def mapear_local(dados: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": dados.get("DESCRLOCAL", "Local Sankhya"),
        "barcode": str(dados.get("CODLOCAL", "")),
        "usage": "internal",
        "active": True,
    }

def sincronizar_local(conexao: OdooConexao, dados: dict[str, Any]) -> tuple[str, int]:
    modelo = "stock.location"
    # Busca por barcode (que armazena o CODLOCAL)
    # ATENÇÃO: search_read do wrapper usa 'limite', não 'limit'
    busca = conexao.search_read(modelo, [["barcode", "=", dados["barcode"]]], ["id"], limite=1)
    
    if busca:
        lid = busca[0]["id"]
        conexao.atualizar(modelo, lid, dados)
        return "atualizado", lid
    else:
        # Tenta criar
        lid = conexao.criar(modelo, dados)
        return "criado", lid

def executar():
    console.print(Panel.fit("[bold blue]🏢 Sincronização de Locais[/bold blue]"))
    
    # 1. Sankhya
    with console.status("[bold green]Lendo Sankhya..."):
        client = criar_gateway_client()
        sql = carregar_sql(SQL_PATH)
        locais_snk = buscar_dados_sankhya(client, sql)
    
    console.print(f"[green]✅ {len(locais_snk)} locais encontrados no Sankhya.[/green]")
    
    # 2. Odoo
    with console.status("[bold green]Conectando Odoo..."):
        conexao_odoo = criar_conexao_odoo()
    
    # 3. Sincronizar
    criados = updated = erros = 0
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Sincronizando...", total=len(locais_snk))
        
        for local in locais_snk:
            try:
                dados = mapear_local(local)
                acao, _ = sincronizar_local(conexao_odoo, dados)
                if acao == "criado": criados += 1
                else: updated += 1
                progress.update(task, advance=1, description=f"[green]{dados['name']}")
            except Exception as e:
                erros += 1
                console.print(f"[red]Erro em {local.get('CODLOCAL')}: {e}[/red]")
                progress.update(task, advance=1)

    # Resumo
    summary = Table(title="Resumo Locais")
    summary.add_column("Status"); summary.add_column("Qtd")
    summary.add_row("Criados", str(criados), style="green")
    summary.add_row("Atualizados", str(updated), style="yellow")
    summary.add_row("Erros", str(erros), style="red")
    console.print(Panel(summary, expand=False))

if __name__ == "__main__":
    executar()
