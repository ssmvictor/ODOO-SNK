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


class TestValidarHierarquiaOrigem:
    def test_hierarquia_valida(self):
        from Produtos.sincronizar_locais import validar_hierarquia_origem

        locais = [
            {"CODLOCAL": "1", "CODLOCALPAI": "0"},
            {"CODLOCAL": "2", "CODLOCALPAI": "1"},
            {"CODLOCAL": "3", "CODLOCALPAI": "2"},
        ]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(locais)
        assert auto_ref == 0
        assert orfaos == 0
        assert ciclos == 0

    def test_auto_referencia(self):
        from Produtos.sincronizar_locais import validar_hierarquia_origem

        locais = [{"CODLOCAL": "1", "CODLOCALPAI": "1"}]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(locais)
        assert auto_ref == 1

    def test_orfao(self):
        from Produtos.sincronizar_locais import validar_hierarquia_origem

        locais = [
            {"CODLOCAL": "1", "CODLOCALPAI": "0"},
            {"CODLOCAL": "2", "CODLOCALPAI": "999"},
        ]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(locais)
        assert orfaos == 1

    def test_ciclo(self):
        from Produtos.sincronizar_locais import validar_hierarquia_origem

        locais = [
            {"CODLOCAL": "A", "CODLOCALPAI": "B"},
            {"CODLOCAL": "B", "CODLOCALPAI": "C"},
            {"CODLOCAL": "C", "CODLOCALPAI": "A"},
        ]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(locais)
        assert ciclos == 1

    def test_lista_vazia(self):
        from Produtos.sincronizar_locais import validar_hierarquia_origem

        auto_ref, orfaos, ciclos = validar_hierarquia_origem([])
        assert (auto_ref, orfaos, ciclos) == (0, 0, 0)


class TestMapearLocal:
    def test_mapear_basico(self):
        from Produtos.sincronizar_locais import mapear_local

        dados = {
            "CODLOCAL": "LOC001",
            "DESCRLOCAL": "Armazem A",
            "CODLOCALPAI": "0",
            "GRAU": "1",
        }
        result = mapear_local(
            dados,
            parent_id=10,
            campo_chave=None,
            campo_pai_staging=None,
            campo_grau=None,
        )
        assert result["name"] == "Armazem A"
        assert result["barcode"] == "LOC001"
        assert result["usage"] == "internal"
        assert result["active"] is True
        assert result["location_id"] == 10

    def test_mapear_sem_parent(self):
        from Produtos.sincronizar_locais import mapear_local

        dados = {
            "CODLOCAL": "LOC002",
            "DESCRLOCAL": "Local B",
            "CODLOCALPAI": "0",
            "GRAU": "1",
        }
        result = mapear_local(
            dados,
            parent_id=None,
            campo_chave=None,
            campo_pai_staging=None,
            campo_grau=None,
        )
        assert "location_id" not in result

    def test_mapear_com_campo_chave(self):
        from Produtos.sincronizar_locais import mapear_local

        dados = {
            "CODLOCAL": "LOC003",
            "DESCRLOCAL": "Local C",
            "CODLOCALPAI": "0",
            "GRAU": "2",
        }
        result = mapear_local(
            dados,
            parent_id=5,
            campo_chave="x_sankhya_id",
            campo_pai_staging=None,
            campo_grau=None,
        )
        assert result["x_sankhya_id"] == "LOC003"

    def test_mapear_com_campo_pai_staging(self):
        from Produtos.sincronizar_locais import mapear_local

        dados = {
            "CODLOCAL": "LOC004",
            "DESCRLOCAL": "Local D",
            "CODLOCALPAI": "LOC001",
            "GRAU": "2",
        }
        result = mapear_local(
            dados,
            parent_id=5,
            campo_chave=None,
            campo_pai_staging="x_parent_id",
            campo_grau=None,
        )
        assert result["x_parent_id"] == "LOC001"

    def test_mapear_com_campo_grau(self):
        from Produtos.sincronizar_locais import mapear_local

        dados = {
            "CODLOCAL": "LOC005",
            "DESCRLOCAL": "Local E",
            "CODLOCALPAI": "0",
            "GRAU": "3",
        }
        result = mapear_local(
            dados,
            parent_id=5,
            campo_chave=None,
            campo_pai_staging=None,
            campo_grau="x_grau",
        )
        assert result["x_grau"] == 3

    def test_mapear_grau_invalido(self):
        from Produtos.sincronizar_locais import mapear_local

        dados = {
            "CODLOCAL": "LOC006",
            "DESCRLOCAL": "Local F",
            "CODLOCALPAI": "0",
            "GRAU": "abc",
        }
        result = mapear_local(
            dados,
            parent_id=5,
            campo_chave=None,
            campo_pai_staging=None,
            campo_grau="x_grau",
        )
        assert result["x_grau"] == 0

    def test_mapear_grau_none(self):
        from Produtos.sincronizar_locais import mapear_local

        dados = {
            "CODLOCAL": "LOC007",
            "DESCRLOCAL": "Local G",
            "CODLOCALPAI": "0",
            "GRAU": None,
        }
        result = mapear_local(
            dados,
            parent_id=5,
            campo_chave=None,
            campo_pai_staging=None,
            campo_grau="x_grau",
        )
        assert result["x_grau"] == 0

    def test_mapear_descricao_padrao(self):
        from Produtos.sincronizar_locais import mapear_local

        dados = {"CODLOCAL": "LOC008", "CODLOCALPAI": "0", "GRAU": "1"}
        result = mapear_local(
            dados,
            parent_id=None,
            campo_chave=None,
            campo_pai_staging=None,
            campo_grau=None,
        )
        assert result["name"] == "Local Sankhya"


