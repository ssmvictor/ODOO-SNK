import pytest
from unittest.mock import patch, MagicMock
from loginSNK.conexao import (
    SankhyaConfig,
    SankhyaConexao,
    SankhyaError,
    SankhyaConfigError,
    SankhyaAuthError,
    carregar_configuracao_sankhya,
    criar_conexao_sankhya,
    BASE_URL_DEFAULT,
)


class TestSankhyaConfig:
    def test_validar_todos_preenchidos(self):
        config = SankhyaConfig(
            client_id="abc123",
            client_secret="secret456",
            token="token789",
        )
        assert config.validar() == []

    def test_validar_todos_vazios(self):
        config = SankhyaConfig(client_id="", client_secret="", token="")
        faltantes = config.validar()
        assert set(faltantes) == {
            "SANKHYA_CLIENT_ID",
            "SANKHYA_CLIENT_SECRET",
            "SANKHYA_TOKEN",
        }

    def test_validar_parcial(self):
        config = SankhyaConfig(client_id="abc", client_secret="", token="tok")
        faltantes = config.validar()
        assert "SANKHYA_CLIENT_SECRET" in faltantes
        assert "SANKHYA_CLIENT_ID" not in faltantes
        assert "SANKHYA_TOKEN" not in faltantes

    def test_base_url_default(self):
        config = SankhyaConfig(client_id="a", client_secret="b", token="c")
        assert config.base_url == BASE_URL_DEFAULT
        assert config.base_url == "https://api.sankhya.com.br"

    def test_base_url_custom(self):
        config = SankhyaConfig(
            client_id="a",
            client_secret="b",
            token="c",
            base_url="https://custom.api.com",
        )
        assert config.base_url == "https://custom.api.com"

    def test_dataclass_attributes(self):
        config = SankhyaConfig(client_id="cid", client_secret="cs", token="t")
        assert config.client_id == "cid"
        assert config.client_secret == "cs"
        assert config.token == "t"


class TestExcecoes:
    def test_heranca(self):
        assert issubclass(SankhyaConfigError, SankhyaError)
        assert issubclass(SankhyaAuthError, SankhyaError)

    def test_config_error_mensagem(self):
        with pytest.raises(SankhyaConfigError, match="variavel_teste"):
            raise SankhyaConfigError("Erro: variavel_teste")

    def test_auth_error_mensagem(self):
        with pytest.raises(SankhyaAuthError, match="autenticacao"):
            raise SankhyaAuthError("falha na autenticacao")


class TestSankhyaConexaoPropriedades:
    def _make_conexao(self):
        config = SankhyaConfig(client_id="cid", client_secret="cs", token="tok")
        return SankhyaConexao(config)

    def test_autenticado_inicial_false(self):
        conn = self._make_conexao()
        assert conn.autenticado is False

    def test_bearer_token_inicial_none(self):
        conn = self._make_conexao()
        assert conn.bearer_token is None

    def test_config_retorna_config_original(self):
        config = SankhyaConfig(client_id="cid", client_secret="cs", token="tok")
        conn = SankhyaConexao(config)
        assert conn.config is config

    def test_session_sem_autenticacao(self):
        conn = self._make_conexao()
        with pytest.raises(ValueError, match="Não autenticado"):
            _ = conn.session

    def test_obter_headers_sem_autenticacao(self):
        conn = self._make_conexao()
        with pytest.raises(ValueError, match="Não autenticado"):
            conn.obter_headers_autorizacao()


