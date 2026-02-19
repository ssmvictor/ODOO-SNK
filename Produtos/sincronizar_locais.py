#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Locais de Estoque: Sankhya (TGFLOC) → Odoo (stock.location).

Lê os locais de estoque do Sankhya via SQL e realiza upsert no modelo
``stock.location`` do Odoo, preservando a hierarquia pai/filho.

O processo é dividido em dois passos para evitar violações de integridade
referencial ao criar locais cujo pai ainda não existe:

- **Passo A** — upsert base: cria ou atualiza todos os locais usando o
  depósito padrão (``WH/Stock``) como ``location_id`` provisório. Os locais
  são ordenados pelo campo GRAU antes do processamento.
- **Passo B** — reconciliação de hierarquia: para cada local, busca o ID
  do pai (no mapa local ou via barcode) e atualiza ``location_id``.

O CODLOCAL é armazenado no campo ``barcode`` do ``stock.location``, o que
permite localizar registros existentes de forma inequívoca.

Antes do Passo A é feita uma validação da hierarquia de origem para
detectar auto-referências, órfãos e ciclos nos dados do Sankhya.

Mapeamento principal:
    - CODLOCAL    → barcode (chave de busca) e campo de chave externa (se disponível)
    - DESCRLOCAL  → name
    - CODLOCALPAI → location_id (via mapa local ou busca por barcode)
    - GRAU        → campo customizado de grau hierárquico (se disponível)

Pré-requisito:
    - Pelo menos um depósito (``stock.warehouse``) configurado no Odoo.

Uso::

    python Produtos/sincronizar_locais.py
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
    """Autentica no Sankhya via OAuth2 e retorna um ``GatewayClient`` pronto.

    Returns:
        Instância de ``GatewayClient`` autenticada.

    Raises:
        RuntimeError: Se as credenciais Sankhya não estiverem definidas no ``.env``.
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

def obter_campos_modelo(conexao: OdooConexao, modelo: str) -> dict[str, Any]:
    """Retorna os metadados dos campos de um modelo Odoo, com cache.

    Args:
        conexao: Conexão autenticada com o Odoo.
        modelo:  Nome técnico do modelo (ex.: ``stock.location``).

    Returns:
        Dicionário ``{nome_campo: metadados}`` conforme retornado por ``fields_get``.
    """
    if modelo in FIELDS_CACHE:
        return FIELDS_CACHE[modelo]
    campos = conexao.executar(modelo, "fields_get")
    FIELDS_CACHE[modelo] = campos
    return campos

def primeiro_campo_disponivel(campos: dict[str, Any], candidatos: list[str], tipos: tuple[str, ...]) -> str | None:
    """Retorna o primeiro campo da lista ``candidatos`` que existe no modelo e tem o tipo correto.

    Usado para selecionar adaptativamente o campo de chave externa, campo de código
    pai ou campo de grau, dependendo de quais campos customizados estão disponíveis
    na instalação Odoo do cliente.

    Args:
        campos:     Metadados dos campos do modelo (retorno de ``fields_get``).
        candidatos: Lista de nomes de campo em ordem de preferência.
        tipos:      Tipos aceitos (ex.: ``("char", "integer")``).

    Returns:
        Nome do primeiro campo compatível, ou ``None`` se nenhum for encontrado.
    """
    for nome in candidatos:
        if nome in campos and campos[nome].get("type") in tipos:
            return nome
    return None

def validar_hierarquia_origem(locais: list[dict[str, Any]]) -> tuple[int, int, int]:
    """Valida a hierarquia dos locais vindos do Sankhya antes de carregar no Odoo.

    Detecta auto-referências (CODLOCALPAI == CODLOCAL), órfãos (pai não existe
    na lista) e ciclos na cadeia de dependências pai/filho.

    Args:
        locais: Lista de dicionários com os dados dos locais do Sankhya.

    Returns:
        Tupla ``(auto_referencia, orfaos, ciclos)`` com as contagens de cada anomalia.
    """
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
    """Monta o dicionário de valores para criar ou atualizar um ``stock.location``.

    Define o ``name`` (DESCRLOCAL), ``barcode`` (CODLOCAL), ``usage`` como
    ``internal`` e ``active`` como ``True``. Se campos customizados estiverem
    disponíveis, grava também o código Sankhya, o código do pai (staging) e
    o grau hierárquico. Define ``location_id`` com o ``parent_id`` fornecido
    (inicialmente o depósito padrão; reconciliado no Passo B).

    Args:
        dados:             Dicionário com os campos do local (CODLOCAL, DESCRLOCAL,
                           CODLOCALPAI, GRAU).
        parent_id:         ID do local pai a usar no Passo A (depósito padrão).
        campo_chave:       Campo customizado de chave externa Sankhya, ou ``None``.
        campo_pai_staging: Campo customizado de código do pai Sankhya, ou ``None``.
        campo_grau:        Campo customizado de grau hierárquico, ou ``None``.

    Returns:
        Dicionário de valores pronto para ``criar`` ou ``atualizar`` no Odoo.
    """
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
    """Cria ou atualiza um ``stock.location`` no Odoo.

    Localiza o registro existente pelo ``barcode`` (= CODLOCAL). Se encontrado,
    atualiza; caso contrário, cria um novo.

    Args:
        conexao: Conexão autenticada com o Odoo.
        dados:   Dicionário de valores mapeado por :func:`mapear_local`
                 (deve conter a chave ``barcode``).

    Returns:
        Tupla ``(acao, id)`` onde ``acao`` é ``'criado'`` ou ``'atualizado'``
        e ``id`` é o ID do registro no Odoo.
    """
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
    """Localiza um ``stock.location`` pelo código do local (``barcode`` = CODLOCAL).

    Args:
        conexao:  Conexão autenticada com o Odoo.
        codlocal: Código do local de estoque do Sankhya.

    Returns:
        Primeiro registro encontrado (com ``id``, ``name`` e ``location_id``),
        ou ``None`` se não existir.
    """
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
    """Chave de ordenação para processar locais do menor grau para o maior.

    Locais com menor GRAU são criados primeiro, garantindo que os pais
    existam antes dos filhos no Passo A.

    Args:
        local: Dicionário com os dados de um local do Sankhya.

    Returns:
        Tupla ``(grau_int, codigo)`` usada como chave de comparação.
        Locais sem GRAU numérico válido recebem grau ``999999``.
    """
    grau = local.get("GRAU")
    try:
        grau_int = int(grau)
    except (TypeError, ValueError):
        grau_int = 999999
    codigo = str(local.get("CODLOCAL", ""))
    return grau_int, codigo

def executar() -> None:
    """Ponto de entrada principal da sincronização de locais de estoque.

    Executa o fluxo completo em quatro etapas:

    1. **Sankhya** — autentica e executa ``loginSNK/sql/locais.sql``.
    2. **Odoo** — conecta, obtém o depósito padrão, introspecciona campos e
       valida a hierarquia de origem.
    3. **Passo A** — upsert base de todos os locais (ordenados por GRAU),
       usando o depósito padrão como ``location_id`` provisório.
    4. **Passo B** — reconcilia a hierarquia pai/filho em ``location_id``.

    Exibe barra de progresso (``rich``) para cada passo e, ao final, um
    painel de resumo com contadores de criados, atualizados, erros,
    pais atualizados, órfãos e anomalias da origem.
    """
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
