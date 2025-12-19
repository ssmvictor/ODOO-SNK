# -*- coding: utf-8 -*-
"""
Módulo loginSNK - Autenticação e conexão com a API Sankhya.
"""

from .conexao import (
    SankhyaConfig,
    SankhyaConexao,
    SankhyaError,
    SankhyaConfigError,
    SankhyaAuthError,
    carregar_configuracao_sankhya,
    criar_conexao_sankhya,
)

__all__ = [
    "SankhyaConfig",
    "SankhyaConexao",
    "SankhyaError",
    "SankhyaConfigError",
    "SankhyaAuthError",
    "carregar_configuracao_sankhya",
    "criar_conexao_sankhya",
]
