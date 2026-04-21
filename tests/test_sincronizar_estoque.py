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


class TestCarregarSQL:
    def test_arquivo_nao_encontrado(self, tmp_path):
        from Produtos.sincronizar_estoque import carregar_sql

        with pytest.raises(FileNotFoundError):
            carregar_sql(tmp_path / "nao_existe.sql")

    def test_sucesso(self, tmp_path):
        from Produtos.sincronizar_estoque import carregar_sql

        f = tmp_path / "test.sql"
        f.write_text("SELECT * FROM TGFEST  ", encoding="utf-8")
        assert carregar_sql(f) == "SELECT * FROM TGFEST"


class TestBuscarDadosSankhya:
    @patch("Produtos.sincronizar_estoque.GatewayClient")
    def test_sucesso(self, mock_gw_cls):
        from Produtos.sincronizar_estoque import buscar_dados_sankhya

        mock_client = MagicMock()
        mock_client.execute_service.return_value = {
            "responseBody": {
                "fieldsMetadata": [{"name": "CODPROD"}, {"name": "ESTOQUE"}],
                "rows": [["001", "100.5"], ["002", "200.0"]],
            }
        }
        mock_gw_cls.is_success.return_value = True

        result = buscar_dados_sankhya(
            mock_client, "SELECT CODPROD, ESTOQUE FROM TGFEST"
        )
        assert len(result) == 2
        assert result[0]["CODPROD"] == "001"

    @patch("Produtos.sincronizar_estoque.GatewayClient")
    def test_erro(self, mock_gw_cls):
        from Produtos.sincronizar_estoque import buscar_dados_sankhya

        mock_client = MagicMock()
        mock_gw_cls.is_success.return_value = False
        mock_gw_cls.get_error_message.return_value = "Erro SQL"

        with pytest.raises(Exception, match="Erro SQL"):
            buscar_dados_sankhya(mock_client, "BAD SQL")


class TestBuscarInfoProduto:
    def setup_method(self):
        from Produtos.sincronizar_estoque import CACHE_PRODUTOS

        CACHE_PRODUTOS.clear()

    def test_cache_hit(self):
        from Produtos.sincronizar_estoque import CACHE_PRODUTOS, buscar_info_produto

        CACHE_PRODUTOS["100"] = {"id": 10, "type": "product"}
        conn, _ = _make_connected_conexao()
        assert buscar_info_produto(conn, "100") == {"id": 10, "type": "product"}

    def test_encontrado_na_api(self):
        from Produtos.sincronizar_estoque import buscar_info_produto

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 20, "type": "product"}]
        mock_odoo.env.__getitem__.return_value = mock_model

        result = buscar_info_produto(conn, "200")
        assert result["id"] == 20

    def test_nao_encontrado(self):
        from Produtos.sincronizar_estoque import buscar_info_produto

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_odoo.env.__getitem__.return_value = mock_model

        assert buscar_info_produto(conn, "999") is None


class TestBuscarIdLocal:
    def setup_method(self):
        from Produtos.sincronizar_estoque import CACHE_LOCAIS

        CACHE_LOCAIS.clear()

    def test_cache_hit(self):
        from Produtos.sincronizar_estoque import CACHE_LOCAIS, buscar_id_local

        CACHE_LOCAIS["LOC1"] = 50
        conn, _ = _make_connected_conexao()
        assert buscar_id_local(conn, "LOC1") == 50

    def test_encontrado_na_api(self):
        from Produtos.sincronizar_estoque import buscar_id_local

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 60}]
        mock_odoo.env.__getitem__.return_value = mock_model

        assert buscar_id_local(conn, "LOC2") == 60

    def test_nao_encontrado(self):
        from Produtos.sincronizar_estoque import buscar_id_local

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_odoo.env.__getitem__.return_value = mock_model

        assert buscar_id_local(conn, "LOC_INEXISTENTE") is None


