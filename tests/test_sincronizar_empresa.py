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


class TestMapearRegimeTributario:
    def test_simples_nacional(self):
        from Produtos.sincronizar_empresa import mapear_regime_tributario

        assert mapear_regime_tributario("1") == "1"

    def test_simples_nacional_sublimite(self):
        from Produtos.sincronizar_empresa import mapear_regime_tributario

        assert mapear_regime_tributario("2") == "2"

    def test_regime_normal(self):
        from Produtos.sincronizar_empresa import mapear_regime_tributario

        assert mapear_regime_tributario("3") == "3"

    def test_codigo_invalido(self):
        from Produtos.sincronizar_empresa import mapear_regime_tributario

        assert mapear_regime_tributario("9") is None

    def test_vazio(self):
        from Produtos.sincronizar_empresa import mapear_regime_tributario

        assert mapear_regime_tributario("") is None

    def test_com_espacos(self):
        from Produtos.sincronizar_empresa import mapear_regime_tributario

        assert mapear_regime_tributario(" 1 ") == "1"


class TestMapearEmpresa:
    def setup_method(self):
        from Produtos.sincronizar_empresa import (
            _COUNTRY_CACHE,
            _STATE_CACHE,
            _CNAE_CACHE,
            _LEGAL_NATURE_CACHE,
        )

        _COUNTRY_CACHE.clear()
        _STATE_CACHE.clear()
        _CNAE_CACHE.clear()
        _LEGAL_NATURE_CACHE.clear()

    @patch("Produtos.sincronizar_empresa.resolver_natureza_juridica")
    @patch("Produtos.sincronizar_empresa.resolver_cnae")
    @patch("Produtos.sincronizar_empresa.resolver_estado")
    @patch("Produtos.sincronizar_empresa.resolver_pais")
    def test_mapear_empresa_completa(
        self, mock_pais, mock_estado, mock_cnae, mock_natureza
    ):
        from Produtos.sincronizar_empresa import mapear_empresa

        mock_pais.return_value = 31
        mock_estado.return_value = 50
        mock_cnae.return_value = 100
        mock_natureza.return_value = 200

        conn, _ = _make_connected_conexao()
        emp_snk = {
            "RAZAO_SOCIAL": "Empresa Teste LTDA",
            "NOME_FANTASIA": "Empresa Teste",
            "TIPO_LOGRADOURO": "Rua",
            "LOGRADOURO": "das Flores",
            "CODIGO_UF": "SP",
            "CNPJ_CPF": "12.345.678/0001-90",
            "EMAIL": "contato@empresa.com",
            "TELEFONE": "11999999999",
            "SITE": "https://empresa.com",
            "NUMERO": "123",
            "BAIRRO": "Centro",
            "COMPLEMENTO": "Sala 1",
            "CIDADE": "Sao Paulo",
            "CEP": "01000-000",
            "INSCRICAO_ESTADUAL": "123456",
            "INSCRICAO_MUNICIPAL": "789012",
            "CODIGO_REGIME_TRIBUTARIO": "3",
            "CNAE_PREPONDERANTE": "1234-56",
            "NATUREZA_JURIDICA": "2062",
        }

        result = mapear_empresa(emp_snk, conn)
        assert result["name"] == "Empresa Teste"
        assert result["legal_name"] == "Empresa Teste LTDA"
        assert result["vat"] == "12.345.678/0001-90"
        assert result["company_registry"] == "12345678000190"
        assert result["street"] == "Rua das Flores"
        assert result["city"] == "Sao Paulo"
        assert result["zip"] == "01000-000"
        assert result["email"] == "contato@empresa.com"
        assert result["phone"] == "11999999999"
        assert result["website"] == "https://empresa.com"
        assert result["country_id"] == 31
        assert result["state_id"] == 50
        assert result["l10n_br_ie_code"] == "123456"
        assert result["l10n_br_im_code"] == "789012"
        assert result["tax_framework"] == "3"
        assert result["cnae_main_id"] == 100
        assert result["legal_nature_id"] == 200

    @patch("Produtos.sincronizar_empresa.resolver_natureza_juridica")
    @patch("Produtos.sincronizar_empresa.resolver_cnae")
    @patch("Produtos.sincronizar_empresa.resolver_estado")
    @patch("Produtos.sincronizar_empresa.resolver_pais")
    def test_mapear_empresa_nome_fantasia_fallback(
        self, mock_pais, mock_estado, mock_cnae, mock_natureza
    ):
        from Produtos.sincronizar_empresa import mapear_empresa

        mock_pais.return_value = None
        mock_estado.return_value = None
        mock_cnae.return_value = None
        mock_natureza.return_value = None

        conn, _ = _make_connected_conexao()
        emp_snk = {
            "RAZAO_SOCIAL": "So Razao Social",
            "NOME_FANTASIA": "",
            "CNPJ_CPF": "12345678000190",
        }

        result = mapear_empresa(emp_snk, conn)
        assert result["name"] == "So Razao Social"

    @patch("Produtos.sincronizar_empresa.resolver_natureza_juridica")
    @patch("Produtos.sincronizar_empresa.resolver_cnae")
    @patch("Produtos.sincronizar_empresa.resolver_estado")
    @patch("Produtos.sincronizar_empresa.resolver_pais")
    def test_mapear_empresa_sem_pais_estado(
        self, mock_pais, mock_estado, mock_cnae, mock_natureza
    ):
        from Produtos.sincronizar_empresa import mapear_empresa

        mock_pais.return_value = None
        mock_estado.return_value = None
        mock_cnae.return_value = None
        mock_natureza.return_value = None

        conn, _ = _make_connected_conexao()
        emp_snk = {"RAZAO_SOCIAL": "Empresa", "NOME_FANTASIA": "Emp", "CNPJ_CPF": "123"}

        result = mapear_empresa(emp_snk, conn)
        assert "country_id" not in result
        assert "state_id" not in result


