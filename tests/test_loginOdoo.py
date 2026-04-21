import pytest
from unittest.mock import patch, MagicMock
from loginOdoo.conexao import (
    OdooConfig,
    OdooConexao,
    OdooError,
    OdooConfigError,
    OdooConnectionError,
    carregar_configuracao,
    criar_conexao,
    DEFAULT_TIMEOUT,
)


class TestOdooConfig:
    def test_validar_todos_preenchidos(self):
        config = OdooConfig(
            url="https://empresa.odoo.com",
            db="mydb",
            username="user@example.com",
            password="secret",
        )
        assert config.validar() == []

    def test_validar_todos_vazios(self):
        config = OdooConfig(url="", db="", username="", password="")
        faltantes = config.validar()
        assert set(faltantes) == {"ODOO_URL", "ODOO_DB", "ODOO_EMAIL", "ODOO_SENHA"}

    def test_validar_parcial(self):
        config = OdooConfig(
            url="https://empresa.odoo.com", db="", username="", password="secret"
        )
        faltantes = config.validar()
        assert "ODOO_DB" in faltantes
        assert "ODOO_EMAIL" in faltantes
        assert "ODOO_URL" not in faltantes
        assert "ODOO_SENHA" not in faltantes

    def test_dataclass_attributes(self):
        config = OdooConfig(url="u", db="d", username="e", password="p")
        assert config.url == "u"
        assert config.db == "d"
        assert config.username == "e"
        assert config.password == "p"


class TestParseUrl:
    def _make_conexao(self, url):
        config = OdooConfig(url=url, db="db", username="u", password="p")
        return OdooConexao(config)

    def test_https_com_porta(self):
        conn = self._make_conexao("https://empresa.odoo.com:8071")
        assert conn._host == "empresa.odoo.com"
        assert conn._port == 8071
        assert conn._protocol == "jsonrpc+ssl"

    def test_https_sem_porta(self):
        conn = self._make_conexao("https://empresa.odoo.com")
        assert conn._host == "empresa.odoo.com"
        assert conn._port == 443
        assert conn._protocol == "jsonrpc+ssl"

    def test_http_com_porta(self):
        conn = self._make_conexao("http://localhost:8069")
        assert conn._host == "localhost"
        assert conn._port == 8069
        assert conn._protocol == "jsonrpc"

    def test_http_sem_porta(self):
        conn = self._make_conexao("http://localhost")
        assert conn._host == "localhost"
        assert conn._port == 8069
        assert conn._protocol == "jsonrpc"

    def test_sem_protocolo(self):
        conn = self._make_conexao("meu-servidor.com:9090")
        assert conn._host == "meu-servidor.com"
        assert conn._port == 9090
        assert conn._protocol == "jsonrpc"

    def test_url_com_path(self):
        conn = self._make_conexao("https://empresa.odoo.com/web")
        assert conn._host == "empresa.odoo.com"
        assert conn._port == 443
        assert conn._protocol == "jsonrpc+ssl"

    def test_url_com_porta_e_path(self):
        conn = self._make_conexao("http://host:12345/some/path")
        assert conn._host == "host"
        assert conn._port == 12345
        assert conn._protocol == "jsonrpc"


class TestOdooConexaoPropriedades:
    def _make_conexao(self):
        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )
        return OdooConexao(config)

    def test_conectado_inicial_false(self):
        conn = self._make_conexao()
        assert conn.conectado is False

    def test_uid_inicial_none(self):
        conn = self._make_conexao()
        assert conn.uid is None

    def test_odoo_inicial_none(self):
        conn = self._make_conexao()
        assert conn.odoo is None

    def test_config_retorna_config_original(self):
        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )
        conn = OdooConexao(config)
        assert conn.config is config


class TestOdooConexaoSemConexao:
    def _make_conexao(self):
        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )
        conn = OdooConexao(config)
        return conn

    def test_search_read_sem_conexao(self):
        conn = self._make_conexao()
        with pytest.raises(ConnectionError, match="Não conectado"):
            conn.search_read("res.partner")

    def test_criar_sem_conexao(self):
        conn = self._make_conexao()
        with pytest.raises(ConnectionError, match="Não conectado"):
            conn.criar("res.partner", {"name": "Test"})

    def test_atualizar_sem_conexao(self):
        conn = self._make_conexao()
        with pytest.raises(ConnectionError, match="Não conectado"):
            conn.atualizar("res.partner", 1, {"name": "Test"})

    def test_excluir_sem_conexao(self):
        conn = self._make_conexao()
        with pytest.raises(ConnectionError, match="Não conectado"):
            conn.excluir("res.partner", 1)

    def test_executar_sem_conexao(self):
        conn = self._make_conexao()
        with pytest.raises(ConnectionError, match="Não conectado"):
            conn.executar("res.partner", "fields_get")


