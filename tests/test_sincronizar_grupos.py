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
        from Produtos.sincronizar_grupos import validar_hierarquia_origem

        grupos = [
            {"CODGRUPOPROD": "1", "CODGRUPAI": "0"},
            {"CODGRUPOPROD": "2", "CODGRUPAI": "1"},
            {"CODGRUPOPROD": "3", "CODGRUPAI": "2"},
        ]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(grupos)
        assert auto_ref == 0
        assert orfaos == 0
        assert ciclos == 0

    def test_auto_referencia(self):
        from Produtos.sincronizar_grupos import validar_hierarquia_origem

        grupos = [
            {"CODGRUPOPROD": "1", "CODGRUPAI": "1"},
        ]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(grupos)
        assert auto_ref == 1

    def test_orfao(self):
        from Produtos.sincronizar_grupos import validar_hierarquia_origem

        grupos = [
            {"CODGRUPOPROD": "1", "CODGRUPAI": "0"},
            {"CODGRUPOPROD": "2", "CODGRUPAI": "999"},
        ]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(grupos)
        assert orfaos == 1

    def test_ciclo(self):
        from Produtos.sincronizar_grupos import validar_hierarquia_origem

        grupos = [
            {"CODGRUPOPROD": "1", "CODGRUPAI": "2"},
            {"CODGRUPOPROD": "2", "CODGRUPAI": "3"},
            {"CODGRUPOPROD": "3", "CODGRUPAI": "1"},
        ]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(grupos)
        assert ciclos == 1

    def test_lista_vazia(self):
        from Produtos.sincronizar_grupos import validar_hierarquia_origem

        auto_ref, orfaos, ciclos = validar_hierarquia_origem([])
        assert auto_ref == 0
        assert orfaos == 0
        assert ciclos == 0

    def test_multiplos_problemas(self):
        from Produtos.sincronizar_grupos import validar_hierarquia_origem

        grupos = [
            {"CODGRUPOPROD": "1", "CODGRUPAI": "1"},
            {"CODGRUPOPROD": "2", "CODGRUPAI": "999"},
            {"CODGRUPOPROD": "3", "CODGRUPAI": "4"},
            {"CODGRUPOPROD": "4", "CODGRUPAI": "3"},
        ]
        auto_ref, orfaos, ciclos = validar_hierarquia_origem(grupos)
        assert auto_ref == 1
        assert orfaos == 1
        assert ciclos == 1


class TestPrimeiroCampoDisponivel:
    def test_encontra_primeiro(self):
        from Produtos.sincronizar_grupos import primeiro_campo_disponivel

        campos = {"x_sankhya_id": {"type": "char"}}
        assert (
            primeiro_campo_disponivel(campos, ["x_sankhya_id", "ref"], ("char",))
            == "x_sankhya_id"
        )

    def test_nenhum(self):
        from Produtos.sincronizar_grupos import primeiro_campo_disponivel

        assert primeiro_campo_disponivel({}, ["x_sankhya_id"], ("char",)) is None


class TestCarregarSQL:
    def test_arquivo_nao_encontrado(self, tmp_path):
        from Produtos.sincronizar_grupos import carregar_sql

        with pytest.raises(FileNotFoundError):
            carregar_sql(tmp_path / "nao_existe.sql")

    def test_sucesso(self, tmp_path):
        from Produtos.sincronizar_grupos import carregar_sql

        f = tmp_path / "test.sql"
        f.write_text("SELECT 1  ", encoding="utf-8")
        assert carregar_sql(f) == "SELECT 1"


class TestBuscarCategoriaPorCodigo:
    def test_codigo_vazio(self):
        from Produtos.sincronizar_grupos import buscar_categoria_por_codigo

        conn, _ = _make_connected_conexao()
        assert buscar_categoria_por_codigo(conn, "") is None

    def test_codigo_zero(self):
        from Produtos.sincronizar_grupos import buscar_categoria_por_codigo

        conn, _ = _make_connected_conexao()
        assert buscar_categoria_por_codigo(conn, "0") is None

    def test_encontrado(self):
        from Produtos.sincronizar_grupos import buscar_categoria_por_codigo

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 10, "name": "[100] Grupo A"}]
        mock_odoo.env.__getitem__.return_value = mock_model

        result = buscar_categoria_por_codigo(conn, "100")
        assert result["id"] == 10


class TestSincronizarGrupo:
    def test_criar_grupo_novo(self):
        from Produtos.sincronizar_grupos import sincronizar_grupo

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_model.create.return_value = 15
        mock_odoo.env.__getitem__.return_value = mock_model

        dados = {
            "CODGRUPOPROD": "50",
            "DESCRGRUPOPROD": "Grupo Teste",
            "CODGRUPAI": "0",
            "GRAU": "1",
        }
        acao, gid = sincronizar_grupo(conn, dados, None, None, None)
        assert acao == "criado"
        assert gid == 15

    def test_atualizar_grupo_existente(self):
        from Produtos.sincronizar_grupos import sincronizar_grupo

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 20, "name": "[50] Grupo Teste"}]
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        dados = {
            "CODGRUPOPROD": "50",
            "DESCRGRUPOPROD": "Grupo Atualizado",
            "CODGRUPAI": "0",
            "GRAU": "1",
        }
        acao, gid = sincronizar_grupo(conn, dados, None, None, None)
        assert acao == "atualizado"
        assert gid == 20

    def test_grupo_com_campos_custom(self):
        from Produtos.sincronizar_grupos import sincronizar_grupo

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_model.create.return_value = 30
        mock_odoo.env.__getitem__ = MagicMock(return_value=mock_model)

        dados = {
            "CODGRUPOPROD": "60",
            "DESCRGRUPOPROD": "Grupo Custom",
            "CODGRUPAI": "50",
            "GRAU": "2",
        }
        acao, gid = sincronizar_grupo(
            conn, dados, "x_sankhya_id", "x_parent_id", "x_grau"
        )
        assert acao == "criado"
