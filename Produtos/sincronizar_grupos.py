#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Grupos: Sankhya (TGFGRU) → Odoo (product.category)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

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
    """Forca UTF-8 na saida para evitar falhas com emoji no Windows."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


configurar_saida_utf8()

# Carregar .env
load_dotenv(PROJECT_ROOT / ".env")

console = Console()
FIELDS_CACHE: dict[str, dict[str, Any]] = {}

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

def obter_campos_modelo(conexao: OdooConexao, modelo: str) -> dict[str, Any]:
    if modelo in FIELDS_CACHE:
        return FIELDS_CACHE[modelo]
    campos = conexao.executar(modelo, "fields_get")
    FIELDS_CACHE[modelo] = campos
    return campos


def primeiro_campo_disponivel(campos: dict[str, Any], candidatos: list[str], tipos: tuple[str, ...]) -> str | None:
    for nome in candidatos:
        if nome in campos and campos[nome].get("type") in tipos:
            return nome
    return None


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

def buscar_categoria_por_chave_externa(
    conexao: OdooConexao,
    campo_chave: str,
    codigo: str,
) -> dict[str, Any] | None:
    res = conexao.search_read(
        "product.category",
        [[campo_chave, "=", codigo]],
        ["id", "name", campo_chave],
        limite=1,
    )
    return res[0] if res else None

def validar_hierarquia_origem(grupos: list[dict[str, Any]]) -> tuple[int, int, int]:
    codigos = {str(g.get("CODGRUPOPROD", "")).strip() for g in grupos}
    mapa_pai: dict[str, str] = {}
    auto_referencia = 0
    orfaos = 0

    for g in grupos:
        cod = str(g.get("CODGRUPOPROD", "")).strip()
        pai = str(g.get("CODGRUPAI", "")).strip()
        if not cod:
            continue
        mapa_pai[cod] = pai
        if pai and pai not in ("0",) and pai == cod:
            auto_referencia += 1
        if pai and pai not in ("0", cod) and pai not in codigos:
            orfaos += 1

    ciclos = 0
    status: dict[str, int] = {k: 0 for k in mapa_pai}
    for cod in mapa_pai:
        if status.get(cod) == 2:
            continue
        atual = cod
        trilha: set[str] = set()
        while atual and atual in mapa_pai:
            if status.get(atual) == 2:
                break
            if atual in trilha:
                ciclos += 1
                break
            trilha.add(atual)
            proximo = mapa_pai.get(atual, "")
            if not proximo or proximo == "0" or proximo == atual:
                break
            atual = proximo
        for n in trilha:
            status[n] = 2

    return auto_referencia, orfaos, ciclos

def sincronizar_grupo(
    conexao: OdooConexao,
    dados: dict[str, Any],
    campo_chave: str | None,
    campo_pai_staging: str | None,
    campo_grau: str | None,
) -> tuple[str, int]:
    modelo = "product.category"
    codigo = str(dados.get("CODGRUPOPROD", "")).strip()
    nome = dados.get("DESCRGRUPOPROD", f"Grupo {codigo}")

    # Formato: [CODIGO] Nome
    nome_odoo = f"[{codigo}] {nome}"

    vals = {
        "name": nome_odoo,
    }

    if campo_chave:
        vals[campo_chave] = codigo
    if campo_pai_staging:
        vals[campo_pai_staging] = str(dados.get("CODGRUPAI", "")).strip()
    if campo_grau:
        grau_raw = dados.get("GRAU")
        try:
            vals[campo_grau] = int(grau_raw) if grau_raw is not None else 0
        except (TypeError, ValueError):
            vals[campo_grau] = 0

    categoria_existente = (
        buscar_categoria_por_chave_externa(conexao, campo_chave, codigo)
        if campo_chave
        else buscar_categoria_por_codigo(conexao, codigo)
    )

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
    campos_categoria = obter_campos_modelo(conexao_odoo, "product.category")
    campo_chave = primeiro_campo_disponivel(
        campos_categoria,
        ["x_sankhya_id", "x_codigo_sankhya", "x_studio_sankhya_id"],
        ("char", "integer"),
    )
    campo_pai_staging = primeiro_campo_disponivel(
        campos_categoria,
        ["x_parent_sankhya_id", "x_codigo_pai_sankhya", "x_studio_parent_sankhya_id"],
        ("char", "integer"),
    )
    campo_grau = primeiro_campo_disponivel(
        campos_categoria,
        ["x_grau", "x_studio_grau"],
        ("integer", "float", "char"),
    )

    auto_ref, orfaos_origem, ciclos_origem = validar_hierarquia_origem(grupos_snk)
    if auto_ref or orfaos_origem or ciclos_origem:
        console.print(
            f"[yellow]Validação origem Sankhya (grupos): auto_ref={auto_ref}, "
            f"órfãos={orfaos_origem}, ciclos={ciclos_origem}[/yellow]"
        )

    # 3. Passo A: upsert sem parent_id
    criados = updated = erros = 0
    cod_para_id: dict[str, int] = {}
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Passo A (base)...", total=len(grupos_snk))
        for grupo in grupos_snk:
            try:
                cod = str(grupo.get("CODGRUPOPROD", "")).strip()
                if not cod:
                    raise RuntimeError("CODGRUPOPROD vazio")
                acao, cid = sincronizar_grupo(conexao_odoo, grupo, campo_chave, campo_pai_staging, campo_grau)
                cod_para_id[cod] = cid
                if acao == "criado":
                    criados += 1
                else:
                    updated += 1
                progress.update(task, advance=1, description=f"[green]Grupo {cod}")
            except Exception as e:
                erros += 1
                console.print(f"[red]Erro no grupo {grupo.get('CODGRUPOPROD')}: {e}[/red]")
                progress.update(task, advance=1)

    # 4. Passo B: reconciliar parent_id
    pais_atualizados = 0
    erros_parent = 0
    orfaos_carga = 0
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Passo B (hierarquia)...", total=len(grupos_snk))
        for grupo in grupos_snk:
            try:
                cod = str(grupo.get("CODGRUPOPROD", "")).strip()
                cod_pai = str(grupo.get("CODGRUPAI", "")).strip()
                if not cod or not cod_pai or cod_pai in ("0",) or cod_pai == cod:
                    progress.update(task, advance=1)
                    continue
                filho_id = cod_para_id.get(cod)
                pai_id = cod_para_id.get(cod_pai)
                if not filho_id:
                    progress.update(task, advance=1)
                    continue
                if not pai_id:
                    pai_ref = (
                        buscar_categoria_por_chave_externa(conexao_odoo, campo_chave, cod_pai)
                        if campo_chave
                        else buscar_categoria_por_codigo(conexao_odoo, cod_pai)
                    )
                    pai_id = int(pai_ref["id"]) if pai_ref else None
                    if pai_id:
                        cod_para_id[cod_pai] = pai_id
                if not pai_id:
                    orfaos_carga += 1
                    progress.update(task, advance=1)
                    continue
                conexao_odoo.atualizar("product.category", filho_id, {"parent_id": pai_id})
                pais_atualizados += 1
                progress.update(task, advance=1, description=f"[cyan]Pai {cod} -> {cod_pai}")
            except Exception as e:
                erros_parent += 1
                console.print(f"[red]Erro ao vincular pai do grupo {grupo.get('CODGRUPOPROD')}: {e}[/red]")
                progress.update(task, advance=1)

    # Resumo
    summary = Table(title="Resumo Grupos")
    summary.add_column("Status"); summary.add_column("Qtd")
    summary.add_row("Criados", str(criados), style="green")
    summary.add_row("Atualizados", str(updated), style="yellow")
    summary.add_row("Erros", str(erros), style="red")
    summary.add_row("Pais atualizados", str(pais_atualizados), style="cyan")
    summary.add_row("Orfaos na carga", str(orfaos_carga), style="yellow")
    summary.add_row("Erros no passo B", str(erros_parent), style="red")
    summary.add_row("Auto-referencia origem", str(auto_ref), style="yellow")
    summary.add_row("Orfaos origem", str(orfaos_origem), style="yellow")
    summary.add_row("Ciclos origem", str(ciclos_origem), style="yellow")
    console.print(Panel(summary, expand=False))

if __name__ == "__main__":
    executar()
