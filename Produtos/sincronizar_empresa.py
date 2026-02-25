#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Empresa: Sankhya (TSIEMP) → Odoo (res.company)

Lê os dados da empresa do Sankhya via SQL (DbExplorerSP) e
cria/atualiza no Odoo via OdooRPC.
"""

from __future__ import annotations


import os
import sys
from pathlib import Path
from typing import Any

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
    """Força UTF-8 na saída para evitar falhas com emoji no Windows."""
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
SQL_PATH = PROJECT_ROOT / "loginSNK" / "sql" / "empresa.sql"

console = Console()
_COUNTRY_CACHE: dict[str, int | None] = {}
_STATE_CACHE: dict[str, int | None] = {}
_CNAE_CACHE: dict[str, int | None] = {}
_LEGAL_NATURE_CACHE: dict[str, int | None] = {}

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


def buscar_empresas_sankhya(client: GatewayClient, sql: str) -> list[dict[str, Any]]:
    """Executa SQL na TSIEMP e retorna lista de dicionários."""
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

    console.print(f"[bold green]✅ {len(registros)} empresa(s) encontrada(s) no Sankhya[/bold green]")
    return registros


# ========== MAPEAMENTO SANKHYA → ODOO ==========

def resolver_pais(conexao_odoo: OdooConexao) -> int | None:
    """Busca o ID do país Brasil (BR)."""
    if "BR" in _COUNTRY_CACHE:
        return _COUNTRY_CACHE["BR"]
        
    res = conexao_odoo.search_read("res.country", [["code", "=", "BR"]], ["id"], limite=1)
    country_id = int(res[0]["id"]) if res else None
    _COUNTRY_CACHE["BR"] = country_id
    return country_id

def resolver_estado(conexao_odoo: OdooConexao, uf_code: str, country_id: int | None) -> int | None:
    """Busca o ID do estado (UF) no Odoo."""
    if not uf_code or not country_id:
        return None
        
    uf_code = uf_code.strip().upper()
    if uf_code in _STATE_CACHE:
        return _STATE_CACHE[uf_code]
        
    res = conexao_odoo.search_read(
        "res.country.state", 
        [["code", "=", uf_code], ["country_id", "=", country_id]], 
        ["id"], 
        limite=1
    )
    state_id = int(res[0]["id"]) if res else None
    _STATE_CACHE[uf_code] = state_id
    return state_id


def resolver_cnae(conexao_odoo: OdooConexao, codigo_cnae: str) -> int | None:
    """Busca o ID do CNAE no Odoo pelo código numérico."""
    if not codigo_cnae:
        return None

    codigo_cnae = str(codigo_cnae).strip()
    if codigo_cnae in _CNAE_CACHE:
        return _CNAE_CACHE[codigo_cnae]

    # Tenta buscar no modelo l10n_br_fiscal.cnae
    try:
        res = conexao_odoo.search_read(
            "l10n_br_fiscal.cnae",
            [["code", "=", codigo_cnae]],
            ["id"],
            limite=1,
        )
        cnae_id = int(res[0]["id"]) if res else None
    except Exception:
        cnae_id = None

    _CNAE_CACHE[codigo_cnae] = cnae_id
    return cnae_id


def resolver_natureza_juridica(conexao_odoo: OdooConexao, codigo_nat: str) -> int | None:
    """Busca o ID da Natureza Jurídica no Odoo pelo código."""
    if not codigo_nat:
        return None

    codigo_nat = str(codigo_nat).strip()
    if codigo_nat in _LEGAL_NATURE_CACHE:
        return _LEGAL_NATURE_CACHE[codigo_nat]

    # Tenta buscar no modelo l10n_br_fiscal.nature
    try:
        res = conexao_odoo.search_read(
            "l10n_br_fiscal.nature",
            [["code", "=", codigo_nat]],
            ["id"],
            limite=1,
        )
        nat_id = int(res[0]["id"]) if res else None
    except Exception:
        nat_id = None

    _LEGAL_NATURE_CACHE[codigo_nat] = nat_id
    return nat_id


def mapear_regime_tributario(cod_reg_trib: str) -> str | None:
    """Mapeia CODREGTRIB do Sankhya para tax_framework do Odoo.

    Sankhya: 1=Simples Nacional, 2=Simples Nacional Sublimite, 3=Regime Normal
    Odoo tax_framework: '1'=Simples Nacional, '2'=Simples Nacional Sublimite, '3'=Regime Normal
    """
    mapa = {
        "1": "1",  # Simples Nacional
        "2": "2",  # Simples Nacional - Sublimite
        "3": "3",  # Regime Normal
    }
    return mapa.get(str(cod_reg_trib).strip())


def mapear_empresa(
    emp_snk: dict[str, Any],
    conexao_odoo: OdooConexao,
) -> dict[str, Any]:
    """Mapeia campos da TSIEMP para res.company do Odoo."""

    razao_social = str(emp_snk.get("RAZAO_SOCIAL", "")).strip()
    nome_fantasia = str(emp_snk.get("NOME_FANTASIA", "")).strip()
    
    # Endereço
    tipo_logradouro = str(emp_snk.get("TIPO_LOGRADOURO", "")).strip()
    logradouro = str(emp_snk.get("LOGRADOURO", "")).strip()
    rua = f"{tipo_logradouro} {logradouro}".strip()
    
    # País e Estado
    country_id = resolver_pais(conexao_odoo)
    uf_code = str(emp_snk.get("CODIGO_UF", "")).strip()
    state_id = resolver_estado(conexao_odoo, uf_code, country_id)

    # Pegar apenas os números do CNPJ
    cnpj = str(emp_snk.get("CNPJ_CPF", "")).strip()
    cnpj_limpo = "".join(filter(str.isdigit, cnpj))

    dados_odoo = {
        "name": nome_fantasia or razao_social or f"Empresa {emp_snk.get('CODIGO_EMPRESA')}",
        "legal_name": razao_social,
        "vat": cnpj, # vat geralmente recebe formatado
        "company_registry": cnpj_limpo,
        "email": str(emp_snk.get("EMAIL", "")).strip(),
        "phone": str(emp_snk.get("TELEFONE", "")).strip(),
        "website": str(emp_snk.get("SITE", "")).strip(),
        
        # Endereço
        "street": rua,
        "street2": f"Nº {str(emp_snk.get('NUMERO', '')).strip()} - Bairro: {str(emp_snk.get('BAIRRO', '')).strip()} - Compl: {str(emp_snk.get('COMPLEMENTO', '')).strip()}",
        "city": str(emp_snk.get("CIDADE", "")).strip(),
        "zip": str(emp_snk.get("CEP", "")).strip(),
    }
    
    if country_id:
        dados_odoo["country_id"] = country_id
    if state_id:
        dados_odoo["state_id"] = state_id

    # Inscrições
    ie = str(emp_snk.get("INSCRICAO_ESTADUAL", "")).strip()
    if ie:
        dados_odoo["l10n_br_ie_code"] = ie

    im = str(emp_snk.get("INSCRICAO_MUNICIPAL", "")).strip()
    if im:
        dados_odoo["l10n_br_im_code"] = im

    # ===== DADOS FISCAIS (aba Fiscal do Odoo) =====

    # Estrutura Tributária (tax_framework)
    cod_reg_trib = str(emp_snk.get("CODIGO_REGIME_TRIBUTARIO", "")).strip()
    tax_framework = mapear_regime_tributario(cod_reg_trib)
    if tax_framework:
        dados_odoo["tax_framework"] = tax_framework

    # CNAE Principal
    cnae_code = str(emp_snk.get("CNAE_PREPONDERANTE", "")).strip()
    cnae_id = resolver_cnae(conexao_odoo, cnae_code)
    if cnae_id:
        dados_odoo["cnae_main_id"] = cnae_id
    elif cnae_code:
        console.print(f"[yellow]⚠️  CNAE '{cnae_code}' não encontrado no Odoo[/yellow]")

    # Natureza Jurídica
    nat_jur = str(emp_snk.get("NATUREZA_JURIDICA", "")).strip()
    nat_id = resolver_natureza_juridica(conexao_odoo, nat_jur)
    if nat_id:
        dados_odoo["legal_nature_id"] = nat_id
    elif nat_jur:
        console.print(f"[yellow]⚠️  Natureza Jurídica '{nat_jur}' não encontrada no Odoo[/yellow]")

    return dados_odoo


# ========== ODOO: ESCRITA ==========


def sincronizar_empresa(
    conexao_odoo: OdooConexao,
    dados_odoo: dict[str, Any],
    cnpj_limpo: str,
) -> tuple[str, int]:
    """Cria ou atualiza empresa no Odoo baseado no CNPJ/company_registry.

    Returns:
        Tupla (ação, id) onde ação é 'criado' ou 'atualizado'.
    """
    modelo = "res.company"
    
    # Tenta buscar por CNPJ limpo ou formatado
    dominio = ["|", ("vat", "ilike", cnpj_limpo), ("company_registry", "=", cnpj_limpo)]

    existentes = conexao_odoo.search_read(
        modelo,
        dominio=dominio,
        campos=["id"],
        limite=1,
    )

    if existentes:
        # Atualizar
        emp_id = existentes[0]["id"]
        conexao_odoo.atualizar(modelo, emp_id, dados_odoo)
        return ("atualizado", emp_id)
    else:
        # Tenta atualizar a empresa padrao (ID = 1) se ela nao tiver CNPJ configurado
        emp_1 = conexao_odoo.search_read(modelo, [["id", "=", 1]], ["vat"], limite=1)
        if emp_1 and not emp_1[0].get("vat"):
            emp_id = 1
            conexao_odoo.atualizar(modelo, emp_id, dados_odoo)
            return ("atualizado", emp_id)
        
        # Criar
        emp_id = conexao_odoo.criar(modelo, dados_odoo)
        return ("criado", emp_id)


# ========== ORQUESTRAÇÃO ==========


def executar_sincronizacao() -> None:
    """Fluxo principal: Sankhya → Odoo."""
    console.print(Panel.fit("[bold white]🔄 SINCRONIZAÇÃO DE EMPRESAS: SANKHYA → ODOO[/bold white]", style="bold blue"))

    # 1. Conexão Sankhya
    console.print("\n[bold cyan]📡 [1/4] Conectando ao Sankhya...[/bold cyan]")
    with console.status("[bold green]Autenticando...", spinner="dots"):
        client = criar_gateway_client()
    console.print("[bold green]✅ Sankhya conectado (OAuth2)[/bold green]")

    # 2. Carregar e executar SQL
    console.print("\n[bold cyan]📄 [2/4] Carregando SQL...[/bold cyan]")
    sql = carregar_sql(SQL_PATH)
    try:
        empresas_snk = buscar_empresas_sankhya(client, sql)
    except Exception as e:
         console.print(f"[bold red]❌ Falha na busca Sankhya:[/bold red] {e}")
         return

    if not empresas_snk:
        console.print("\n[bold yellow]⚠️  Nenhuma empresa para sincronizar. Encerrando.[/bold yellow]")
        return

    # Mostrar preview
    console.print("\n[bold white]📋 Preview das empresas:[/bold white]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("COD", style="dim")
    table.add_column("Razão Social")
    table.add_column("CNPJ")

    for e in empresas_snk[:5]:
        table.add_row(
            str(e.get("CODIGO_EMPRESA")), 
            str(e.get("RAZAO_SOCIAL", "N/A")), 
            str(e.get("CNPJ_CPF", "N/A"))
        )
    console.print(table)

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
    console.print(f"\n[bold cyan]🔄 [4/4] Sincronizando {len(empresas_snk)} empresa(s)...[/bold cyan]\n")

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
        task = progress.add_task("[green]Sincronizando...", total=len(empresas_snk))

        for i, emp_snk in enumerate(empresas_snk, 1):
            codemp = emp_snk.get("CODIGO_EMPRESA", "?")
            nome = emp_snk.get("NOME_FANTASIA") or emp_snk.get("RAZAO_SOCIAL", f"Empresa {codemp}")
            
            # Pegar CNPJ limpo para buscar no Odoo (chave de busca)
            cnpj = str(emp_snk.get("CNPJ_CPF", "")).strip()
            cnpj_limpo = "".join(filter(str.isdigit, cnpj))
            
            if not cnpj_limpo:
                erros += 1
                progress.console.print(f"[bold red]❌ Erro em {nome}:[/bold red] CNPJ não preenchido!")
                progress.update(task, advance=1)
                continue
            
            try:
                dados_odoo = mapear_empresa(emp_snk, conexao_odoo)
                acao, emp_id = sincronizar_empresa(conexao_odoo, dados_odoo, cnpj_limpo)

                if acao == "criado":
                    criados += 1
                else:
                    atualizados += 1
                
                progress.update(task, advance=1, description=f"[green]Processando {nome} ({acao})")

            except Exception as e:
                erros += 1
                progress.console.print(f"[bold red]❌ Erro em {nome}:[/bold red] {e}")
                progress.update(task, advance=1)

    # Resumo Final
    summary_table = Table(title="📊 Resumo da Sincronização", show_header=True)
    summary_table.add_column("Status", justify="right")
    summary_table.add_column("Quantidade", justify="right")
    
    summary_table.add_row("[blue]Total Processado[/blue]", str(len(empresas_snk)))
    summary_table.add_row("[green]🆕 Criados[/green]", str(criados))
    summary_table.add_row("[yellow]🔄 Atualizados[/yellow]", str(atualizados))
    summary_table.add_row("[red]❌ Erros[/red]", str(erros))

    console.print(Panel(summary_table, expand=False))


if __name__ == "__main__":
    executar_sincronizacao()
