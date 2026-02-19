#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sincronização de Funcionários: Oracle/Rubi (VETORH) → Odoo (hr.employee).

Consulta os funcionários ativos (e demitidos a partir de 01/01/2026) na base
Oracle do sistema Rubi (VETORH) e realiza upsert no modelo ``hr.employee``
do Odoo.

Fonte de dados:
    - Tabela principal: ``VETORH.R034FUN`` (cadastro de funcionários)
    - Centro de custo: ``VETORH.R038HCC`` + ``VETORH.R018CCU`` (setor/departamento)
    - Cargo: ``VETORH.R024CAR`` (título do cargo)
    - Empresa: ``NUMEMP = 11``, tipo de colaborador: ``TIPCOL = 1``

Mapeamento principal:
    - NUMCAD  → barcode (chave de busca no Odoo)
    - NOMFUN  → name
    - CARGO   → job_title
    - SETOR   → department_id (cria o departamento se não existir)
    - SITAFA  → active (``SITAFA != 7`` = ativo; ``SITAFA = 7`` = demitido)

Variáveis de ambiente necessárias (``.env``):
    - ``ORACLE_HOST``
    - ``ORACLE_PORT``
    - ``ORACLE_SERVICE_NAME``
    - ``ORACLE_USER``
    - ``ORACLE_PASSWORD``

Uso::

    python producao/sync_funcionarios.py