class TestSincronizarEmpresa:
    def test_criar_empresa_nova(self):
        from Produtos.sincronizar_empresa import sincronizar_empresa

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_model.create.return_value = 5
        mock_odoo.env.__getitem__ = MagicMock(return_value=mock_model)

        dados = {"name": "Nova Empresa", "vat": "12345678000190"}
        acao, eid = sincronizar_empresa(conn, dados, "12345678000190")
        assert acao == "criado"
        assert eid == 5

    def test_atualizar_empresa_existente(self):
        from Produtos.sincronizar_empresa import sincronizar_empresa

        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 1}]
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__ = MagicMock(return_value=mock_model)

        dados = {"name": "Empresa Atualizada", "vat": "12345678000190"}
        acao, eid = sincronizar_empresa(conn, dados, "12345678000190")
        assert acao == "atualizado"
        assert eid == 1


class TestCarregarSQL:
    def test_arquivo_nao_encontrado(self, tmp_path):
        from Produtos.sincronizar_empresa import carregar_sql

        with pytest.raises(FileNotFoundError):
            carregar_sql(tmp_path / "nao_existe.sql")

    def test_sucesso(self, tmp_path):
        from Produtos.sincronizar_empresa import carregar_sql

        f = tmp_path / "test.sql"
        f.write_text("SELECT * FROM TSIEMP  ", encoding="utf-8")
        assert carregar_sql(f) == "SELECT * FROM TSIEMP"


class TestResolverPais:
    def test_cache_hit(self):
        from Produtos.sincronizar_empresa import resolver_pais, _COUNTRY_CACHE

        _COUNTRY_CACHE.clear()
        _COUNTRY_CACHE["BR"] = 31
        conn, _ = _make_connected_conexao()
        assert resolver_pais(conn) == 31

    def test_encontrado(self):
        from Produtos.sincronizar_empresa import resolver_pais, _COUNTRY_CACHE

        _COUNTRY_CACHE.clear()
        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 31}]
        mock_odoo.env.__getitem__.return_value = mock_model

        assert resolver_pais(conn) == 31

    def test_nao_encontrado(self):
        from Produtos.sincronizar_empresa import resolver_pais, _COUNTRY_CACHE

        _COUNTRY_CACHE.clear()
        conn, mock_odoo = _make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = []
        mock_odoo.env.__getitem__.return_value = mock_model

        assert resolver_pais(conn) is None
