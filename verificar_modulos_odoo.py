# -*- coding: utf-8 -*-
"""
Verificar quais módulos estão instalados no Odoo
Utiliza a conexão centralizada do módulo loginOdoo.conexao
"""

from __future__ import annotations

from typing import Any

from loginOdoo.conexao import OdooConexao, criar_conexao


class ModuloService:
    """Serviço para operações com módulos do Odoo."""
    
    MODELO: str = 'ir.module.module'
    
    def __init__(self, conexao: OdooConexao) -> None:
        """Inicializa o serviço de módulos.
        
        Args:
            conexao: Conexão autenticada com o Odoo.
        """
        self._conexao: OdooConexao = conexao
    
    def listar_instalados(self) -> list[dict[str, Any]]:
        """Lista todos os módulos instalados no Odoo.
        
        Returns:
            Lista de dicionários com informações dos módulos.
        """
        print("\n[MODULOS INSTALADOS]")
        print("-" * 50)
        
        modulos = self._conexao.search_read(
            self.MODELO,
            dominio=[['state', '=', 'installed']],
            campos=['name', 'shortdesc'],
            ordem='name',
            limite=1000
        )
        
        for m in modulos:
            print(f"  - {m['name']:30} - {m['shortdesc']}")
        
        print(f"\nTotal: {len(modulos)} módulos instalados")
        return modulos
    
    def verificar_modulos(self, nomes: list[str]) -> list[dict[str, Any]]:
        """Verifica o status de módulos específicos.
        
        Args:
            nomes: Lista de nomes de módulos a verificar.
            
        Returns:
            Lista de dicionários com status dos módulos.
        """
        print("\n[VERIFICANDO MODULOS]")
        print("-" * 50)
        
        modulos = self._conexao.search_read(
            self.MODELO,
            dominio=[['name', 'in', nomes]],
            campos=['name', 'state', 'shortdesc']
        )
        
        for m in modulos:
            status = "[OK] INSTALADO" if m['state'] == 'installed' else f"[X] {m['state']}"
            print(f"  {m['name']:15} - {status} - {m['shortdesc']}")
        
        return modulos


def main() -> None:
    """Função principal."""
    print("Conectando ao Odoo...")
    conexao = criar_conexao()
    
    modulo_service = ModuloService(conexao)
    
    # Listar todos os módulos instalados
    modulo_service.listar_instalados()
    
    # Verificar módulos específicos de produtos
    print("\n[VERIFICANDO MODULO DE PRODUTOS]")
    modulo_service.verificar_modulos(['product', 'sale', 'stock', 'purchase'])


if __name__ == "__main__":
    main()
