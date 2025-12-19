# -*- coding: utf-8 -*-
"""
Módulo de conexão com Odoo 18 via XML-RPC e JSON-RPC
Fornece classes e funções reutilizáveis para autenticação e comunicação com a API.
"""

from __future__ import annotations

import os
import sys
import xmlrpc.client
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv


# ========== EXCEÇÕES CUSTOMIZADAS ==========

class OdooError(Exception):
    """Exceção base para erros relacionados ao Odoo."""
    pass


class OdooConfigError(OdooError):
    """Exceção para erros de configuração do Odoo."""
    pass


class OdooConnectionError(OdooError):
    """Exceção para erros de conexão com o Odoo."""
    pass


# Constantes
DEFAULT_TIMEOUT: int = 30  # segundos


@dataclass
class OdooConfig:
    """Configuração de conexão com o Odoo."""
    url: str
    db: str
    username: str
    password: str

    def validar(self) -> list[str]:
        """Valida se todas as configurações estão preenchidas.
        
        Returns:
            Lista de campos faltantes (vazia se todos ok).
        """
        campos: dict[str, str | None] = {
            "ODOO_URL": self.url,
            "ODOO_DB": self.db,
            "ODOO_EMAIL": self.username,
            "ODOO_SENHA": self.password,
        }
        return [nome for nome, valor in campos.items() if not valor]


def carregar_configuracao(env_path: Optional[Path] = None) -> OdooConfig:
    """Carrega configuração do Odoo a partir do arquivo .env.
    
    Args:
        env_path: Caminho para o arquivo .env. Se None, usa a raiz do projeto.
        
    Returns:
        OdooConfig com as credenciais carregadas.
        
    Raises:
        OdooConfigError: Se variáveis obrigatórias não estiverem configuradas.
    """
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
    
    load_dotenv(env_path)
    
    config = OdooConfig(
        url=os.getenv("ODOO_URL", ""),
        db=os.getenv("ODOO_DB", ""),
        username=os.getenv("ODOO_EMAIL", ""),
        password=os.getenv("ODOO_SENHA", ""),
    )
    
    faltantes = config.validar()
    if faltantes:
        raise OdooConfigError(
            f"Variáveis de ambiente não configuradas: {', '.join(faltantes)}. "
            f"Configure no arquivo: {env_path}"
        )
    
    return config


