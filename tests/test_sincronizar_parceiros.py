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


class TestLimparDocumento:
    def test_cnpj_com_pontos_tracos(self):
        from Parceiros.sincronizar_parceiros import limpar_documento

        assert limpar_documento("12.345.678/0001-90") == "12345678000190"

    def test_cpf_com_pontos_tracos(self):
        from Parceiros.sincronizar_parceiros import limpar_documento

        assert limpar_documento("123.456.789-00") == "12345678900"

    def test_documento_ja_limpo(self):
        from Parceiros.sincronizar_parceiros import limpar_documento

        assert limpar_documento("12345678900") == "12345678900"

    def test_documento_none(self):
        from Parceiros.sincronizar_parceiros import limpar_documento

        assert limpar_documento(None) == ""

    def test_documento_vazio(self):
        from Parceiros.sincronizar_parceiros import limpar_documento

        assert limpar_documento("") == ""

    def test_documento_com_espacos(self):
        from Parceiros.sincronizar_parceiros import limpar_documento

        assert limpar_documento(" 123.456.789-00 ") == "12345678900"


class TestFlagSankhya:
    def test_flag_s(self):
        from Parceiros.sincronizar_parceiros import flag_sankhya

        assert flag_sankhya("S") is True

    def test_flag_s_minusculo(self):
        from Parceiros.sincronizar_parceiros import flag_sankhya

        assert flag_sankhya("s") is True

    def test_flag_n(self):
        from Parceiros.sincronizar_parceiros import flag_sankhya

        assert flag_sankhya("N") is False

    def test_flag_none(self):
        from Parceiros.sincronizar_parceiros import flag_sankhya

        assert flag_sankhya(None) is False

    def test_flag_vazio(self):
        from Parceiros.sincronizar_parceiros import flag_sankhya

        assert flag_sankhya("") is False

    def test_flag_com_espacos(self):
        from Parceiros.sincronizar_parceiros import flag_sankhya

        assert flag_sankhya(" S ") is True


class TestPrimeiroCampoDisponivel:
    def test_encontra_primeiro(self):
        from Parceiros.sincronizar_parceiros import primeiro_campo_disponivel

        campos = {"x_sankhya_id": {"type": "char"}, "ref": {"type": "char"}}
        assert (
            primeiro_campo_disponivel(campos, ["x_sankhya_id", "ref"], ("char",))
            == "x_sankhya_id"
        )

    def test_encontra_segundo(self):
        from Parceiros.sincronizar_parceiros import primeiro_campo_disponivel

        campos = {"ref": {"type": "char"}}
        assert (
            primeiro_campo_disponivel(campos, ["x_sankhya_id", "ref"], ("char",))
            == "ref"
        )

    def test_nenhum_disponivel(self):
        from Parceiros.sincronizar_parceiros import primeiro_campo_disponivel

        campos = {"name": {"type": "char"}}
        assert (
            primeiro_campo_disponivel(
                campos, ["x_sankhya_id", "x_codigo_sankhya"], ("char",)
            )
            is None
        )

    def test_tipo_incorreto(self):
        from Parceiros.sincronizar_parceiros import primeiro_campo_disponivel

        campos = {"x_sankhya_id": {"type": "integer"}}
        assert primeiro_campo_disponivel(campos, ["x_sankhya_id"], ("char",)) is None

    def test_tipo_correto_na_lista(self):
        from Parceiros.sincronizar_parceiros import primeiro_campo_disponivel

        campos = {"x_sankhya_id": {"type": "integer"}}
        assert (
            primeiro_campo_disponivel(campos, ["x_sankhya_id"], ("char", "integer"))
            == "x_sankhya_id"
        )


class TestCarregarSQL:
    def test_arquivo_nao_encontrado(self, tmp_path):
        from Parceiros.sincronizar_parceiros import carregar_sql

        with pytest.raises(FileNotFoundError, match="Arquivo SQL"):
            carregar_sql(tmp_path / "nao_existe.sql")

    def test_carregar_sucesso(self, tmp_path):
        from Parceiros.sincronizar_parceiros import carregar_sql

        f = tmp_path / "test.sql"
        f.write_text("SELECT 1  ", encoding="utf-8")
        assert carregar_sql(f) == "SELECT 1"


