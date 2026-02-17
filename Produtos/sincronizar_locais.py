#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Locais: Sankhya (TGFLOC) → Odoo (stock.location)
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

def validar_hierarquia_origem(locais: list[dict[str, Any]]) -> tuple[int, int, int]:
    codigos = {str(l.get("CODLOCAL", "")).strip() for l in locais}
    mapa_pai: dict[str, str] = {}
    auto_referencia = 0
    orfaos = 0
    for l in locais:
        cod = str(l.get("CODLOCAL", "")).strip()
        pai = str(l.get("CODLOCALPAI", "")).strip()
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

def mapear_local(
    dados: dict[str, Any],
    parent_id: int | None,
    campo_chave: str | None,
    campo_pai_staging: str | None,
    campo_grau: str | None,
) -> dict[str, Any]:
    vals: dict[str, Any] = {
        "name": dados.get("DESCRLOCAL", "Local Sankhya"),
        "barcode": str(dados.get("CODLOCAL", "")),
        "usage": "internal",
        "active": True,
    }
    if campo_chave:
        vals[campo_chave] = str(dados.get("CODLOCAL", "")).strip()
    if campo_pai_staging:
        vals[campo_pai_staging] = str(dados.get("CODLOCALPAI", "")).strip()
    if campo_grau:
        grau_raw = dados.get("GRAU")
        try:
            vals[campo_grau] = int(grau_raw) if grau_raw is not None else 0
        except (TypeError, ValueError):
            vals[campo_grau] = 0
    if parent_id is not None:
        vals["location_id"] = parent_id
    return vals

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


def buscar_local_por_codigo(conexao: OdooConexao, codlocal: str) -> dict[str, Any] | None:
    codlocal = str(codlocal).strip()
    if not codlocal:
        return None
    busca = conexao.search_read(
        "stock.location",
        [["barcode", "=", codlocal]],
        ["id", "name", "location_id"],
        limite=1,
    )
    return busca[0] if busca else None


def obter_local_estoque_padrao(conexao: OdooConexao) -> int:
    """Obtém o local interno padrão do depósito (ex.: WH/Stock)."""
    wh = conexao.search_read("stock.warehouse", [], ["id", "name", "lot_stock_id"], limite=1)
    if not wh or not wh[0].get("lot_stock_id"):
        raise RuntimeError("Não foi possível localizar stock.warehouse.lot_stock_id no Odoo.")
    return int(wh[0]["lot_stock_id"][0])


def ordenar_locais(local: dict[str, Any]) -> tuple[int, str]:
    grau = local.get("GRAU")
    try:
        grau_int = int(grau)
    except (TypeError, ValueError):
        grau_int = 999999
    codigo = str(local.get("CODLOCAL", ""))
    return grau_int, codigo

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
        local_estoque_padrao_id = obter_local_estoque_padrao(conexao_odoo)
    campos_local = obter_campos_modelo(conexao_odoo, "stock.location")
    campo_chave = primeiro_campo_disponivel(
        campos_local,
        ["x_sankhya_id", "x_codigo_sankhya", "x_studio_sankhya_id"],
        ("char", "integer"),
    )
    campo_pai_staging = primeiro_campo_disponivel(
        campos_local,
        ["x_parent_sankhya_id", "x_codigo_pai_sankhya", "x_studio_parent_sankhya_id"],
        ("char", "integer"),
    )
    campo_grau = primeiro_campo_disponivel(
        campos_local,
        ["x_grau", "x_studio_grau"],
        ("integer", "float", "char"),
    )

    auto_ref, orfaos_origem, ciclos_origem = validar_hierarquia_origem(locais_snk)
    if auto_ref or orfaos_origem or ciclos_origem:
        console.print(
            f"[yellow]Validação origem Sankhya (locais): auto_ref={auto_ref}, "
            f"órfãos={orfaos_origem}, ciclos={ciclos_origem}[/yellow]"
        )

    # 3. Passo A: base (sem depender de pai da origem)
    criados = updated = erros = 0
    codlocal_para_id: dict[str, int] = {}
    locais_ordenados = sorted(locais_snk, key=ordenar_locais)

    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Passo A (base)...", total=len(locais_ordenados))
        for local in locais_ordenados:
            try:
                codlocal = str(local.get("CODLOCAL", "")).strip()
                if not codlocal:
                    raise RuntimeError("CODLOCAL vazio")
                dados = mapear_local(
                    local,
                    parent_id=local_estoque_padrao_id,
                    campo_chave=campo_chave,
                    campo_pai_staging=campo_pai_staging,
                    campo_grau=campo_grau,
                )
                acao, local_id = sincronizar_local(conexao_odoo, dados)
                codlocal_para_id[codlocal] = local_id

                if acao == "criado": criados += 1
                else: updated += 1
                progress.update(task, advance=1, description=f"[green]{dados['name']}")
            except Exception as e:
                erros += 1
                console.print(f"[red]Erro em {local.get('CODLOCAL')}: {e}[/red]")
                progress.update(task, advance=1)

    # 4. Passo B: reconciliar location_id
    pais_atualizados = 0
    erros_parent = 0
    orfaos_carga = 0
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), BarColumn(), TaskProgressColumn(), console=console) as progress:
        task = progress.add_task("Passo B (hierarquia)...", total=len(locais_ordenados))
        for local in locais_ordenados:
            try:
                codlocal = str(local.get("CODLOCAL", "")).strip()
                codlocal_pai = str(local.get("CODLOCALPAI", "")).strip()
                if not codlocal:
                    progress.update(task, advance=1)
                    continue
                filho_id = codlocal_para_id.get(codlocal)
                if not filho_id:
                    progress.update(task, advance=1)
                    continue
                if not codlocal_pai or codlocal_pai in ("0",) or codlocal_pai == codlocal:
                    progress.update(task, advance=1)
                    continue

                pai_id = codlocal_para_id.get(codlocal_pai)
                if pai_id is None:
                    pai_existente = buscar_local_por_codigo(conexao_odoo, codlocal_pai)
                    if pai_existente:
                        pai_id = int(pai_existente["id"])
                        codlocal_para_id[codlocal_pai] = pai_id

                if pai_id is None:
                    orfaos_carga += 1
                    progress.update(task, advance=1)
                    continue

                conexao_odoo.atualizar("stock.location", filho_id, {"location_id": pai_id})
                pais_atualizados += 1
                progress.update(task, advance=1, description=f"[cyan]Pai {codlocal} -> {codlocal_pai}")
            except Exception as e:
                erros_parent += 1
                console.print(f"[red]Erro ao vincular pai de CODLOCAL={local.get('CODLOCAL')}: {e}[/red]")
                progress.update(task, advance=1)

    # Resumo
    summary = Table(title="Resumo Locais")
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
