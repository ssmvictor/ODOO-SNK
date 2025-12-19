# -*- coding: utf-8 -*-
"""
Módulo de autenticação na API Sankhya
Fornece classes e funções reutilizáveis para obter Bearer Token.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv


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
DEFAULT_TIMEOUT: int = 30  # segundos


@dataclass
class SankhyaConfig:
    """Configuração de conexão com a API Sankhya."""
    appkey: str
    token: str
    username: str
    password: str
    url: str = "https://api.sankhya.com.br/login"

    def validar(self) -> list[str]:
        """Valida se todas as configurações estão preenchidas.
        
        Returns:
            Lista de campos faltantes (vazia se todos ok).
        """
        campos: dict[str, str | None] = {
            "SANKHYA_APPKEY": self.appkey,
            "SANKHYA_TOKEN": self.token,
            "SANKHYA_USERNAME": self.username,
            "SANKHYA_PASSWORD": self.password,
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
        appkey=os.getenv("SANKHYA_APPKEY", ""),
        token=os.getenv("SANKHYA_TOKEN", ""),
        username=os.getenv("SANKHYA_USERNAME", ""),
        password=os.getenv("SANKHYA_PASSWORD", ""),
    )
    
    faltantes = config.validar()
    if faltantes:
        raise SankhyaConfigError(
            f"Variáveis de ambiente não configuradas: {', '.join(faltantes)}. "
            f"Configure no arquivo: {env_path}"
        )
    
    return config


class SankhyaConexao:
    """Conexão com a API Sankhya."""
    
    TOKEN_FILE: str = "bearer_token.txt"
    
    def __init__(self, config: SankhyaConfig) -> None:
        """Inicializa a conexão com a Sankhya.
        
        Args:
            config: Configuração de conexão.
        """
        self._config: SankhyaConfig = config
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
    
    def _montar_headers(self) -> dict[str, str]:
        """Monta os headers de autenticação.
        
        Returns:
            Dicionário com os headers.
        """
        return {
            'Appkey': self._config.appkey,
            'Token': self._config.token,
            'Username': self._config.username,
            'Password': self._config.password,
        }
    
    def autenticar(self) -> bool:
        """Realiza autenticação e obtém o Bearer Token.
        
        Returns:
            True se autenticou com sucesso, False caso contrário.
        """
        try:
            response = requests.post(
                self._config.url, 
                headers=self._montar_headers(),
                timeout=DEFAULT_TIMEOUT
            )
            
            # Valida resposta HTTP
            response.raise_for_status()
            
            try:
                data = response.json()
            except ValueError as e:
                print(f"❌ Erro ao decodificar JSON da resposta: {e}")
                return False
            
            self._bearer_token = data.get("bearerToken")
            
            if self._bearer_token:
                print(f"✅ Autenticação bem-sucedida!")
                return True
            else:
                print("❌ Erro: Token não encontrado na resposta.")
                return False
                
        except requests.Timeout:
            print(f"❌ Timeout: Requisição excedeu {DEFAULT_TIMEOUT} segundos.")
            return False
        except requests.HTTPError as e:
            print(f"❌ Erro HTTP: {e.response.status_code} - {e.response.text}")
            return False
        except requests.RequestException as e:
            print(f"❌ Erro na conexão com a API: {e}")
            return False
    
    def salvar_token(self, arquivo: Optional[str] = None) -> bool:
        """Salva o Bearer Token em arquivo.
        
        Args:
            arquivo: Caminho do arquivo. Se None, usa TOKEN_FILE.
            
        Returns:
            True se salvou com sucesso.
        """
        if not self._bearer_token:
            print("❌ Erro: Nenhum token para salvar. Execute autenticar() primeiro.")
            return False
        
        arquivo = arquivo or self.TOKEN_FILE
        
        try:
            with open(arquivo, "w", encoding="utf-8") as file:
                file.write(self._bearer_token)
            print(f"✅ Token salvo com sucesso em: {arquivo}")
            return True
        except IOError as e:
            print(f"❌ Erro ao salvar token: {e}")
            return False
    
    def carregar_token(self, arquivo: Optional[str] = None) -> Optional[str]:
        """Carrega o Bearer Token de arquivo.
        
        Args:
            arquivo: Caminho do arquivo. Se None, usa TOKEN_FILE.
            
        Returns:
            O token lido ou None se não existir.
        """
        arquivo = arquivo or self.TOKEN_FILE
        
        try:
            with open(arquivo, "r", encoding="utf-8") as file:
                self._bearer_token = file.read().strip()
            return self._bearer_token
        except FileNotFoundError:
            print(f"❌ Arquivo de token não encontrado: {arquivo}")
            return None
        except IOError as e:
            print(f"❌ Erro ao carregar token: {e}")
            return None
    
    def obter_headers_autorizacao(self) -> dict[str, str]:
        """Retorna headers com Authorization Bearer para requisições.
        
        Returns:
            Dicionário com header Authorization.
            
        Raises:
            ValueError: Se não estiver autenticado.
        """
        if not self._bearer_token:
            raise ValueError("Não autenticado. Execute autenticar() primeiro.")
        
        return {
            "Authorization": f"Bearer {self._bearer_token}",
            "Content-Type": "application/json"
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
    print("🔐 AUTENTICAÇÃO SANKHYA")
    print("=" * 50)
    
    try:
        config = carregar_configuracao_sankhya()
        print(f"Usuário: {config.username}")
        
        conexao = SankhyaConexao(config)
        
        if conexao.autenticar():
            conexao.salvar_token()
    except SankhyaConfigError as e:
        print(f"❌ Erro de configuração: {e}")
        sys.exit(1)
    except SankhyaAuthError as e:
        print(f"❌ Erro de autenticação: {e}")
        sys.exit(1)
    
    print("=" * 50)


if __name__ == "__main__":
    main()