class TestOrdenarLocais:
    def test_ordenar_por_grau(self):
        from Produtos.sincronizar_locais import ordenar_locais

        locais = [
            {"CODLOCAL": "3", "GRAU": "3"},
            {"CODLOCAL": "1", "GRAU": "1"},
            {"CODLOCAL": "2", "GRAU": "2"},
        ]
        ordenados = sorted(locais, key=ordenar_locais)
        assert [l["CODLOCAL"] for l in ordenados] == ["1", "2", "3"]

    def test_grau_invalido_fica_no_fim(self):
        from Produtos.sincronizar_locais import ordenar_locais

        locais = [
            {"CODLOCAL": "2", "GRAU": "abc"},
            {"CODLOCAL": "1", "GRAU": "1"},
        ]
        ordenados = sorted(locais, key=ordenar_locais)
        assert ordenados[0]["CODLOCAL"] == "1"

    def test_grau_none_fica_no_fim(self):
        from Produtos.sincronizar_locais import ordenar_locais

        locais = [
            {"CODLOCAL": "2", "GRAU": None},
            {"CODLOCAL": "1", "GRAU": "1"},
        ]
        ordenados = sorted(locais, key=ordenar_locais)
        assert ordenados[0]["CODLOCAL"] == "1"


class TestSincronizarLocal:
    def test_criar_novo(self):
        from Produtos.sincronizar_locais import sincronizar_local

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_model.create.return_value = 100
        mock_odoo.env.__getitem__.return_value = mock_model

        dados = {
            "barcode": "LOC_NEW",
            "name": "Novo Local",
            "usage": "internal",
            "active": True,
        }
        acao, lid = sincronizar_local(conn, dados)
        assert acao == "criado"
        assert lid == 100

    def test_atualizar_existente(self):
        from Produtos.sincronizar_locais import sincronizar_local

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 50}]
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        dados = {
            "barcode": "LOC_EXIST",
            "name": "Local Existente",
            "usage": "internal",
            "active": True,
        }
        acao, lid = sincronizar_local(conn, dados)
        assert acao == "atualizado"
        assert lid == 50


class TestBuscarLocalPorCodigo:
    def test_codigo_vazio(self):
        from Produtos.sincronizar_locais import buscar_local_por_codigo

        conn, _ = _make_connected_conexao()
        assert buscar_local_por_codigo(conn, "") is None

    def test_encontrado(self):
        from Produtos.sincronizar_locais import buscar_local_por_codigo

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [
            {"id": 20, "name": "Local A", "location_id": [1, "WH/Stock"]}
        ]
        mock_odoo.env.__getitem__.return_value = mock_model

        result = buscar_local_por_codigo(conn, "LOC20")
        assert result["id"] == 20

    def test_nao_encontrado(self):
        from Produtos.sincronizar_locais import buscar_local_por_codigo

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_odoo.env.__getitem__.return_value = mock_model

        assert buscar_local_por_codigo(conn, "LOC_INEXISTENTE") is None


class TestCarregarSQL:
    def test_arquivo_nao_encontrado(self, tmp_path):
        from Produtos.sincronizar_locais import carregar_sql

        with pytest.raises(FileNotFoundError):
            carregar_sql(tmp_path / "nao_existe.sql")

    def test_sucesso(self, tmp_path):
        from Produtos.sincronizar_locais import carregar_sql

        f = tmp_path / "test.sql"
        f.write_text("SELECT * FROM TGFLOC  ", encoding="utf-8")
        assert carregar_sql(f) == "SELECT * FROM TGFLOC"
