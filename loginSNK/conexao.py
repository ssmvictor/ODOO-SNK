# -*- coding: utf-8 -*-
"""
Módulo de autenticação na API Sankhya via Sankhya SDK Python (OAuth2).

Fornece classes e funções reutilizáveis para obter e renovar tokens
OAuth2 (client credentials) e criar sessões HTTP autenticadas para
uso com o ``GatewayClient`` (DbExplorerSP).

Uso rápido::

    from loginSNK.conexao import criar_conexao_sankhya

    conexao = criar_conexao_sankhya()
    session = conexao.session          # SankhyaSession com auto-refresh
    headers = conexao.obter_headers_autorizacao()

Classes:
    SankhyaConfig    -- Dataclass com os parâmetros de autenticação OAuth2.
    SankhyaConexao   -- Gerencia autenticação e sessão com a API Sankhya.

Funções:
    carregar_configuracao_sankhya() -- Lê credenciais do .env.
    criar_conexao_sankhya()         -- Cria e retorna conexão já autenticada.

Exceções:
    SankhyaError       -- Base para todos os erros deste módulo.
    SankhyaConfigError -- Variáveis de ambiente ausentes ou inválidas.
    SankhyaAuthError   -- Falha na autenticação OAuth2.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from sankhya_sdk.auth import OAuthClient, AuthError, AuthNetworkError
from sankhya_sdk.http import SankhyaSession


# ========== EXCEÇÕES CUSTOMIZADAS ==========

class SankhyaError(Exception):
    """Exceção base para erros relacionados à Sankhya."""
    pass


class SankhyaConfigError(SankhyaError):
    """Exceção para erros de configuração da Sankhya."""
    pass


class SankhyaAuthError(SankhyaError):
    """Exceção para erros de autenticação na Sankhya."""
    pass


# Constantes
BASE_URL_DEFAULT: str = "https://api.sankhya.com.br"


@dataclass
class SankhyaConfig:
    """Parâmetros de autenticação OAuth2 para a API Sankhya.

    Attributes:
        client_id:     Client ID obtido no Portal do Desenvolvedor Sankhya.
        client_secret: Client Secret correspondente ao ``client_id``.
        token:         Token proprietário Sankhya (cabeçalho ``X-Token``).
        base_url:      URL base da API. Padrão: ``https://api.sankhya.com.br``.
    """

    client_id: str
    client_secret: str
    token: str  # Token proprietário Sankhya (X-Token)
    base_url: str = BASE_URL_DEFAULT

    def validar(self) -> list[str]:
        """Verifica se todas as credenciais estão preenchidas.

        Returns:
            Lista com os nomes das variáveis de ambiente faltantes.
            Retorna lista vazia quando todas estão configuradas.
        """
        campos: dict[str, str | None] = {
            "SANKHYA_CLIENT_ID": self.client_id,
            "SANKHYA_CLIENT_SECRET": self.client_secret,
            "SANKHYA_TOKEN": self.token,
        }
        return [nome for nome, valor in campos.items() if not valor]


def carregar_configuracao_sankhya(env_path: Optional[Path] = None) -> SankhyaConfig:
    """Carrega as credenciais Sankhya a partir do arquivo ``.env``.

    Args:
        env_path: Caminho para o arquivo ``.env``.
                  Se ``None``, usa ``<raiz_do_projeto>/.env``.

    Returns:
        :class:`SankhyaConfig` populado com as credenciais lidas.

    Raises:
        SankhyaConfigError: Quando uma ou mais variáveis obrigatórias
            (``SANKHYA_CLIENT_ID``, ``SANKHYA_CLIENT_SECRET``,
            ``SANKHYA_TOKEN``) não estiverem definidas no ``.env``.
    """
    if env_path is None:
        env_path = Path(__file__).resolve().parent.parent / ".env"

    load_dotenv(env_path)

    config = SankhyaConfig(
        client_id=os.getenv("SANKHYA_CLIENT_ID", ""),
        client_secret=os.getenv("SANKHYA_CLIENT_SECRET", ""),
        token=os.getenv("SANKHYA_TOKEN", ""),
    )

    faltantes = config.validar()
    if faltantes:
        raise SankhyaConfigError(
            f"Variáveis de ambiente não configuradas: {', '.join(faltantes)}. "
            f"Configure no arquivo: {env_path}"
        )

    return config


class SankhyaConexao:
    """Gerencia autenticação e sessão OAuth2 com a API Sankhya.

    Utiliza o ``OAuthClient`` do Sankhya SDK para obter o Bearer Token
    e cria uma ``SankhyaSession`` com auto-refresh de tokens. A sessão
    pode ser usada diretamente com o ``GatewayClient`` para executar
    queries SQL via ``DbExplorerSP.executeQuery``.

    Exemplo de uso::

        config = carregar_configuracao_sankhya()
        conn = SankhyaConexao(config)
        conn.autenticar()

        from sankhya_sdk.http import GatewayClient
        client = GatewayClient(conn.session)
        response = client.execute_service(
            "DbExplorerSP.executeQuery",
            {"sql": "SELECT CODPROD FROM TGFPRO WHERE ROWNUM <= 5"},
        )
    """

    def __init__(self, config: SankhyaConfig) -> None:
        """Inicializa o cliente OAuth2 sem realizar autenticação.

        A autenticação efetiva só ocorre ao chamar :meth:`autenticar`.

        Args:
            config: Instância de :class:`SankhyaConfig` com as credenciais.
        """
        self._config: SankhyaConfig = config
        self._oauth: OAuthClient = OAuthClient(
            base_url=config.base_url,
            token=config.token,
        )
        self._session: Optional[SankhyaSession] = None
        self._bearer_token: Optional[str] = None

    @property
    def config(self) -> SankhyaConfig:
        """Retorna a configuração utilizada."""
        return self._config

    @property
    def bearer_token(self) -> Optional[str]:
        """Retorna o Bearer Token após autenticação."""
        return self._bearer_token

    @property
    def autenticado(self) -> bool:
        """Verifica se está autenticado."""
        return self._bearer_token is not None

    @property
    def session(self) -> SankhyaSession:
        """Retorna a sessão HTTP autenticada com auto-refresh de tokens.

        Raises:
            ValueError: Se não estiver autenticado.
        """
        if self._session is None:
            raise ValueError("Não autenticado. Execute autenticar() primeiro.")
        return self._session

    def autenticar(self) -> bool:
        """Realiza a autenticação OAuth2 e cria a sessão HTTP.

        Chama ``OAuthClient.authenticate`` com as credenciais configuradas
        e instancia a ``SankhyaSession`` com auto-refresh de tokens.

        Returns:
            ``True`` se a autenticação foi bem-sucedida; ``False`` caso contrário.
        """
        try:
            self._bearer_token = self._oauth.authenticate(
                client_id=self._config.client_id,
                client_secret=self._config.client_secret,
            )

            self._session = SankhyaSession(
                oauth_client=self._oauth,
                base_url=self._config.base_url,
            )

            print("✅ Autenticação bem-sucedida! (OAuth2 via SDK)")
            return True

        except AuthNetworkError as e:
            print(f"❌ Erro de rede na autenticação: {e}")
            return False
        except AuthError as e:
            print(f"❌ Erro de autenticação OAuth2: {e}")
            return False

    def obter_headers_autorizacao(self) -> dict[str, str]:
        """Retorna os headers HTTP com o Bearer Token para requisições manuais.

        Obtém um token válido via ``get_valid_token`` (auto-refresh se expirado).

        Returns:
            Dicionário com os cabeçalhos ``Authorization`` e ``Content-Type``.

        Raises:
            ValueError: Se :meth:`autenticar` ainda não foi chamado.
        """
        if not self._bearer_token:
            raise ValueError("Não autenticado. Execute autenticar() primeiro.")

        # Obtém token válido (auto-refresh se expirado)
        token = self._oauth.get_valid_token()

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }


def criar_conexao_sankhya(config: Optional[SankhyaConfig] = None) -> SankhyaConexao:
    """Cria e retorna uma conexão já autenticada com a API Sankhya.

    Função utilitária de alto nível: carrega as credenciais do ``.env``
    (ou usa ``config`` fornecido), instancia :class:`SankhyaConexao` e
    chama :meth:`~SankhyaConexao.autenticar`.

    Args:
        config: Configuração opcional. Se ``None``, as credenciais são
                lidas automaticamente do arquivo ``.env``.

    Returns:
        Instância de :class:`SankhyaConexao` já autenticada e pronta para uso.

    Raises:
        SankhyaConfigError: Variáveis de ambiente ausentes no ``.env``.
        SankhyaAuthError:   Falha na autenticação OAuth2.
    """
    if config is None:
        config = carregar_configuracao_sankhya()

    conexao = SankhyaConexao(config)

    if not conexao.autenticar():
        raise SankhyaAuthError("Não foi possível autenticar na Sankhya.")

    return conexao


# ========== DEMONSTRAÇÃO / TESTE ==========

def main() -> None:
    """Demonstra a autenticação Sankhya e exibe os primeiros caracteres do token.

    Executar diretamente para testar a configuração::

        python loginSNK/conexao.py
    """
    print("=" * 50)
    print("🔐 AUTENTICAÇÃO SANKHYA (SDK OAuth2)")
    print("=" * 50)

    try:
        config = carregar_configuracao_sankhya()
        print(f"Client ID: {config.client_id[:8]}...")

        conexao = criar_conexao_sankhya(config)
        print(f"Token: {conexao.bearer_token[:20]}...")

        # Teste de obtenção de headers
        headers = conexao.obter_headers_autorizacao()
        print(f"Authorization header: {headers['Authorization'][:30]}...")

    except SankhyaConfigError as e:
        print(f"❌ Erro de configuração: {e}")
        sys.exit(1)
    except SankhyaAuthError as e:
        print(f"❌ Erro de autenticação: {e}")
        sys.exit(1)

    print("=" * 50)


if __name__ == "__main__":
    main()
