# -*- coding: utf-8 -*-
"""
Módulo loginOdoo - Autenticação e conexão com o Odoo via OdooRPC.
"""

from .conexao import (
    OdooConfig,
    OdooConexao,
    OdooError,
    OdooConfigError,
    OdooConnectionError,
    carregar_configuracao,
    criar_conexao,
)

__all__ = [
    "OdooConfig",
    "OdooConexao",
    "OdooError",
    "OdooConfigError",
    "OdooConnectionError",
    "carregar_configuracao",
    "criar_conexao",
]
