#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronizacao de Parceiros: Sankhya (TGFPAR) -> Odoo (res.partner)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

from dotenv import load_dotenv
from sankhya_sdk.auth.oauth_client import OAuthClient
from sankhya_sdk.http import GatewayClient, SankhyaSession

from loginOdoo.conexao import (
    OdooConexao,
    OdooConfigError,
    OdooConnectionError,
    criar_conexao as criar_conexao_odoo,
)

from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table


def configurar_saida_utf8() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


configurar_saida_utf8()
load_dotenv(PROJECT_ROOT / ".env")

console = Console()
FIELDS_CACHE: dict[str, dict[str, Any]] = {}
COUNTRY_CACHE: dict[str, int | None] = {}
STATE_CACHE: dict[str, int | None] = {}

SANKHYA_CLIENT_ID = os.getenv("SANKHYA_CLIENT_ID", "")
SANKHYA_CLIENT_SECRET = os.getenv("SANKHYA_CLIENT_SECRET", "")
SANKHYA_BASE_URL = os.getenv("SANKHYA_AUTH_BASE_URL", "https://api.sankhya.com.br")
SANKHYA_X_TOKEN = os.getenv("SANKHYA_TOKEN", "")
SQL_PATH = PROJECT_ROOT / "loginSNK" / "sql" / "parceiros.sql"


def criar_gateway_client() -> GatewayClient:
    oauth = OAuthClient(base_url=SANKHYA_BASE_URL, token=SANKHYA_X_TOKEN)
    if not SANKHYA_CLIENT_ID or not SANKHYA_CLIENT_SECRET:
        raise RuntimeError("SANKHYA_CLIENT_ID e SANKHYA_CLIENT_SECRET devem estar definidos no .env")
    oauth.authenticate(SANKHYA_CLIENT_ID, SANKHYA_CLIENT_SECRET)
    session = SankhyaSession(oauth_client=oauth, base_url=SANKHYA_BASE_URL)
    return GatewayClient(session)


def carregar_sql(caminho: Path) -> str:
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo SQL nao encontrado: {caminho}")
    return caminho.read_text(encoding="utf-8").strip()


def buscar_parceiros_sankhya(client: GatewayClient, sql: str) -> list[dict[str, Any]]:
    response = client.execute_service(
        service_name="DbExplorerSP.executeQuery",
        request_body={"sql": sql},
    )
    if not GatewayClient.is_success(response):
        raise RuntimeError(f"Erro ao executar SQL: {GatewayClient.get_error_message(response)}")

    body = response.get("responseBody", {})
    fields_metadata = body.get("fieldsMetadata", [])
    rows = body.get("rows", [])
    colunas = [f["name"] for f in fields_metadata]
    return [dict(zip(colunas, row)) for row in rows]


def obter_campos_modelo(conexao_odoo: OdooConexao, modelo: str) -> dict[str, Any]:
    if modelo in FIELDS_CACHE:
        return FIELDS_CACHE[modelo]
    campos = conexao_odoo.executar(modelo, "fields_get")
    FIELDS_CACHE[modelo] = campos
    return campos


def primeiro_campo_disponivel(campos: dict[str, Any], candidatos: list[str], tipos: tuple[str, ...]) -> str | None:
    for nome in candidatos:
        if nome in campos and campos[nome].get("type") in tipos:
            return nome
    return None


def limpar_documento(valor: Any) -> str:
    bruto = str(valor or "").strip()
    return "".join(ch for ch in bruto if ch.isdigit())


def resolve_country_id(conexao_odoo: OdooConexao, sigla_pais: Any) -> int | None:
    sigla = str(sigla_pais or "").strip().upper()
    if not sigla:
        return None
    if sigla in COUNTRY_CACHE:
        return COUNTRY_CACHE[sigla]

    res = conexao_odoo.search_read("res.country", [["code", "=", sigla]], ["id"], limite=1)
    country_id = int(res[0]["id"]) if res else None
    COUNTRY_CACHE[sigla] = country_id
    return country_id