class TestBuscarParceirosSankhya:
    @patch("Parceiros.sincronizar_parceiros.GatewayClient")
    def test_buscar_sucesso(self, mock_gw_cls):
        from Parceiros.sincronizar_parceiros import buscar_parceiros_sankhya

        mock_client = MagicMock()
        mock_client.execute_service.return_value = {
            "responseBody": {
                "fieldsMetadata": [{"name": "CODPARC"}, {"name": "NOMEPARC"}],
                "rows": [["1", "Parceiro A"], ["2", "Parceiro B"]],
            }
        }
        mock_gw_cls.is_success.return_value = True

        result = buscar_parceiros_sankhya(
            mock_client, "SELECT CODPARC, NOMEPARC FROM TGFPAR"
        )
        assert len(result) == 2
        assert result[0]["CODPARC"] == "1"

    @patch("Parceiros.sincronizar_parceiros.GatewayClient")
    def test_buscar_erro(self, mock_gw_cls):
        from Parceiros.sincronizar_parceiros import buscar_parceiros_sankhya

        mock_client = MagicMock()
        mock_gw_cls.is_success.return_value = False
        mock_gw_cls.get_error_message.return_value = "SQL Error"

        with pytest.raises(RuntimeError, match="SQL Error"):
            buscar_parceiros_sankhya(mock_client, "BAD SQL")


