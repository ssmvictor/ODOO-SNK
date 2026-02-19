# -*- coding: utf-8 -*-
"""
Módulo de conexão com o Odoo via OdooRPC (JSON-RPC).

Fornece classes e funções reutilizáveis para autenticação e comunicação
com a API do Odoo 19 Enterprise. Lê as credenciais do arquivo .env na
raiz do projeto.

Uso rápido::

    from loginOdoo.conexao import criar_conexao

    conexao = criar_conexao()
    parceiros = conexao.search_read('res.partner', campos=['name', 'email'])

Classes:
    OdooConfig         -- Dataclass com os parâmetros de conexão.
    OdooConexao        -- Gerencia conexão e operações CRUD no Odoo.

Funções:
    carregar_configuracao() -- Lê credenciais do .env.
    criar_conexao()         -- Cria e retorna conexão já autenticada.

Exceções:
    OdooError           -- Base para todos os erros deste módulo.
    OdooConfigError     -- Variáveis de ambiente ausentes ou inválidas.
    OdooConnectionError -- Falha ao conectar ou autenticar no Odoo.
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
    """Parâmetros de conexão com o Odoo.

    Attributes:
        url:      URL completa do servidor (ex: ``https://empresa.odoo.com``).
        db:       Nome do banco de dados Odoo.
        username: E-mail do usuário (variável ``ODOO_EMAIL``).
        password: Senha do usuário (variável ``ODOO_SENHA``).
    """

    url: str
    db: str
    username: str
    password: str

    def validar(self) -> list[str]:
        """Verifica se todas as credenciais estão preenchidas.

        Returns:
            Lista com os nomes das variáveis de ambiente faltantes.
            Retorna lista vazia quando todas estão configuradas.
        """
        campos: dict[str, str | None] = {
            "ODOO_URL": self.url,
            "ODOO_DB": self.db,
            "ODOO_EMAIL": self.username,
            "ODOO_SENHA": self.password,
        }
        return [nome for nome, valor in campos.items() if not valor]


def carregar_configuracao(env_path: Optional[Path] = None) -> OdooConfig:
    """Carrega as credenciais do Odoo a partir do arquivo ``.env``.

    Args:
        env_path: Caminho para o arquivo ``.env``.
                  Se ``None``, usa ``<raiz_do_projeto>/.env``.

    Returns:
        :class:`OdooConfig` populado com as credenciais lidas.

    Raises:
        OdooConfigError: Quando uma ou mais variáveis obrigatórias
            (``ODOO_URL``, ``ODOO_DB``, ``ODOO_EMAIL``, ``ODOO_SENHA``)
            não estiverem definidas no arquivo ``.env``.
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
    """Conexão com o Odoo via OdooRPC (protocolo JSON-RPC / JSON-RPC+SSL).

    Encapsula autenticação e operações CRUD básicas, expondo métodos
    em português para facilitar o uso nos scripts de sincronização.

    Exemplo de uso::

        config = carregar_configuracao()
        conn = OdooConexao(config)
        conn.conectar()

        registros = conn.search_read('res.partner', campos=['name'])
        novo_id   = conn.criar('product.template', {'name': 'Teste'})
        conn.atualizar('product.template', novo_id, {'list_price': 10.0})
        conn.excluir('product.template', novo_id)
    """
    
    def __init__(self, config: OdooConfig) -> None:
        """Inicializa os atributos internos da conexão sem abrir socket.

        A conexão efetiva só é aberta ao chamar :meth:`conectar`.

        Args:
            config: Instância de :class:`OdooConfig` com as credenciais.
        """
        self._config: OdooConfig = config
        self._odoo: Optional[odoorpc.ODOO] = None
        self._uid: Optional[int] = None
        self._conectado: bool = False
        
        # Extrair host e porta da URL
        self._host, self._port, self._protocol = self._parse_url(config.url)
    
    def _parse_url(self, url: str) -> tuple[str, int, str]:
        """Extrai host, porta e protocolo OdooRPC a partir de uma URL.

        Args:
            url: URL completa, ex: ``'http://localhost:8069'``
                 ou ``'https://empresa.odoo.com'``.

        Returns:
            Tupla ``(host, porta, protocolo)`` onde ``protocolo`` é
            ``'jsonrpc'`` para HTTP ou ``'jsonrpc+ssl'`` para HTTPS.
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
        """Abre a conexão JSON-RPC e autentica o usuário no Odoo.

        Instancia o objeto OdooRPC, chama ``login`` e armazena o UID
        do usuário autenticado em :attr:`uid`.

        Returns:
            ``True`` em caso de sucesso; ``False`` se ocorrer qualquer erro.
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
        """Consulta a versão do servidor Odoo sem autenticação.

        Returns:
            String com a versão (ex: ``'19.0'``) ou ``None`` em caso de erro.
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
        """Executa um método arbitrário em um modelo do Odoo via RPC.

        Útil para chamar métodos que não possuem wrapper dedicado, como
        ``fields_get``, ``action_apply_inventory``, etc.

        Args:
            modelo: Nome técnico do modelo (ex: ``'res.partner'``).
            metodo: Nome do método a chamar (ex: ``'fields_get'``).
            args:   Lista de argumentos posicionais. Padrão: ``[]``.
            kwargs: Dicionário de argumentos nomeados. Quando fornecido,
                    é adicionado ao final da lista de argumentos.

        Returns:
            Valor retornado pelo método no servidor Odoo.

        Raises:
            ConnectionError: Se :meth:`conectar` ainda não foi chamado.
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
        """Busca e retorna registros de um modelo com filtros opcionais.

        Equivalente ao método ``search_read`` da ORM do Odoo.

        Args:
            modelo:  Nome técnico do modelo (ex: ``'product.template'``).
            dominio: Lista de triplas de domínio Odoo para filtrar registros.
                     Ex: ``[['active', '=', True]]``. Padrão: ``[]`` (sem filtro).
            campos:  Lista de campos a incluir no resultado.
                     Padrão: todos os campos.
            limite:  Quantidade máxima de registros a retornar. Padrão: ``100``.
            offset:  Número de registros a pular (paginação). Padrão: ``0``.
            ordem:   Critério de ordenação (ex: ``'name asc'``).

        Returns:
            Lista de dicionários, cada um representando um registro.

        Raises:
            ConnectionError: Se :meth:`conectar` ainda não foi chamado.
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
        """Cria um novo registro no modelo informado.

        Args:
            modelo:  Nome técnico do modelo (ex: ``'product.template'``).
            valores: Dicionário ``{campo: valor}`` com os dados do registro.

        Returns:
            ID (inteiro) do registro recém-criado.

        Raises:
            ConnectionError: Se :meth:`conectar` ainda não foi chamado.
        """
        if not self._conectado or self._odoo is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        Model = self._odoo.env[modelo]  # type: ignore
        return Model.create(valores)
    
    def atualizar(self, modelo: str, ids: int | list[int], valores: dict[str, Any]) -> bool:
        """Atualiza um ou mais registros existentes.

        Args:
            modelo:  Nome técnico do modelo.
            ids:     ID único ou lista de IDs a atualizar.
            valores: Dicionário ``{campo: valor}`` com os dados a sobrescrever.

        Returns:
            ``True`` se a operação foi concluída com sucesso.

        Raises:
            ConnectionError: Se :meth:`conectar` ainda não foi chamado.
        """
        if not self._conectado or self._odoo is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        if not isinstance(ids, list):
            ids = [ids]
        
        Model = self._odoo.env[modelo]  # type: ignore
        return Model.write(ids, valores)
    
    def excluir(self, modelo: str, ids: int | list[int]) -> bool:
        """Remove um ou mais registros do modelo informado.

        Args:
            modelo: Nome técnico do modelo.
            ids:    ID único ou lista de IDs a excluir.

        Returns:
            ``True`` se a operação foi concluída com sucesso.

        Raises:
            ConnectionError: Se :meth:`conectar` ainda não foi chamado.
        """
        if not self._conectado or self._odoo is None:
            raise ConnectionError("Não conectado ao Odoo. Execute conectar() primeiro.")
        
        if not isinstance(ids, list):
            ids = [ids]
        
        Model = self._odoo.env[modelo]  # type: ignore
        return Model.unlink(ids)


def criar_conexao(config: Optional[OdooConfig] = None) -> OdooConexao:
    """Cria e retorna uma conexão já autenticada com o Odoo.

    Função utilitária de alto nível: carrega as credenciais do ``.env``
    (ou usa ``config`` fornecido), instancia :class:`OdooConexao` e chama
    :meth:`~OdooConexao.conectar`.

    Args:
        config: Configuração opcional. Se ``None``, as credenciais são
                lidas automaticamente do arquivo ``.env``.

    Returns:
        Instância de :class:`OdooConexao` já autenticada e pronta para uso.

    Raises:
        OdooConfigError:     Variáveis de ambiente ausentes no ``.env``.
        OdooConnectionError: Falha ao conectar ou autenticar no Odoo.
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