def resolve_state_id(conexao_odoo: OdooConexao, uf_sigla: Any, country_id: int | None) -> int | None:
    uf = str(uf_sigla or "").strip().upper()
    if not uf:
        return None

    chave = f"{uf}:{country_id or 0}"
    if chave in STATE_CACHE:
        return STATE_CACHE[chave]

    dominio: list[list[Any]] = [["code", "=", uf]]
    if country_id:
        dominio.append(["country_id", "=", country_id])

    res = conexao_odoo.search_read("res.country.state", dominio, ["id"], limite=1)
    state_id = int(res[0]["id"]) if res else None

    if state_id is None and country_id:
        res = conexao_odoo.search_read("res.country.state", [["code", "=", uf]], ["id"], limite=1)
        state_id = int(res[0]["id"]) if res else None

    STATE_CACHE[chave] = state_id
    return state_id


def mapear_parceiro(
    parc_snk: dict[str, Any],
    conexao_odoo: OdooConexao,
    campos_partner: dict[str, Any],
    campo_chave_externa: str | None,
) -> dict[str, Any]:
    codparc = str(parc_snk.get("CODPARC", "")).strip()
    razao = str(parc_snk.get("RAZAOSOCIAL") or "").strip()
    nome = str(parc_snk.get("NOMEPARC") or "").strip()
    tipo_pessoa = str(parc_snk.get("TIPPESSOA") or "").strip().upper()

    nome_final = razao or nome or f"Parceiro {codparc}"
    is_company = tipo_pessoa != "F"
    company_type = "company" if is_company else "person"

    rua = str(parc_snk.get("NOMEEND") or "").strip()
    numero = str(parc_snk.get("NUMEND") or "").strip()
    complemento = str(parc_snk.get("COMPLEMENTO") or "").strip()
    bairro = str(parc_snk.get("NOMEBAI") or "").strip()
    cidade = str(parc_snk.get("NOMECID") or "").strip()
    cep = str(parc_snk.get("CEP") or "").strip()
    email = str(parc_snk.get("EMAIL") or "").strip()
    telefone = str(parc_snk.get("TELEFONE") or "").strip()
    celular = str(parc_snk.get("FAX") or "").strip()
    ie = str(parc_snk.get("IDENTINSCESTAD") or "").strip()

    country_id = resolve_country_id(conexao_odoo, parc_snk.get("PAIS_SIGLA"))
    state_id = resolve_state_id(conexao_odoo, parc_snk.get("UF_SIGLA"), country_id)

    dados: dict[str, Any] = {
        "name": nome_final,
        "ref": codparc,
        "active": str(parc_snk.get("ATIVO", "S")).strip().upper() == "S",
    }
    if "company_type" in campos_partner:
        dados["company_type"] = company_type
    if "is_company" in campos_partner:
        dados["is_company"] = is_company

    if campo_chave_externa and campo_chave_externa != "ref":
        dados[campo_chave_externa] = codparc

    street_parts = [rua]
    if numero:
        street_parts.append(numero)
    street = ", ".join(part for part in street_parts if part)
    if street:
        dados["street"] = street
    if complemento:
        dados["street2"] = complemento
    elif bairro:
        dados["street2"] = bairro
    if cidade:
        dados["city"] = cidade
    if cep:
        dados["zip"] = cep
    if email:
        dados["email"] = email
    if telefone:
        dados["phone"] = telefone
    if celular:
        dados["mobile"] = celular
    if ie:
        if "l10n_br_ie" in campos_partner:
            dados["l10n_br_ie"] = ie
        elif "x_ie" in campos_partner and campos_partner["x_ie"].get("type") in ("char", "text"):
            dados["x_ie"] = ie
    if country_id:
        dados["country_id"] = country_id
    if state_id:
        dados["state_id"] = state_id

    cnpj_cpf = str(parc_snk.get("CGC_CPF") or "").strip()
    if cnpj_cpf:
        if "vat" in campos_partner:
            dados["vat"] = cnpj_cpf
        doc_limpo = limpar_documento(cnpj_cpf)
        if "l10n_br_cnpj_cpf" in campos_partner and doc_limpo:
            dados["l10n_br_cnpj_cpf"] = doc_limpo

    is_cliente = str(parc_snk.get("CLIENTE", "N")).strip().upper() == "S"
    is_fornecedor = str(parc_snk.get("FORNECEDOR", "N")).strip().upper() == "S"

    if "customer_rank" in campos_partner:
        dados["customer_rank"] = 1 if is_cliente else 0
    if "supplier_rank" in campos_partner:
        dados["supplier_rank"] = 1 if is_fornecedor else 0
    if "customer" in campos_partner:
        dados["customer"] = is_cliente
    if "supplier" in campos_partner:
        dados["supplier"] = is_fornecedor

    return dados


