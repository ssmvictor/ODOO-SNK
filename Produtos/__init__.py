# -*- coding: utf-8 -*-
"""
Módulo Produtos - Serviços CRUD para produtos do Odoo.
"""

from .odoo_produtos_api import (
    ProdutoService,
    CategoriaService,
)

__all__ = [
    "ProdutoService",
    "CategoriaService",
]