class TestAtualizarEstoque:
    def setup_method(self):
        from Produtos.sincronizar_estoque import CACHE_PRODUTOS, CACHE_LOCAIS

        CACHE_PRODUTOS.clear()
        CACHE_LOCAIS.clear()

    @patch("Produtos.sincronizar_estoque.buscar_id_local")
    @patch("Produtos.sincronizar_estoque.buscar_info_produto")
    def test_produto_nao_encontrado(self, mock_prod, mock_local):
        from Produtos.sincronizar_estoque import atualizar_estoque

        mock_prod.return_value = None
        conn, _ = _make_connected_conexao()
        result = atualizar_estoque(
            conn, {"CODPROD": "999", "CODLOCAL": "LOC1", "ESTOQUE": 10}
        )
        assert result == "produto_nao_encontrado"

    @patch("Produtos.sincronizar_estoque.buscar_id_local")
    @patch("Produtos.sincronizar_estoque.buscar_info_produto")
    def test_local_nao_encontrado(self, mock_prod, mock_local):
        from Produtos.sincronizar_estoque import atualizar_estoque

        mock_prod.return_value = {"id": 1, "type": "product"}
        mock_local.return_value = None
        conn, _ = _make_connected_conexao()
        result = atualizar_estoque(
            conn, {"CODPROD": "100", "CODLOCAL": "INVALID", "ESTOQUE": 10}
        )
        assert result == "local_nao_encontrado"

    @patch("Produtos.sincronizar_estoque.buscar_id_local")
    @patch("Produtos.sincronizar_estoque.buscar_info_produto")
    def test_produto_servico(self, mock_prod, mock_local):
        from Produtos.sincronizar_estoque import atualizar_estoque

        mock_prod.return_value = {"id": 2, "type": "service"}
        mock_local.return_value = 50
        conn, _ = _make_connected_conexao()
        result = atualizar_estoque(
            conn, {"CODPROD": "S001", "CODLOCAL": "LOC1", "ESTOQUE": 0}
        )
        assert result == "produto_nao_estocavel"

    @patch("Produtos.sincronizar_estoque.buscar_id_local")
    @patch("Produtos.sincronizar_estoque.buscar_info_produto")
    def test_criar_novo_quant(self, mock_prod, mock_local):
        from Produtos.sincronizar_estoque import atualizar_estoque

        mock_prod.return_value = {"id": 10, "type": "product"}
        mock_local.return_value = 50

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_model.create.return_value = 100
        mock_odoo.env.__getitem__.return_value = mock_model
        mock_odoo.execute.return_value = None

        result = atualizar_estoque(
            conn, {"CODPROD": "P001", "CODLOCAL": "LOC1", "ESTOQUE": 50.0}
        )
        assert result == "criado"

    @patch("Produtos.sincronizar_estoque.buscar_id_local")
    @patch("Produtos.sincronizar_estoque.buscar_info_produto")
    def test_atualizar_quant_existente(self, mock_prod, mock_local):
        from Produtos.sincronizar_estoque import atualizar_estoque

        mock_prod.return_value = {"id": 10, "type": "product"}
        mock_local.return_value = 50

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 100, "inventory_quantity": 30}]
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model
        mock_odoo.execute.return_value = None

        result = atualizar_estoque(
            conn, {"CODPROD": "P001", "CODLOCAL": "LOC1", "ESTOQUE": 75.0}
        )
        assert result == "atualizado"


class TestCarregarMapaProdutos:
    def setup_method(self):
        from Produtos.sincronizar_estoque import CACHE_PRODUTOS

        CACHE_PRODUTOS.clear()

    def test_carregar_mapa(self):
        from Produtos.sincronizar_estoque import carregar_mapa_produtos_odoo

        conn, mock_odoo = _make_connected_conexao()

        mock_model = MagicMock()
        mock_model.search_read.side_effect = [
            [
                {"id": 1, "default_code": "P001", "type": "product"},
                {"id": 2, "default_code": "P002", "type": "consu"},
            ],
            [],
        ]
        mock_odoo.env.__getitem__ = MagicMock(return_value=mock_model)

        mapa = carregar_mapa_produtos_odoo(conn, lote=2)
        assert "P001" in mapa
        assert mapa["P001"]["id"] == 1
        assert "P002" in mapa
