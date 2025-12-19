# -*- coding: utf-8 -*-
"""
Módulo loginOdoo - Autenticação e conexão com o Odoo 18 via XML-RPC e JSON-RPC.
"""

from .conexao import (
    OdooConfig,
    OdooConexao,
    OdooConexaoJsonRpc,
    OdooError,
    OdooConfigError,
    OdooConnectionError,
    carregar_configuracao,
    criar_conexao,
)

__all__ = [
    "OdooConfig",
    "OdooConexao",
    "OdooConexaoJsonRpc",
    "OdooError",
    "OdooConfigError",
    "OdooConnectionError",
    "carregar_configuracao",
    "criar_conexao",
]