"""
import os
import oracledb
from dotenv import load_dotenv
import sys
from rich.console import Console
from rich.table import Table

# Adicionar raiz do projeto ao sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

from loginOdoo.conexao import criar_conexao, OdooConexao

# Inicializar console
console = Console()

# Carregar variáveis de ambiente
dotenv_path = os.path.join(project_root, ".env")
load_dotenv(dotenv_path)

# Configuração Oracle
DB_HOST = os.getenv("ORACLE_HOST")
DB_PORT = os.getenv("ORACLE_PORT")
DB_SERVICE = os.getenv("ORACLE_SERVICE_NAME")
DB_USER = os.getenv("ORACLE_USER")
DB_PASSWORD = os.getenv("ORACLE_PASSWORD")

def get_employees_from_rubi():
    """Conecta ao Oracle/Rubi e retorna os registros de funcionários.

    Executa consulta SQL nas tabelas VETORH que une funcionários (R034FUN),
    histórico de centro de custo (R038HCC), centros de custo (R018CCU) e
    cargos (R024CAR), filtrando pela empresa 11 e tipo de colaborador 1.

    Inclui apenas funcionários ativos ou demitidos a partir de 01/01/2026.

    Returns:
        Lista de dicionários com os campos: NUMCAD, NOMFUN, SETOR, DATALT,
        CARGO e SITAFA. Retorna lista vazia em caso de erro ou configuração
        incompleta.
    """
    if not all([DB_HOST, DB_PORT, DB_SERVICE, DB_USER, DB_PASSWORD]):
        console.print(f"[red]Error: Missing Oracle environment variables using .env at {dotenv_path}[/red]")
        return []

    dsn = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"
    
    try:
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=dsn
        )

        with connection.cursor() as cursor:
            # Consulta SQL para buscar funcionários
            sql = """
            SELECT FUN.NUMCAD, FUN.NOMFUN, CCU.NOMCCU AS SETOR, HCC.DATALT, CAR.TITCAR AS CARGO, FUN.SITAFA
              FROM VETORH.R034FUN FUN 
              LEFT JOIN VETORH.R038HCC HCC ON (HCC.NUMCAD = FUN.NUMCAD) AND (HCC.NUMEMP = FUN.NUMEMP) AND
                                         (HCC.TIPCOL = FUN.TIPCOL)
              LEFT JOIN VETORH.R018CCU CCU ON (CCU.NUMEMP = FUN.NUMEMP
                                          AND  CCU.CODCCU = HCC.CODCCU)
              LEFT JOIN VETORH.R024CAR CAR ON (CAR.CODCAR = FUN.CODCAR)
             WHERE FUN.NUMEMP = 11
               AND FUN.TIPCOL = 1
               AND (FUN.SITAFA <> 7 OR TRUNC(FUN.DATAFA) >= '01/01/2026')
             ORDER BY FUN.NUMCAD
            """
            
            cursor.execute(sql)
            
            # Obter nomes das colunas
            columns = [col[0] for col in cursor.description]
            
            # Buscar todas as linhas
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append(dict(zip(columns, row)))
            
            return results

    except oracledb.Error as e:
        console.print(f"[bold red]Erro Oracle:[/bold red] {e}")
        return []
    except Exception as e:
        console.print(f"[bold red]Erro:[/bold red] {e}")
        return []
    finally:
        if 'connection' in locals():
            connection.close()

def sync_employees(employees, odoo_conn: OdooConexao):
    """Sincroniza funcionários do Rubi para o Odoo.

    Para cada funcionário:

    - Busca ou cria o departamento (setor) no Odoo.
    - Localiza o ``hr.employee`` pelo ``barcode`` (= NUMCAD).
    - Se encontrado: atualiza nome, cargo, departamento e status ativo/inativo.
    - Se não encontrado e ativo: cria novo registro.
    - Se não encontrado e demitido: registra como ignorado na tabela de resumo.

    Exibe uma tabela ``rich`` com o resultado de cada funcionário processado.

    Args:
        employees: Lista de dicionários retornada por :func:`get_employees_from_rubi`.
        odoo_conn: Conexão autenticada com o Odoo.
    """
    console.print(f"\n[bold blue]Iniciando sincronização de {len(employees)} funcionários...[/bold blue]")
    
    table = Table(title="Resultado da Sincronização")
    table.add_column("Matrícula (NUMCAD)", style="cyan")
    table.add_column("Nome", style="magenta")
    table.add_column("Situação (Rubi)", style="yellow")
    table.add_column("Ação (Odoo)", style="green")
    
    # Cache de departamentos para evitar re-consultas
    departments = {}
    
    for emp in employees:
        numcad = str(emp['NUMCAD'])
        nomfun = emp['NOMFUN']
        titcar = emp['CARGO']
        sitafa = emp['SITAFA']
        setor_nome = emp.get('SETOR')
        data_admissao = emp.get('DATALT')  # Objeto datetime do Oracle

        # Determinar situação
        is_active = sitafa != 7
        status_str = "Ativo" if is_active else "Demitido"
        
        department_id = False
        if is_active and setor_nome:
            if setor_nome not in departments:
                # Verificar se o departamento já existe
                dept_search = odoo_conn.search_read('hr.department', dominio=[['name', '=', setor_nome]], campos=['id'])
                if dept_search:
                     departments[setor_nome] = dept_search[0]['id']
                else:
                     # Criar departamento
                     new_dept_id = odoo_conn.criar('hr.department', {'name': setor_nome})
                     departments[setor_nome] = new_dept_id
            
            department_id = departments[setor_nome]

        # Buscar funcionário existente no Odoo pelo barcode (NUMCAD)
        existing = odoo_conn.search_read(
            'hr.employee',
            dominio=[['barcode', '=', numcad]],
            campos=['id', 'name', 'active', 'job_title', 'department_id']
        )
        
        if existing:
            # Atualizar funcionário existente
            employee_id = existing[0]['id']
            odoo_active = existing[0]['active']
            
            vals = {}
            action = "Sem alteração"

            # Verificar necessidade de arquivar/desarquivar
            if odoo_active != is_active:
                vals['active'] = is_active
                action = "Arquivado" if not is_active else "Reativado"
            
            # Atualizar outros campos se ativo ou sendo reativado
            if is_active:
                if existing[0]['name'] != nomfun:
                   vals['name'] = nomfun
                   action = "Nome atualizado"
                if existing[0]['job_title'] != titcar:
                   vals['job_title'] = titcar
                   if action == "Sem alteração": action = "Cargo atualizado"
                   else: action += ", Cargo"
                
                # Verificar atualização de departamento
                current_dept_id = existing[0].get('department_id', [False])[0] if existing[0].get('department_id') else False
                if department_id and current_dept_id != department_id:
                    vals['department_id'] = department_id
                    if action == "Sem alteração": action = "Depto atualizado"
                    else: action += ", Depto"

                # Atualização de data de admissão (first_contract_date) — desativado
                # if data_admissao:
                #     date_str = data_admissao.strftime('%Y-%m-%d')
                #     current_date = existing[0].get('first_contract_date')
                #     if current_date != date_str:
                #         vals['first_contract_date'] = date_str
                #         if action == "Sem alteração": action = "Data atualizada"
                #         else: action += ", Data"
            
            if vals:
                odoo_conn.atualizar('hr.employee', employee_id, vals)
                if action == "Sem alteração": 
                    action = "Atualizado"
            
            table.add_row(numcad, nomfun, status_str, action)
            
        else:
            # Criar novo funcionário
            if is_active:
                vals = {
                    'name': nomfun,
                    'job_title': titcar,
                    'barcode': numcad,
                    'active': True
                }
                if department_id:
                    vals['department_id'] = department_id
                # if data_admissao:
                #    vals['first_contract_date'] = data_admissao.strftime('%Y-%m-%d')

                odoo_conn.criar('hr.employee', vals)
                table.add_row(numcad, nomfun, status_str, "Criado")
            else:
                table.add_row(numcad, nomfun, status_str, "Ignorado (Demitido e não encontrado)")

    console.print(table)

def main():
    """Ponto de entrada principal da sincronização de funcionários.

    Executa o fluxo:

    1. Busca funcionários no Oracle/Rubi via :func:`get_employees_from_rubi`.
    2. Conecta ao Odoo via :func:`criar_conexao`.
    3. Sincroniza todos os registros via :func:`sync_employees`.

    Interrompe a execução com mensagem de aviso se nenhum funcionário for
    encontrado no Rubi ou se a conexão ao Odoo falhar.
    """
    # 1. Buscar funcionários no Rubi
    employees = get_employees_from_rubi()
    
    if not employees:
        console.print("[yellow]Nenhum funcionário encontrado no Rubi ou ocorreu um erro.[/yellow]")
        return

    # 2. Conectar ao Odoo
    try:
        odoo_conn = criar_conexao()
    except Exception as e:
        console.print(f"[bold red]Falha ao conectar ao Odoo: {e}[/bold red]")
        return

    # 3. Sincronizar
    sync_employees(employees, odoo_conn)

if __name__ == "__main__":
    main()
