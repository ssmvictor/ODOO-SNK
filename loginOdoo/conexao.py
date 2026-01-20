# -*- coding: utf-8 -*-
"""
Módulo de conexão com Odoo 18 via OdooRPC
Fornece classes e funções reutilizáveis para autenticação e comunicação com a API.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import odoorpc
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
    """Conexão com o Odoo via OdooRPC (JSON-RPC por padrão)."""
    
    def __init__(self, config: OdooConfig) -> None:
        """Inicializa a conexão com o Odoo.
        
        Args:
            config: Configuração de conexão.
        """
        self._config: OdooConfig = config
        self._odoo: Optional[odoorpc.ODOO] = None
        self._uid: Optional[int] = None
        self._conectado: bool = False
        
        # Extrair host e porta da URL
        self._host, self._port, self._protocol = self._parse_url(config.url)
    
    def _parse_url(self, url: str) -> tuple[str, int, str]:
        """Extrai host, porta e protocolo da URL.
        
        Args:
            url: URL completa (ex: 'http://localhost:8069' ou 'https://example.com')
            
        Returns:
            Tupla (host, porta, protocol)
        """
        # Remove protocolo
        if url.startswith('https://'):
            protocol = 'jsonrpc+ssl'
            url = url.replace('https://', '')
        elif url.startswith('http://'):
            protocol = 'jsonrpc'
            url = url.replace('http://', '')
        else:
            protocol = 'jsonrpc'
        
        # Extrai host e porta
        if ':' in url:
            host, port_str = url.split(':', 1)
            # Remove qualquer path após a porta
            port_str = port_str.split('/')[0]
            port = int(port_str)
        else:
            host = url.split('/')[0]
            port = 443 if protocol == 'jsonrpc+ssl' else 8069
        
        return host, port, protocol
    
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
    
    @property
    def odoo(self) -> Optional[odoorpc.ODOO]:
        """Retorna a instância OdooRPC (para uso avançado)."""
        return self._odoo
    
    def conectar(self) -> bool:
        """Estabelece conexão e autentica no Odoo.
        
        Returns:
            True se conectou com sucesso, False caso contrário.
        """
        try:
            # Cria instância OdooRPC
            self._odoo = odoorpc.ODOO(
                self._host, 
                protocol=self._protocol, 
                port=self._port,
                timeout=DEFAULT_TIMEOUT
            )
            
            # Autentica
            self._odoo.login(
                self._config.db,
                self._config.username,
                self._config.password
            )
            
            if hasattr(self._odoo.env, 'uid'):
                self._uid = self._odoo.env.uid  # type: ignore
            self._conectado = True
            
            print(f"[OK] Conectado ao Odoo como {self._config.username} (UID: {self._uid})")
            return True
            
        except odoorpc.error.RPCError as e:
            print(f"[ERRO] Erro RPC ao conectar: {e}")
            return False
        except Exception as e:
            print(f"[ERRO] Erro ao conectar: {e}")
            return False
    
    def obter_versao(self) -> Optional[str]:
        """Obtém a versão do servidor Odoo.
        
        Returns:
            String com a versão ou None se erro.
        """
        try:
            if self._odoo is None:
                # Cria conexão temporária para obter versão
                odoo_temp = odoorpc.ODOO(
                    self._host, 
                    protocol=self._protocol, 
                    port=self._port,
                    timeout=DEFAULT_TIMEOUT
                )
                version_info = odoo_temp.version
            else:
                version_info = self._odoo.version
            
            # OdooRPC retorna dict ou string dependendo do contexto
            if isinstance(version_info, dict):
                return version_info.get('server_version', 'N/A')
            return str(version_info) if version_info else 'N/A'
        except Exception as e:
            print(f"[ERRO] Erro ao obter versao: {e}")
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
        if not self._conectado or self._odoo is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        args = args or []
        
        # OdooRPC não aceita **kwargs diretamente, precisa incluir no args
        if kwargs:
            all_args = args + [kwargs]
        else:
            all_args = args
        
        # Usa o método execute do OdooRPC
        return self._odoo.execute(modelo, metodo, *all_args)
    
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
        if not self._conectado or self._odoo is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        dominio = dominio or []
        
        # Usa a API nativa do OdooRPC que é mais direta
        Model = self._odoo.env[modelo]  # type: ignore
        
        # search_read aceita dominio como primeiro arg e kwargs
        kwargs: dict[str, Any] = {
            'limit': limite,
            'offset': offset
        }
        
        if campos:
            kwargs['fields'] = campos
        if ordem:
            kwargs['order'] = ordem
        
        return Model.search_read(dominio, **kwargs)
    
    def criar(self, modelo: str, valores: dict[str, Any]) -> int:
        """Cria um novo registro.
        
        Args:
            modelo: Nome do modelo
            valores: Dicionário com os valores do registro
            
        Returns:
            ID do registro criado.
        """
        if not self._conectado or self._odoo is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        Model = self._odoo.env[modelo]  # type: ignore
        return Model.create(valores)
    
    def atualizar(self, modelo: str, ids: int | list[int], valores: dict[str, Any]) -> bool:
        """Atualiza registros existentes.
        
        Args:
            modelo: Nome do modelo
            ids: ID ou lista de IDs dos registros
            valores: Dicionário com os valores a atualizar
            
        Returns:
            True se sucesso.
        """
        if not self._conectado or self._odoo is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        if not isinstance(ids, list):
            ids = [ids]
        
        Model = self._odoo.env[modelo]  # type: ignore
        return Model.write(ids, valores)
    
    def excluir(self, modelo: str, ids: int | list[int]) -> bool:
        """Exclui registros.
        
        Args:
            modelo: Nome do modelo
            ids: ID ou lista de IDs dos registros
            
        Returns:
            True se sucesso.
        """
        if not self._conectado or self._odoo is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        if not isinstance(ids, list):
            ids = [ids]
        
        Model = self._odoo.env[modelo]  # type: ignore
        return Model.unlink(ids)


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

def _testar_conexao(config: OdooConfig) -> None:
    """Testa conexão via OdooRPC."""
    print("\n[1] Testando OdooRPC...")
    
    conexao = OdooConexao(config)
    versao = conexao.obter_versao()
    
    if versao:
        print(f"[OK] Conexao OK! Versao do Odoo: {versao}")
    
    print(f"\n[2] Autenticando usuario: {config.username}")
    
    if conexao.conectar():
        print("\n[3] Testando acesso aos modelos...")
        
        parceiros = conexao.search_read(
            'res.partner',
            campos=['name', 'email'],
            limite=3
        )
        
        print("[OK] Parceiros encontrados:")
        for p in parceiros:
            print(f"   - {p.get('name')} ({p.get('email', 'sem email')})")
        
        # Demonstração de uso avançado com OdooRPC
        if conexao.odoo:
            print("\n[4] Testando API nativa OdooRPC (uso avancado)...")
            user = conexao.odoo.env.user  # type: ignore
            print(f"[OK] Usuario conectado: {user.name}")
            if user.company_id:
                print(f"[OK] Empresa: {user.company_id.name}")


if __name__ == "__main__":
    print("=" * 50)
    print("TESTE DA API ODOORPC")
    print("=" * 50)
    
    try:
        config = carregar_configuracao()
    except OdooConfigError as e:
        print(f"[ERRO] Erro de configuracao: {e}")
        sys.exit(1)
    
    try:
        _testar_conexao(config)
    except OdooConnectionError as e:
        print(f"[ERRO] Erro de conexao: {e}")
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
    
    print("\n" + "=" * 50)
    print("TESTE CONCLUÍDO")
    print("=" * 50)