class TestMapearParceiro:
    def setup_method(self):
        from Parceiros.sincronizar_parceiros import (
            COUNTRY_CACHE,
            STATE_CACHE,
            TAG_CACHE,
        )

        COUNTRY_CACHE.clear()
        STATE_CACHE.clear()
        TAG_CACHE.clear()

    @patch("Parceiros.sincronizar_parceiros.resolver_tag_parceiro")
    @patch("Parceiros.sincronizar_parceiros.resolve_state_id")
    @patch("Parceiros.sincronizar_parceiros.resolve_country_id")
    def test_mapear_pessoa_juridica(self, mock_country, mock_state, mock_tag):
        from Parceiros.sincronizar_parceiros import mapear_parceiro

        mock_country.return_value = 31
        mock_state.return_value = 50
        mock_tag.return_value = 10

        conn, _ = _make_connected_conexao()
        campos_partner = {
            "name": {"type": "char"},
            "ref": {"type": "char"},
            "company_type": {"type": "selection"},
            "is_company": {"type": "boolean"},
            "street": {"type": "char"},
            "city": {"type": "char"},
            "zip": {"type": "char"},
            "email": {"type": "char"},
            "phone": {"type": "char"},
            "vat": {"type": "char"},
            "country_id": {"type": "many2one"},
            "state_id": {"type": "many2one"},
            "customer_rank": {"type": "integer"},
            "supplier_rank": {"type": "integer"},
            "category_id": {"type": "many2many"},
            "active": {"type": "boolean"},
        }

        parc_snk = {
            "CODPARC": "100",
            "RAZAOSOCIAL": "Empresa Teste LTDA",
            "NOMEPARC": "Empresa Teste",
            "TIPPESSOA": "J",
            "CGC_CPF": "12.345.678/0001-90",
            "NOMEEND": "Rua A",
            "NUMEND": "123",
            "NOMECID": "Sao Paulo",
            "CEP": "01000-000",
            "UF_SIGLA": "SP",
            "PAIS_SIGLA": "BR",
            "EMAIL": "teste@example.com",
            "TELEFONE": "11999999999",
            "CLIENTE": "S",
            "FORNECEDOR": "N",
            "ATIVO": "S",
        }

        result = mapear_parceiro(parc_snk, conn, campos_partner, None)
        assert result["name"] == "Empresa Teste LTDA"
        assert result["ref"] == "100"
        assert result["company_type"] == "company"
        assert result["is_company"] is True
        assert result["street"] == "Rua A, 123"
        assert result["city"] == "Sao Paulo"
        assert result["email"] == "teste@example.com"
        assert result["customer_rank"] == 1
        assert result["supplier_rank"] == 0

    @patch("Parceiros.sincronizar_parceiros.resolver_tag_parceiro")
    @patch("Parceiros.sincronizar_parceiros.resolve_state_id")
    @patch("Parceiros.sincronizar_parceiros.resolve_country_id")
    def test_mapear_pessoa_fisica(self, mock_country, mock_state, mock_tag):
        from Parceiros.sincronizar_parceiros import mapear_parceiro

        mock_country.return_value = None
        mock_state.return_value = None
        mock_tag.return_value = None

        conn, _ = _make_connected_conexao()
        campos_partner = {
            "name": {"type": "char"},
            "ref": {"type": "char"},
            "company_type": {"type": "selection"},
            "is_company": {"type": "boolean"},
            "active": {"type": "boolean"},
        }

        parc_snk = {
            "CODPARC": "200",
            "NOMEPARC": "Joao Silva",
            "TIPPESSOA": "F",
            "ATIVO": "S",
        }

        result = mapear_parceiro(parc_snk, conn, campos_partner, None)
        assert result["company_type"] == "person"
        assert result["is_company"] is False
        assert result["name"] == "Joao Silva"

    @patch("Parceiros.sincronizar_parceiros.resolver_tag_parceiro")
    @patch("Parceiros.sincronizar_parceiros.resolve_state_id")
    @patch("Parceiros.sincronizar_parceiros.resolve_country_id")
    def test_mapear_sem_razao_social_usa_nomeparc(
        self, mock_country, mock_state, mock_tag
    ):
        from Parceiros.sincronizar_parceiros import mapear_parceiro

        mock_country.return_value = None
        mock_state.return_value = None
        mock_tag.return_value = None

        conn, _ = _make_connected_conexao()
        campos_partner = {
            "name": {"type": "char"},
            "ref": {"type": "char"},
            "active": {"type": "boolean"},
        }

        parc_snk = {
            "CODPARC": "300",
            "RAZAOSOCIAL": "",
            "NOMEPARC": "Nome Parceiro",
            "TIPPESSOA": "J",
            "ATIVO": "S",
        }

        result = mapear_parceiro(parc_snk, conn, campos_partner, None)
        assert result["name"] == "Nome Parceiro"

    @patch("Parceiros.sincronizar_parceiros.resolver_tag_parceiro")
    @patch("Parceiros.sincronizar_parceiros.resolve_state_id")
    @patch("Parceiros.sincronizar_parceiros.resolve_country_id")
    def test_mapear_campo_chave_externa(self, mock_country, mock_state, mock_tag):
        from Parceiros.sincronizar_parceiros import mapear_parceiro

        mock_country.return_value = None
        mock_state.return_value = None
        mock_tag.return_value = None

        conn, _ = _make_connected_conexao()
        campos_partner = {
            "name": {"type": "char"},
            "ref": {"type": "char"},
            "x_sankhya_id": {"type": "char"},
            "active": {"type": "boolean"},
        }

        parc_snk = {
            "CODPARC": "500",
            "NOMEPARC": "Teste",
            "TIPPESSOA": "J",
            "ATIVO": "S",
        }

        result = mapear_parceiro(parc_snk, conn, campos_partner, "x_sankhya_id")
        assert result["x_sankhya_id"] == "500"


class TestSincronizarParceiro:
    @patch("Parceiros.sincronizar_parceiros.buscar_parceiro_existente")
    def test_criar_parceiro_novo(self, mock_buscar):
        from Parceiros.sincronizar_parceiros import sincronizar_parceiro

        mock_buscar.return_value = None
        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.create.return_value = 77
        mock_odoo.env.__getitem__.return_value = mock_model

        dados = {"name": "Novo Parceiro", "ref": "400"}
        acao, pid = sincronizar_parceiro(conn, dados, "400", None)
        assert acao == "criado"
        assert pid == 77

    @patch("Parceiros.sincronizar_parceiros.buscar_parceiro_existente")
    def test_atualizar_parceiro_existente(self, mock_buscar):
        from Parceiros.sincronizar_parceiros import sincronizar_parceiro

        mock_buscar.return_value = {"id": 55}
        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        dados = {"name": "Parceiro Atualizado", "ref": "55"}
        acao, pid = sincronizar_parceiro(conn, dados, "55", None)
        assert acao == "atualizado"
        assert pid == 55