def buscar_parceiro_existente(
    conexao_odoo: OdooConexao,
    codigo: str,
    campo_chave_externa: str | None,
) -> dict[str, Any] | None:
    dominio: list[list[Any]]
    if campo_chave_externa:
        dominio = [[campo_chave_externa, "=", codigo]]
    else:
        dominio = [["ref", "=", codigo]]
    res = conexao_odoo.search_read("res.partner", dominio, ["id"], limite=1)
    return res[0] if res else None


def sincronizar_parceiro(
    conexao_odoo: OdooConexao,
    dados_odoo: dict[str, Any],
    campo_chave_externa: str | None,
) -> tuple[str, int]:
    codigo = str(dados_odoo.get("ref") or "").strip()
    existente = buscar_parceiro_existente(conexao_odoo, codigo, campo_chave_externa)
    if existente:
        partner_id = int(existente["id"])
        payload = {k: v for k, v in dados_odoo.items() if not (k == campo_chave_externa and campo_chave_externa == "ref")}
        conexao_odoo.atualizar("res.partner", partner_id, payload)
        return "atualizado", partner_id

    partner_id = int(conexao_odoo.criar("res.partner", dados_odoo))
    return "criado", partner_id


def executar_sincronizacao() -> None:
    console.print(Panel.fit("[bold blue]Sincronizacao de Parceiros: Sankhya -> Odoo[/bold blue]"))

    with console.status("[bold green]Conectando Sankhya...", spinner="dots"):
        client = criar_gateway_client()
        sql = carregar_sql(SQL_PATH)
        parceiros = buscar_parceiros_sankhya(client, sql)

    if not parceiros:
        console.print("[yellow]Nenhum parceiro retornado pela consulta.[/yellow]")
        return
    console.print(f"[green]{len(parceiros)} parceiro(s) encontrado(s) no Sankhya.[/green]")

    try:
        with console.status("[bold green]Conectando Odoo...", spinner="dots"):
            conexao_odoo = criar_conexao_odoo()
    except (OdooConfigError, OdooConnectionError) as exc:
        console.print(f"[red]Erro ao conectar Odoo: {exc}[/red]")
        sys.exit(1)

    campos_partner = obter_campos_modelo(conexao_odoo, "res.partner")
    campo_chave_externa = primeiro_campo_disponivel(
        campos_partner,
        ["x_sankhya_id", "x_codigo_sankhya", "x_studio_sankhya_id", "ref"],
        ("char", "integer"),
    )

    criados = 0
    atualizados = 0
    erros = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[green]Sincronizando parceiros...", total=len(parceiros))
        for parc in parceiros:
            codigo = str(parc.get("CODPARC") or "").strip() or "?"
            try:
                dados = mapear_parceiro(parc, conexao_odoo, campos_partner, campo_chave_externa)
                acao, _partner_id = sincronizar_parceiro(conexao_odoo, dados, campo_chave_externa)
                if acao == "criado":
                    criados += 1
                else:
                    atualizados += 1
                progress.update(task, advance=1, description=f"[green]Parceiro {codigo} ({acao})")
            except Exception as exc:
                erros += 1
                console.print(f"[red]Erro no parceiro {codigo}: {exc}[/red]")
                progress.update(task, advance=1)

    resumo = Table(title="Resumo da Sincronizacao de Parceiros")
    resumo.add_column("Status")
    resumo.add_column("Qtd", justify="right")
    resumo.add_row("Total", str(len(parceiros)))
    resumo.add_row("Criados", str(criados), style="green")
    resumo.add_row("Atualizados", str(atualizados), style="yellow")
    resumo.add_row("Erros", str(erros), style="red")
    console.print(Panel(resumo, expand=False))


if __name__ == "__main__":
    executar_sincronizacao()