class TestSankhyaConexaoAutenticacao:
    @patch("loginSNK.conexao.SankhyaSession")
    @patch("loginSNK.conexao.OAuthClient")
    def test_autenticar_sucesso(self, mock_oauth_cls, mock_session_cls):
        config = SankhyaConfig(client_id="cid", client_secret="cs", token="tok")
        conn = SankhyaConexao(config)

        mock_oauth_instance = mock_oauth_cls.return_value
        mock_oauth_instance.authenticate.return_value = "bearer-token-123"

        result = conn.autenticar()
        assert result is True
        assert conn.autenticado is True
        assert conn.bearer_token == "bearer-token-123"

    @patch("loginSNK.conexao.OAuthClient")
    def test_autenticar_falha_auth_error(self, mock_oauth_cls):
        from sankhya_sdk.auth import AuthError

        config = SankhyaConfig(client_id="cid", client_secret="cs", token="tok")
        conn = SankhyaConexao(config)

        mock_oauth_instance = mock_oauth_cls.return_value
        mock_oauth_instance.authenticate.side_effect = AuthError("Bad creds")

        result = conn.autenticar()
        assert result is False
        assert conn.autenticado is False

    @patch("loginSNK.conexao.OAuthClient")
    def test_autenticar_falha_network_error(self, mock_oauth_cls):
        from sankhya_sdk.auth import AuthNetworkError

        config = SankhyaConfig(client_id="cid", client_secret="cs", token="tok")
        conn = SankhyaConexao(config)

        mock_oauth_instance = mock_oauth_cls.return_value
        mock_oauth_instance.authenticate.side_effect = AuthNetworkError("Timeout")

        result = conn.autenticar()
        assert result is False
        assert conn.autenticado is False


class TestSankhyaConexaoHeaders:
    @patch("loginSNK.conexao.SankhyaSession")
    @patch("loginSNK.conexao.OAuthClient")
    def test_obter_headers_autorizacao(self, mock_oauth_cls, mock_session_cls):
        config = SankhyaConfig(client_id="cid", client_secret="cs", token="tok")
        conn = SankhyaConexao(config)

        mock_oauth_instance = mock_oauth_cls.return_value
        mock_oauth_instance.authenticate.return_value = "token-abc"
        mock_oauth_instance.get_valid_token.return_value = "token-abc-refreshed"

        conn.autenticar()
        headers = conn.obter_headers_autorizacao()

        assert headers["Authorization"] == "Bearer token-abc-refreshed"
        assert headers["Content-Type"] == "application/json"


class TestCarregarConfiguracao:
    @patch("loginSNK.conexao.load_dotenv")
    @patch("loginSNK.conexao.os.getenv")
    def test_carregar_config_sucesso(self, mock_getenv, mock_load_dotenv):
        mock_getenv.side_effect = lambda key, default="": {
            "SANKHYA_CLIENT_ID": "cid",
            "SANKHYA_CLIENT_SECRET": "cs",
            "SANKHYA_TOKEN": "tok",
        }.get(key, default)

        config = carregar_configuracao_sankhya()
        assert config.client_id == "cid"
        assert config.client_secret == "cs"
        assert config.token == "tok"

    @patch("loginSNK.conexao.load_dotenv")
    @patch("loginSNK.conexao.os.getenv")
    def test_carregar_config_faltantes(self, mock_getenv, mock_load_dotenv):
        mock_getenv.side_effect = lambda key, default="": default
        with pytest.raises(
            SankhyaConfigError, match="Variáveis de ambiente não configuradas"
        ):
            carregar_configuracao_sankhya()


class TestCriarConexao:
    @patch("loginSNK.conexao.SankhyaConexao.autenticar")
    @patch("loginSNK.conexao.carregar_configuracao_sankhya")
    def test_criar_conexao_sucesso(self, mock_carregar, mock_autenticar):
        config = SankhyaConfig(client_id="c", client_secret="s", token="t")
        mock_carregar.return_value = config
        mock_autenticar.return_value = True

        conn = criar_conexao_sankhya()
        assert isinstance(conn, SankhyaConexao)

    @patch("loginSNK.conexao.SankhyaConexao.autenticar")
    @patch("loginSNK.conexao.carregar_configuracao_sankhya")
    def test_criar_conexao_falha(self, mock_carregar, mock_autenticar):
        config = SankhyaConfig(client_id="c", client_secret="s", token="t")
        mock_carregar.return_value = config
        mock_autenticar.return_value = False

        with pytest.raises(SankhyaAuthError, match="Não foi possível autenticar"):
            criar_conexao_sankhya()

    @patch("loginSNK.conexao.SankhyaConexao.autenticar")
    def test_criar_conexao_com_config(self, mock_autenticar):
        mock_autenticar.return_value = True
        config = SankhyaConfig(client_id="c", client_secret="s", token="t")

        conn = criar_conexao_sankhya(config)
        assert isinstance(conn, SankhyaConexao)
        assert conn.config is config
