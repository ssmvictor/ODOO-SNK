#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Grupos: Sankhya (TGFGRU) → Odoo (product.category)
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
SQL_PATH = PROJECT_ROOT / "loginSNK" / "sql" / "grupos.sql"
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

def buscar_categoria_por_codigo(conexao: OdooConexao, codigo: str) -> dict[str, Any] | None:
    codigo = str(codigo).strip()
    if not codigo or codigo == "0":
        return None

    criterio_nome = f"[{codigo}]%"
    res = conexao.search_read(
        "product.category",
        [["name", "like", criterio_nome]],
        ["id", "name"],
        limite=1,
    )
    return res[0] if res else None


def buscar_id_categoria_pai(conexao: OdooConexao, cod_pai: str) -> bool | int:
    categoria = buscar_categoria_por_codigo(conexao, cod_pai)
    return categoria["id"] if categoria else False

def sincronizar_grupo(conexao: OdooConexao, dados: dict[str, Any]) -> tuple[str, int]:
    modelo = "product.category"
    codigo = str(dados.get("CODGRUPOPROD"))
    nome = dados.get("DESCRGRUPOPROD", f"Grupo {codigo}")
    
    # Formato: [CODIGO] Nome
    nome_odoo = f"[{codigo}] {nome}"
    
    # Preparar dados para Odoo
    vals = {
        "name": nome_odoo,
        # remove default_code pois não existe
    }

    # Buscar Pai
    # Nota: Assumimos que o Pai já foi processado (ordenado por GRAU)
    cod_pai = dados.get("CODGRUPAI")
    parent_id = buscar_id_categoria_pai(conexao, str(cod_pai))
    if parent_id:
        vals["parent_id"] = parent_id
    
    # Upsert por código estável ([CODIGO] ...)
    categoria_existente = buscar_categoria_por_codigo(conexao, codigo)
    
    if categoria_existente:
        cid = categoria_existente["id"]
        conexao.atualizar(modelo, cid, vals)
        return "atualizado", cid
    else:
        cid = conexao.criar(modelo, vals)
        return "criado", cid

def executar():
    console.print(Panel.fit("[bold magenta]📁 Sincronização de Grupos[/bold magenta]"))
    
    # 1. Sankhya
    with console.status("[bold green]Lendo Sankhya..."):
        client = criar_gateway_client()
        sql = carregar_sql(SQL_PATH)
        grupos_snk = buscar_dados_sankhya(client, sql)
    
    console.print(f"[green]✅ {len(grupos_snk)} grupos encontrados no Sankhya.[/green]")
    
    # 2. Odoo
    with console.status("[bold green]Conectando Odoo..."):
        conexao_odoo = criar_conexao_odoo()
    
    # 3. Sincronizar
    criados = updated = erros = 0
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Sincronizando...", total=len(grupos_snk))
        
        for grupo in grupos_snk:
            try:
                cod = grupo.get("CODGRUPOPROD")
                acao, _ = sincronizar_grupo(conexao_odoo, grupo)
                
                if acao == "criado": criados += 1
                else: updated += 1
                progress.update(task, advance=1, description=f"[green]Grupo {cod}")
                
            except Exception as e:
                erros += 1
                console.print(f"[red]Erro no grupo {grupo.get('CODGRUPOPROD')}: {e}[/red]")
                progress.update(task, advance=1)

    # Resumo
    summary = Table(title="Resumo Grupos")
    summary.add_column("Status"); summary.add_column("Qtd")
    summary.add_row("Criados", str(criados), style="green")
    summary.add_row("Atualizados", str(updated), style="yellow")
    summary.add_row("Erros", str(erros), style="red")
    console.print(Panel(summary, expand=False))

if __name__ == "__main__":
    executar()