class TestOdooConexaoComMock:
    def _make_connected_conexao(self):
        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )
        conn = OdooConexao(config)
        conn._conectado = True
        conn._uid = 1
        mock_odoo = MagicMock()
        conn._odoo = mock_odoo
        return conn, mock_odoo

    def test_search_read_retorna_registros(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_model = MagicMock()
        mock_model.search_read.return_value = [{"id": 1, "name": "Test"}]
        mock_odoo.env.__getitem__.return_value = mock_model

        result = conn.search_read("res.partner", campos=["name"], limite=10)
        assert result == [{"id": 1, "name": "Test"}]
        mock_model.search_read.assert_called_once()

    def test_criar_retorna_id(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_model = MagicMock()
        mock_model.create.return_value = 42
        mock_odoo.env.__getitem__.return_value = mock_model

        result = conn.criar("res.partner", {"name": "Novo"})
        assert result == 42

    def test_atualizar_retorna_true(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_model = MagicMock()
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        result = conn.atualizar("res.partner", 1, {"name": "Atualizado"})
        assert result is True
        mock_model.write.assert_called_once_with([1], {"name": "Atualizado"})

    def test_atualizar_converte_int_para_lista(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_model = MagicMock()
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        conn.atualizar("res.partner", 5, {"name": "X"})
        mock_model.write.assert_called_once_with([5], {"name": "X"})

    def test_atualizar_lista_ids(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_model = MagicMock()
        mock_model.write.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        conn.atualizar("res.partner", [1, 2, 3], {"name": "X"})
        mock_model.write.assert_called_once_with([1, 2, 3], {"name": "X"})

    def test_excluir_retorna_true(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_model = MagicMock()
        mock_model.unlink.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        result = conn.excluir("res.partner", 1)
        assert result is True
        mock_model.unlink.assert_called_once_with([1])

    def test_excluir_converte_int_para_lista(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_model = MagicMock()
        mock_model.unlink.return_value = True
        mock_odoo.env.__getitem__.return_value = mock_model

        conn.excluir("res.partner", 99)
        mock_model.unlink.assert_called_once_with([99])

    def test_executar_com_kwargs(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_odoo.execute.return_value = {"field": "value"}

        result = conn.executar(
            "res.partner", "fields_get", kwargs={"allfields": ["name"]}
        )
        mock_odoo.execute.assert_called_once_with(
            "res.partner", "fields_get", {"allfields": ["name"]}
        )

    def test_executar_sem_kwargs(self):
        conn, mock_odoo = self._make_connected_conexao()
        mock_odoo.execute.return_value = [1, 2, 3]

        result = conn.executar("res.partner", "search", args=[[["id", ">", 0]]])
        mock_odoo.execute.assert_called_once_with(
            "res.partner", "search", [["id", ">", 0]]
        )

    @patch("loginOdoo.conexao.odoorpc.ODOO")
    def test_conectar_sucesso(self, mock_odoorpc_cls):
        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )
        conn = OdooConexao(config)

        mock_instance = MagicMock()
        mock_instance.env.uid = 42
        mock_odoorpc_cls.return_value = mock_instance

        result = conn.conectar()
        assert result is True
        assert conn.conectado is True
        assert conn.uid == 42

    @patch("loginOdoo.conexao.odoorpc.ODOO")
    def test_conectar_falha(self, mock_odoorpc_cls):
        import odoorpc

        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )
        conn = OdooConexao(config)

        mock_instance = MagicMock()
        mock_instance.login.side_effect = odoorpc.error.RPCError("Auth failed")
        mock_odoorpc_cls.return_value = mock_instance

        result = conn.conectar()
        assert result is False
        assert conn.conectado is False


class TestExcecoes:
    def test_odoo_error_heranca(self):
        assert issubclass(OdooConfigError, OdooError)
        assert issubclass(OdooConnectionError, OdooError)

    def test_odoo_config_error_mensagem(self):
        with pytest.raises(OdooConfigError, match="variavel_teste"):
            raise OdooConfigError("Erro: variavel_teste nao configurada")

    def test_odoo_connection_error_mensagem(self):
        with pytest.raises(OdooConnectionError, match="conexao falhou"):
            raise OdooConnectionError("conexao falhou")


class TestCarregarConfiguracao:
    @patch("loginOdoo.conexao.load_dotenv")
    @patch("loginOdoo.conexao.os.getenv")
    def test_carregar_config_sucesso(self, mock_getenv, mock_load_dotenv):
        mock_getenv.side_effect = lambda key, default="": {
            "ODOO_URL": "https://test.odoo.com",
            "ODOO_DB": "db",
            "ODOO_EMAIL": "user@test.com",
            "ODOO_SENHA": "pass",
        }.get(key, default)

        config = carregar_configuracao()
        assert config.url == "https://test.odoo.com"
        assert config.db == "db"
        assert config.username == "user@test.com"
        assert config.password == "pass"

    @patch("loginOdoo.conexao.load_dotenv")
    @patch("loginOdoo.conexao.os.getenv")
    def test_carregar_config_faltantes(self, mock_getenv, mock_load_dotenv):
        mock_getenv.side_effect = lambda key, default="": default
        with pytest.raises(
            OdooConfigError, match="Variáveis de ambiente não configuradas"
        ):
            carregar_configuracao()


class TestCriarConexao:
    @patch("loginOdoo.conexao.OdooConexao.conectar")
    @patch("loginOdoo.conexao.carregar_configuracao")
    def test_criar_conexao_sucesso(self, mock_carregar, mock_conectar):
        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )
        mock_carregar.return_value = config
        mock_conectar.return_value = True

        conn = criar_conexao()
        assert isinstance(conn, OdooConexao)

    @patch("loginOdoo.conexao.OdooConexao.conectar")
    @patch("loginOdoo.conexao.carregar_configuracao")
    def test_criar_conexao_falha(self, mock_carregar, mock_conectar):
        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )
        mock_carregar.return_value = config
        mock_conectar.return_value = False

        with pytest.raises(OdooConnectionError, match="Não foi possível conectar"):
            criar_conexao()

    @patch("loginOdoo.conexao.OdooConexao.conectar")
    def test_criar_conexao_com_config(self, mock_conectar):
        mock_conectar.return_value = True
        config = OdooConfig(
            url="https://test.odoo.com", db="db", username="u", password="p"
        )

        conn = criar_conexao(config)
        assert isinstance(conn, OdooConexao)
        assert conn.config is config
