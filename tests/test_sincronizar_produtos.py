import pytest
from unittest.mock import MagicMock, patch
from loginOdoo.conexao import OdooConfig, OdooConexao


def _make_connected_conexao():
    config = OdooConfig(
        url="https://test.odoo.com", db="db", username="u", password="p"
    )
    conn = OdooConexao(config)
    conn._conectado = True
    conn._uid = 1
    mock_odoo = MagicMock()
    conn._odoo = mock_odoo
    return conn, mock_odoo


class TestNormalizarNCM:
    def test_ncm_com_pontos(self):
        from Produtos.sincronizar_produtos import _normalizar_ncm

        assert _normalizar_ncm("8471.30.10") == "84713010"

    def test_ncm_ja_limpo(self):
        from Produtos.sincronizar_produtos import _normalizar_ncm

        assert _normalizar_ncm("84713010") == "84713010"

    def test_ncm_none(self):
        from Produtos.sincronizar_produtos import _normalizar_ncm

        assert _normalizar_ncm(None) == ""

    def test_ncm_vazio(self):
        from Produtos.sincronizar_produtos import _normalizar_ncm

        assert _normalizar_ncm("") == ""

    def test_ncm_com_espacos(self):
        from Produtos.sincronizar_produtos import _normalizar_ncm

        assert _normalizar_ncm(" 8471.30.10 ") == "84713010"


class TestCarregarSQL:
    def test_arquivo_nao_encontrado(self, tmp_path):
        from Produtos.sincronizar_produtos import carregar_sql

        caminho = tmp_path / "nao_existe.sql"
        with pytest.raises(FileNotFoundError, match="Arquivo SQL não encontrado"):
            carregar_sql(caminho)

    def test_carregar_sql_sucesso(self, tmp_path):
        from Produtos.sincronizar_produtos import carregar_sql

        caminho = tmp_path / "test.sql"
        caminho.write_text("SELECT * FROM test  ", encoding="utf-8")
        result = carregar_sql(caminho)
        assert result == "SELECT * FROM test"


class TestResolverUomOdoo:
    def test_uom_vazia(self):
        from Produtos.sincronizar_produtos import resolver_uom_odoo, _UOM_CACHE

        _UOM_CACHE.clear()
        conn, _ = _make_connected_conexao()
        assert resolver_uom_odoo(conn, "") is None

    def test_uom_none(self):
        from Produtos.sincronizar_produtos import resolver_uom_odoo, _UOM_CACHE

        _UOM_CACHE.clear()
        conn, _ = _make_connected_conexao()
        assert resolver_uom_odoo(conn, None) is None

    def test_uom_cache_hit(self):
        from Produtos.sincronizar_produtos import resolver_uom_odoo, _UOM_CACHE

        _UOM_CACHE.clear()
        _UOM_CACHE["UN"] = 5
        conn, _ = _make_connected_conexao()
        assert resolver_uom_odoo(conn, "UN") == 5

    def test_uom_encontrada(self):
        from Produtos.sincronizar_produtos import resolver_uom_odoo, _UOM_CACHE

        _UOM_CACHE.clear()
        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 3, "name": "Unit"}]
        mock_odoo.env.__getitem__.return_value = mock_model

        result = resolver_uom_odoo(conn, "UN")
        assert result == 3

    def test_uom_nao_encontrada(self):
        from Produtos.sincronizar_produtos import resolver_uom_odoo, _UOM_CACHE

        _UOM_CACHE.clear()
        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_odoo.env.__getitem__.return_value = mock_model

        result = resolver_uom_odoo(conn, "XYZ")
        assert result is None


