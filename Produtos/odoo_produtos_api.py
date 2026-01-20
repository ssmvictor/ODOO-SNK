# -*- coding: utf-8 -*-
"""
Exemplos de operações CRUD com Produtos no Odoo 18 via API OdooRPC
Utiliza a conexão centralizada do módulo loginOdoo.conexao
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from loginOdoo.conexao import (
    OdooConexao, 
    criar_conexao,
    OdooConfigError,
    OdooConnectionError,
)


class ProdutoService:
    """Serviço para operações CRUD em produtos do Odoo."""
    
    MODELO: str = 'product.template'
    
    def __init__(self, conexao: OdooConexao) -> None:
        """Inicializa o serviço de produtos.
        
        Args:
            conexao: Conexão autenticada com o Odoo.
        """
        self._conexao: OdooConexao = conexao
    
    @property
    def conexao(self) -> OdooConexao:
        """Retorna a conexão utilizada."""
        return self._conexao
    
    def listar(self, limite: int = 500) -> list[dict[str, Any]]:
        """Lista produtos do Odoo.
        
        Args:
            limite: Quantidade máxima de produtos a retornar.
            
        Returns:
            Lista de dicionários com os produtos.
        """
        print("\n[LISTANDO PRODUTOS]")
        print("-" * 70)
        
        produtos = self._conexao.search_read(
            self.MODELO,
            dominio=[],
            campos=['id', 'name', 'default_code', 'list_price', 'type'],
            limite=limite,
            ordem='name'
        )
        
        if not produtos:
            print("  [INFO] Nenhum produto cadastrado ainda.")
        else:
            print(f"  [TOTAL] {len(produtos)} produto(s)\n")
            for p in produtos:
                codigo = p.get('default_code') or 'S/N'
                print(f"  ID: {p['id']:4} | {codigo:15} | R$ {p['list_price']:>10.2f} | {p['name'][:40]}")
        
        return produtos
    
    def buscar_por_codigo(self, codigo: str) -> Optional[dict[str, Any]]:
        """Busca produto pelo código interno.
        
        Args:
            codigo: Código interno do produto (default_code).
            
        Returns:
            Dicionário com dados do produto ou None se não encontrado.
        """
        print(f"\n[BUSCANDO PRODUTO: {codigo}]")
        print("-" * 50)
        
        produtos = self._conexao.search_read(
            self.MODELO,
            dominio=[['default_code', '=', codigo]],
            campos=['id', 'name', 'default_code', 'list_price', 'type', 'categ_id']
        )
        
        if produtos:
            p = produtos[0]
            print(f"  [OK] Encontrado!")
            print(f"  ID: {p['id']}")
            print(f"  Nome: {p['name']}")
            print(f"  Código: {p.get('default_code', 'N/A')}")
            print(f"  Preço: R$ {p['list_price']:.2f}")
            print(f"  Tipo: {p['type']}")
            return p
        else:
            print(f"  [X] Produto não encontrado")
            return None
    
    def buscar_por_nome(self, nome: str, limite: int = 10) -> list[dict[str, Any]]:
        """Busca produtos por nome (busca parcial).
        
        Args:
            nome: Termo a buscar no nome do produto.
            limite: Quantidade máxima de resultados.
            
        Returns:
            Lista de produtos encontrados.
        """
        print(f"\n[BUSCANDO PRODUTOS COM NOME: '{nome}']")
        print("-" * 50)
        
        produtos = self._conexao.search_read(
            self.MODELO,
            dominio=[['name', 'ilike', nome]],
            campos=['id', 'name', 'default_code', 'list_price'],
            limite=limite
        )
        
        print(f"  Encontrados: {len(produtos)} produto(s)")
        for p in produtos:
            print(f"    - [{p['id']}] {p['name']} - R$ {p['list_price']:.2f}")
        
        return produtos
    
    def criar(
        self, 
        nome: str, 
        codigo: str, 
        preco: float, 
        tipo: str = 'consu'
    ) -> Optional[int]:
        """Cria novo produto no Odoo.
        
        Args:
            nome: Nome do produto.
            codigo: Código interno (default_code).
            preco: Preço de venda.
            tipo: 'consu' (consumível), 'service' (serviço), 'product' (estocável).
            
        Returns:
            ID do produto criado ou None se já existir.
        """
        print(f"\n[CRIANDO PRODUTO: {nome}]")
        print("-" * 50)
        
        # Verificar se já existe
        existentes = self._conexao.search_read(
            self.MODELO,
            dominio=[['default_code', '=', codigo]],
            campos=['id']
        )
        
        if existentes:
            print(f"  [AVISO] Produto com código {codigo} já existe!")
            return None
        
        # Criar produto
        produto_id: int = self._conexao.criar(self.MODELO, {
            'name': nome,
            'default_code': codigo,
            'list_price': preco,
            'type': tipo,
            'sale_ok': True,
            'purchase_ok': True,
        })
        
        print(f"  [OK] Produto criado com ID: {produto_id}")
        return produto_id
    
    def atualizar(self, produto_id: int, valores: dict[str, Any]) -> bool:
        """Atualiza um produto existente.
        
        Args:
            produto_id: ID do produto a atualizar.
            valores: Dicionário com os valores a atualizar.
            
        Returns:
            True se atualizado com sucesso.
        """
        print(f"\n[ATUALIZANDO PRODUTO ID: {produto_id}]")
        print("-" * 50)
        
        resultado = self._conexao.atualizar(self.MODELO, produto_id, valores)
        
        if resultado:
            print(f"  [OK] Produto atualizado com sucesso!")
            produto = self._conexao.search_read(
                self.MODELO,
                dominio=[['id', '=', produto_id]],
                campos=['name'] + list(valores.keys())
            )
            if produto:
                print(f"  Novos valores: {produto[0]}")
        else:
            print(f"  [X] Falha ao atualizar produto")
        
        return resultado
    
    def excluir(self, produto_id: int) -> bool:
        """Exclui um produto.
        
        Args:
            produto_id: ID do produto a excluir.
            
        Returns:
            True se excluído com sucesso.
        """
        print(f"\n[EXCLUINDO PRODUTO ID: {produto_id}]")
        print("-" * 50)
        
        produto = self._conexao.search_read(
            self.MODELO,
            dominio=[['id', '=', produto_id]],
            campos=['name', 'default_code']
        )
        
        if not produto:
            print(f"  [X] Produto não encontrado")
            return False
        
        print(f"  Produto: {produto[0]['name']} ({produto[0].get('default_code', 'S/N')})")
        
        resultado = self._conexao.excluir(self.MODELO, produto_id)
        
        if resultado:
            print(f"  [OK] Produto excluído com sucesso!")
        else:
            print(f"  [X] Falha ao excluir produto")
        
        return resultado


class CategoriaService:
    """Serviço para operações com categorias de produtos."""
    
    MODELO: str = 'product.category'
    
    def __init__(self, conexao: OdooConexao) -> None:
        """Inicializa o serviço de categorias.
        
        Args:
            conexao: Conexão autenticada com o Odoo.
        """
        self._conexao: OdooConexao = conexao
    
    def listar(self) -> list[dict[str, Any]]:
        """Lista categorias de produtos disponíveis.
        
        Returns:
            Lista de dicionários com as categorias.
        """
        print("\n[CATEGORIAS DE PRODUTOS]")
        print("-" * 50)
        
        categorias = self._conexao.search_read(
            self.MODELO,
            dominio=[],
            campos=['id', 'name', 'complete_name']
        )
        
        for c in categorias:
            print(f"  [{c['id']:3}] {c.get('complete_name', c['name'])}")
        
        return categorias


# ========== DEMONSTRAÇÃO ==========

def main() -> None:
    """Função principal de demonstração."""
    print("=" * 55)
    print("[API DE PRODUTOS - ODOO 18]")
    print("=" * 55)
    
    try:
        # Conectar ao Odoo usando a função centralizada
        conexao = criar_conexao()
    except OdooConfigError as e:
        print(f"[ERRO] Erro de configuracao: {e}")
        sys.exit(1)
    except OdooConnectionError as e:
        print(f"[ERRO] Erro de conexao: {e}")
        sys.exit(1)
    
    # Inicializar serviços
    produto_service = ProdutoService(conexao)
    categoria_service = CategoriaService(conexao)
    
    # 1. Listar TODOS os produtos existentes
    produto_service.listar()
    
    # 2. Listar categorias
    categoria_service.listar()
    
    # 3. Criar um produto de teste
    print("\n" + "=" * 55)
    print("[EXEMPLO: CRIANDO UM PRODUTO DE TESTE]")
    print("=" * 55)
    
    produto_id = produto_service.criar(
        nome="Produto Teste API",
        codigo="API-001",
        preco=99.90,
        tipo='consu'
    )
    
    if produto_id:
        # 4. Buscar o produto criado
        produto_service.buscar_por_codigo("API-001")
        
        # 5. Atualizar o preço
        produto_service.atualizar(produto_id, {'list_price': 149.90})
        
        # 6. Listar novamente
        produto_service.listar()
    
    print("\n" + "=" * 55)
    print("[OK] DEMONSTRACAO CONCLUIDA")
    print("=" * 55)
    print("\n[DICA] Acesse o Odoo para ver o produto criado!")
    print(f"   URL: {conexao.config.url}/odoo")


if __name__ == "__main__":
    main()