class OdooConexao:
    """Conexão base com o Odoo via XML-RPC."""
    
    def __init__(self, config: OdooConfig) -> None:
        """Inicializa a conexão com o Odoo.
        
        Args:
            config: Configuração de conexão.
        """
        self._config: OdooConfig = config
        self._uid: Optional[int] = None
        self._models: Optional[xmlrpc.client.ServerProxy] = None
        self._conectado: bool = False
    
    @property
    def config(self) -> OdooConfig:
        """Retorna a configuração utilizada."""
        return self._config
    
    @property
    def uid(self) -> Optional[int]:
        """Retorna o User ID após autenticação."""
        return self._uid
    
    @property
    def conectado(self) -> bool:
        """Verifica se está conectado."""
        return self._conectado
    
    def conectar(self) -> bool:
        """Estabelece conexão e autentica no Odoo.
        
        Returns:
            True se conectou com sucesso, False caso contrário.
        """
        try:
            common = xmlrpc.client.ServerProxy(f'{self._config.url}/xmlrpc/2/common')
            self._uid = common.authenticate(
                self._config.db, 
                self._config.username, 
                self._config.password, 
                {}
            )
            
            if not self._uid:
                print("❌ Falha na autenticação! Verifique credenciais.")
                return False
            
            self._models = xmlrpc.client.ServerProxy(f'{self._config.url}/xmlrpc/2/object')
            self._conectado = True
            print(f"✅ Conectado ao Odoo como {self._config.username} (UID: {self._uid})")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}")
            return False
    
    def obter_versao(self) -> Optional[str]:
        """Obtém a versão do servidor Odoo.
        
        Returns:
            String com a versão ou None se erro.
        """
        try:
            common = xmlrpc.client.ServerProxy(f'{self._config.url}/xmlrpc/2/common')
            version = common.version()
            return version.get('server_version', 'N/A')
        except Exception as e:
            print(f"❌ Erro ao obter versão: {e}")
            return None
    
    def executar(
        self, 
        modelo: str, 
        metodo: str, 
        args: Optional[list[Any]] = None,
        kwargs: Optional[dict[str, Any]] = None
    ) -> Any:
        """Executa um método em um modelo do Odoo.
        
        Args:
            modelo: Nome do modelo (ex: 'res.partner')
            metodo: Nome do método (ex: 'search_read')
            args: Argumentos posicionais
            kwargs: Argumentos nomeados
            
        Returns:
            Resultado da chamada.
            
        Raises:
            ConnectionError: Se não estiver conectado.
        """
        if not self._conectado or self._models is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        args = args or []
        kwargs = kwargs or {}
        
        return self._models.execute_kw(
            self._config.db,
            self._uid,
            self._config.password,
            modelo,
            metodo,
            args,
            kwargs
        )
    
    def search_read(
        self,
        modelo: str,
        dominio: Optional[list[Any]] = None,
        campos: Optional[list[str]] = None,
        limite: int = 100,
        offset: int = 0,
        ordem: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Busca e lê registros de um modelo.
        
        Args:
            modelo: Nome do modelo
            dominio: Filtros de busca
            campos: Campos a retornar
            limite: Quantidade máxima de registros
            offset: Deslocamento para paginação
            ordem: Ordenação (ex: 'name asc')
            
        Returns:
            Lista de dicionários com os registros.
        """
        dominio = dominio or []
        kwargs: dict[str, Any] = {'limit': limite, 'offset': offset}
        
        if campos:
            kwargs['fields'] = campos
        if ordem:
            kwargs['order'] = ordem
        
        return self.executar(modelo, 'search_read', [dominio], kwargs)
    
    def criar(self, modelo: str, valores: dict[str, Any]) -> int:
        """Cria um novo registro.
        
        Args:
            modelo: Nome do modelo
            valores: Dicionário com os valores do registro
            
        Returns:
            ID do registro criado.
        """
        return self.executar(modelo, 'create', [valores])
    
    def atualizar(self, modelo: str, ids: int | list[int], valores: dict[str, Any]) -> bool:
        """Atualiza registros existentes.
        
        Args:
            modelo: Nome do modelo
            ids: ID ou lista de IDs dos registros
            valores: Dicionário com os valores a atualizar
            
        Returns:
            True se sucesso.
        """
        if not isinstance(ids, list):
            ids = [ids]
        return self.executar(modelo, 'write', [ids, valores])
    
    def excluir(self, modelo: str, ids: int | list[int]) -> bool:
        """Exclui registros.
        
        Args:
            modelo: Nome do modelo
            ids: ID ou lista de IDs dos registros
            
        Returns:
            True se sucesso.
        """
        if not isinstance(ids, list):
            ids = [ids]
        return self.executar(modelo, 'unlink', [ids])


class OdooConexaoJsonRpc:
    """Conexão alternativa via JSON-RPC."""
    
    def __init__(self, config: OdooConfig) -> None:
        """Inicializa a conexão JSON-RPC.
        
        Args:
            config: Configuração de conexão.
        """
        self._config: OdooConfig = config
        self._uid: Optional[int] = None
        self._request_id: int = 0
    
    @property
    def uid(self) -> Optional[int]:
        """Retorna o User ID após autenticação."""
        return self._uid
    
    def _fazer_requisicao(self, servico: str, metodo: str, args: list[Any]) -> Any:
        """Faz uma requisição JSON-RPC ao Odoo.
        
        Args:
            servico: Nome do serviço ('common', 'object')
            metodo: Nome do método
            args: Argumentos da chamada
            
        Returns:
            Resultado da chamada.
            
        Raises:
            OdooConnectionError: Se houver erro na requisição.
        """
        self._request_id += 1
        
        payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "service": servico,
                "method": metodo,
                "args": args
            },
            "id": self._request_id
        }
        
        try:
            response = requests.post(
                f"{self._config.url}/jsonrpc",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=DEFAULT_TIMEOUT
            )
            response.raise_for_status()
        except requests.Timeout:
            raise OdooConnectionError(f"Timeout: Requisição excedeu {DEFAULT_TIMEOUT} segundos.")
        except requests.HTTPError as e:
            raise OdooConnectionError(f"Erro HTTP: {e.response.status_code} - {e.response.text}")
        except requests.RequestException as e:
            raise OdooConnectionError(f"Erro na conexão: {e}")
        
        try:
            resultado = response.json()
        except ValueError as e:
            raise OdooConnectionError(f"Erro ao decodificar JSON da resposta: {e}")
        
        if "error" in resultado:
            raise OdooConnectionError(f"Erro JSON-RPC: {resultado['error']}")
        
        return resultado.get("result")
    
    def obter_versao(self) -> Optional[str]:
        """Obtém a versão do servidor Odoo.
        
        Returns:
            String com a versão ou None se erro.
        """
        try:
            resultado = self._fazer_requisicao("common", "version", [])
            return resultado.get("server_version", "N/A") if resultado else None
        except Exception as e:
            print(f"❌ Erro ao obter versão: {e}")
            return None
    
    def autenticar(self) -> bool:
        """Autentica o usuário no Odoo.
        
        Returns:
            True se autenticou com sucesso.
        """
        try:
            self._uid = self._fazer_requisicao(
                "common",
                "authenticate",
                [self._config.db, self._config.username, self._config.password, {}]
            )
            
            if self._uid:
                print(f"✅ Autenticação JSON-RPC OK! User ID: {self._uid}")
                return True
            else:
                print("❌ Autenticação JSON-RPC falhou!")
                return False
                
        except Exception as e:
            print(f"❌ Erro na autenticação: {e}")
            return False


def criar_conexao(config: Optional[OdooConfig] = None) -> OdooConexao:
    """Função utilitária para criar e conectar ao Odoo.
    
    Args:
        config: Configuração opcional. Se None, carrega do .env.
        
    Returns:
        OdooConexao já autenticada.
        
    Raises:
        OdooConnectionError: Se não conseguir conectar.
        OdooConfigError: Se as variáveis de ambiente não estiverem configuradas.
    """
    if config is None:
        config = carregar_configuracao()
    
    conexao = OdooConexao(config)
    
    if not conexao.conectar():
        raise OdooConnectionError("Não foi possível conectar ao Odoo.")
    
    return conexao


# ========== DEMONSTRAÇÃO / TESTE ==========

def _testar_xml_rpc(config: OdooConfig) -> None:
    """Testa conexão via XML-RPC."""
    print("\n[1] Testando XML-RPC...")
    
    conexao = OdooConexao(config)
    versao = conexao.obter_versao()
    
    if versao:
        print(f"✅ Conexão OK! Versão do Odoo: {versao}")
    
    print(f"\n[2] Autenticando usuário: {config.username}")
    
    if conexao.conectar():
        print("\n[3] Testando acesso aos modelos...")
        
        parceiros = conexao.search_read(
            'res.partner',
            campos=['name', 'email'],
            limite=3
        )
        
        print("✅ Parceiros encontrados:")
        for p in parceiros:
            print(f"   - {p.get('name')} ({p.get('email', 'sem email')})")


def _testar_json_rpc(config: OdooConfig) -> None:
    """Testa conexão via JSON-RPC."""
    print("\n[1] Testando JSON-RPC...")
    
    conexao = OdooConexaoJsonRpc(config)
    versao = conexao.obter_versao()
    
    if versao:
        print(f"✅ JSON-RPC funcionando! Versão: {versao}")
    
    print(f"\n[2] Autenticando via JSON-RPC: {config.username}")
    conexao.autenticar()


if __name__ == "__main__":
    print("=" * 50)
    print("TESTE DA API XML-RPC DO ODOO")
    print("=" * 50)
    
    try:
        config = carregar_configuracao()
    except OdooConfigError as e:
        print(f"❌ Erro de configuração: {e}")
        sys.exit(1)
    
    try:
        _testar_xml_rpc(config)
    except OdooConnectionError as e:
        print(f"❌ Erro de conexão: {e}")
    except Exception as e:
        print(f"❌ Erro XML-RPC: {e}")
    
    print("\n" + "=" * 50)
    print("TESTE DA API JSON-RPC DO ODOO")
    print("=" * 50)
    
    try:
        _testar_json_rpc(config)
    except OdooConnectionError as e:
        print(f"❌ Erro de conexão: {e}")
    except Exception as e:
        print(f"❌ Erro JSON-RPC: {e}")
    
    print("\n" + "=" * 50)
    print("TESTE CONCLUÍDO")
    print("=" * 50)