class TestMapearProduto:
    def setup_method(self):
        from Produtos.sincronizar_produtos import (
            _UOM_CACHE,
            _FIELDS_CACHE,
            _UOM_NAO_ENCONTRADAS,
        )

        _UOM_CACHE.clear()
        _FIELDS_CACHE.clear()
        _UOM_NAO_ENCONTRADAS.clear()

    @patch("Produtos.sincronizar_produtos.aplicar_campos_complementares")
    @patch("Produtos.sincronizar_produtos.resolver_uom_odoo")
    def test_mapear_produto_basico(self, mock_uom, mock_complementares):
        from Produtos.sincronizar_produtos import mapear_produto

        mock_uom.return_value = None
        mock_complementares.return_value = None

        conn, _ = _make_connected_conexao()
        prod_snk = {
            "CODPROD": "12345",
            "DESCRPROD": "Parafuso",
            "PESOBRUTO": 0.5,
            "CODVOL": "UN",
            "USOPROD": "R",
            "REFFORN": "REF001",
        }

        result = mapear_produto(prod_snk, conn)
        assert result["name"] == "Parafuso"
        assert result["default_code"] == "12345"
        assert result["list_price"] == 0.0
        assert result["weight"] == 0.5
        assert result["sale_ok"] is False
        assert result["purchase_ok"] is True
        assert result["type"] == "product"
        assert result["barcode"] == "REF001"

    @patch("Produtos.sincronizar_produtos.aplicar_campos_complementares")
    @patch("Produtos.sincronizar_produtos.resolver_uom_odoo")
    def test_mapear_produto_servico(self, mock_uom, mock_complementares):
        from Produtos.sincronizar_produtos import mapear_produto

        mock_uom.return_value = None
        mock_complementares.return_value = None

        conn, _ = _make_connected_conexao()
        prod_snk = {
            "CODPROD": "S001",
            "DESCRPROD": "Servico Teste",
            "USOPROD": "S",
            "PESOBRUTO": None,
            "CODVOL": "",
        }

        result = mapear_produto(prod_snk, conn)
        assert result["type"] == "service"

    @patch("Produtos.sincronizar_produtos.aplicar_campos_complementares")
    @patch("Produtos.sincronizar_produtos.resolver_uom_odoo")
    def test_mapear_produto_sem_descricao(self, mock_uom, mock_complementares):
        from Produtos.sincronizar_produtos import mapear_produto

        mock_uom.return_value = None
        mock_complementares.return_value = None

        conn, _ = _make_connected_conexao()
        prod_snk = {
            "CODPROD": "999",
            "DESCRPROD": "",
            "USOPROD": "R",
            "PESOBRUTO": None,
            "CODVOL": "",
        }

        result = mapear_produto(prod_snk, conn)
        assert result["name"] == "Produto 999"

    @patch("Produtos.sincronizar_produtos.aplicar_campos_complementares")
    @patch("Produtos.sincronizar_produtos.resolver_uom_odoo")
    def test_mapear_produto_com_uom(self, mock_uom, mock_complementares):
        from Produtos.sincronizar_produtos import mapear_produto

        mock_uom.return_value = 7
        mock_complementares.return_value = None

        conn, _ = _make_connected_conexao()
        prod_snk = {
            "CODPROD": "100",
            "DESCRPROD": "Produto KG",
            "USOPROD": "R",
            "PESOBRUTO": 1.5,
            "CODVOL": "KG",
        }

        result = mapear_produto(prod_snk, conn)
        assert result["uom_id"] == 7
        assert result["uom_po_id"] == 7


class TestSincronizarProduto:
    def test_criar_produto_novo(self):
        from Produtos.sincronizar_produtos import sincronizar_produto

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_model.create.return_value = 99
        mock_odoo.env.__getitem__.return_value = mock_model

        dados = {"default_code": "NEW001", "name": "Novo Produto"}
        acao, pid = sincronizar_produto(conn, dados)
        assert acao == "criado"
        assert pid == 99

    def test_atualizar_produto_existente(self):
        from Produtos.sincronizar_produtos import sincronizar_produto

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 42}]
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        dados = {"default_code": "EXIST001", "name": "Atualizado"}
        acao, pid = sincronizar_produto(conn, dados)
        assert acao == "atualizado"
        assert pid == 42


class TestBuscarProdutosSankhya:
    @patch("Produtos.sincronizar_produtos.GatewayClient")
    def test_buscar_produtos_sucesso(self, mock_gw_cls):
        from Produtos.sincronizar_produtos import buscar_produtos_sankhya

        mock_client = MagicMock()
        mock_client.execute_service.return_value = {
            "responseBody": {
                "fieldsMetadata": [{"name": "CODPROD"}, {"name": "DESCRPROD"}],
                "rows": [["001", "Produto A"], ["002", "Produto B"]],
            }
        }
        mock_gw_cls.is_success.return_value = True

        result = buscar_produtos_sankhya(
            mock_client, "SELECT CODPROD, DESCRPROD FROM TGFPRO"
        )
        assert len(result) == 2
        assert result[0]["CODPROD"] == "001"
        assert result[0]["DESCRPROD"] == "Produto A"

    @patch("Produtos.sincronizar_produtos.GatewayClient")
    def test_buscar_produtos_erro(self, mock_gw_cls):
        from Produtos.sincronizar_produtos import buscar_produtos_sankhya

        mock_client = MagicMock()
        mock_gw_cls.is_success.return_value = False
        mock_gw_cls.get_error_message.return_value = "SQL Error"

        with pytest.raises(Exception, match="SQL Error"):
            buscar_produtos_sankhya(mock_client, "BAD SQL")
