# -*- coding: utf-8 -*-
"""
Módulo de autenticação na API Sankhya via Sankhya SDK Python.
Fornece classes e funções reutilizáveis para conexão OAuth2.
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
    """Configuração de conexão com a API Sankhya via OAuth2."""
    client_id: str
    client_secret: str
    token: str  # Token proprietário Sankhya (X-Token)
    base_url: str = BASE_URL_DEFAULT

    def validar(self) -> list[str]:
        """Valida se todas as configurações estão preenchidas.

        Returns:
            Lista de campos faltantes (vazia se todos ok).
        """
        campos: dict[str, str | None] = {
            "SANKHYA_CLIENT_ID": self.client_id,
            "SANKHYA_CLIENT_SECRET": self.client_secret,
            "SANKHYA_TOKEN": self.token,
        }
        return [nome for nome, valor in campos.items() if not valor]


def carregar_configuracao_sankhya(env_path: Optional[Path] = None) -> SankhyaConfig:
    """Carrega configuração da Sankhya a partir do arquivo .env.

    Args:
        env_path: Caminho para o arquivo .env. Se None, usa a raiz do projeto.

    Returns:
        SankhyaConfig com as credenciais carregadas.

    Raises:
        SankhyaConfigError: Se variáveis obrigatórias não estiverem configuradas.
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
    """Conexão com a API Sankhya via SDK (OAuth2)."""

    def __init__(self, config: SankhyaConfig) -> None:
        """Inicializa a conexão com a Sankhya.

        Args:
            config: Configuração de conexão.
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
        """Realiza autenticação OAuth2 e obtém o Bearer Token.

        Returns:
            True se autenticou com sucesso, False caso contrário.
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
        """Retorna headers com Authorization Bearer para requisições.

        Returns:
            Dicionário com header Authorization.

        Raises:
            ValueError: Se não estiver autenticado.
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
    """Função utilitária para criar e autenticar na Sankhya.

    Args:
        config: Configuração opcional. Se None, carrega do .env.

    Returns:
        SankhyaConexao já autenticada.

    Raises:
        SankhyaAuthError: Se não conseguir autenticar.
        SankhyaConfigError: Se as variáveis de ambiente não estiverem configuradas.
    """
    if config is None:
        config = carregar_configuracao_sankhya()

    conexao = SankhyaConexao(config)

    if not conexao.autenticar():
        raise SankhyaAuthError("Não foi possível autenticar na Sankhya.")

    return conexao


# ========== DEMONSTRAÇÃO / TESTE ==========

def main() -> None:
    """Função principal de demonstração."""
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
