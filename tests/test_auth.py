"""
認証・認可モジュールのユニットテスト

World ID認証、Xaman Wallet連携、JWT発行・検証、
ユーザー登録・ログインAPIのテストを行う。
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest

from app import create_app, db
from app.models import User
from app.services.jwt_auth import generate_token, jwt_required, verify_token
from app.services.world_id import AuthResult, authenticate_with_world_id


@pytest.fixture
def app():
    """テスト用Flaskアプリケーション"""
    app = create_app("testing")
    app.config["JWT_SECRET_KEY"] = "test-secret-key"
    app.config["JWT_ALGORITHM"] = "HS256"
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
    app.config["WORLD_ID_CLIENT_ID"] = "test-client-id"
    app.config["WORLD_ID_CLIENT_SECRET"] = "test-client-secret"
    app.config["XAMAN_API_KEY"] = "test-xaman-key"
    app.config["XAMAN_API_SECRET"] = "test-xaman-secret"
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """テスト用HTTPクライアント"""
    return app.test_client()


@pytest.fixture
def session(app):
    """テスト用DBセッション"""
    with app.app_context():
        yield db.session


def _make_user(**kwargs):
    """テスト用ユーザーを作成するヘルパー"""
    defaults = {
        "id": str(uuid.uuid4()),
        "username": f"test_user_{uuid.uuid4().hex[:8]}",
        "display_name": "テストユーザー",
        "user_type": "human",
    }
    defaults.update(kwargs)
    return User(**defaults)


# ============================================================
# JWT認証サービスのテスト
# ============================================================


class TestJWTAuth:
    """JWT発行・検証のテスト"""

    def test_generate_token(self, app):
        """JWTトークンが正常に生成されること"""
        with app.app_context():
            user_id = str(uuid.uuid4())
            token = generate_token(user_id)
            assert token is not None
            assert isinstance(token, str)
            assert len(token) > 0

    def test_verify_valid_token(self, app):
        """有効なトークンが正常に検証されること"""
        with app.app_context():
            user_id = str(uuid.uuid4())
            token = generate_token(user_id)
            payload = verify_token(token)
            assert payload is not None
            assert payload["sub"] == user_id

    def test_verify_expired_token(self, app):
        """期限切れトークンがNoneを返すこと"""
        with app.app_context():
            secret = app.config["JWT_SECRET_KEY"]
            now = datetime.now(timezone.utc)
            payload = {
                "sub": "test-user",
                "iat": now - timedelta(hours=2),
                "exp": now - timedelta(hours=1),
            }
            token = pyjwt.encode(payload, secret, algorithm="HS256")
            result = verify_token(token)
            assert result is None

    def test_verify_invalid_token(self, app):
        """無効なトークンがNoneを返すこと"""
        with app.app_context():
            result = verify_token("invalid.token.here")
            assert result is None

    def test_verify_wrong_secret(self, app):
        """異なるシークレットで署名されたトークンがNoneを返すこと"""
        with app.app_context():
            now = datetime.now(timezone.utc)
            payload = {
                "sub": "test-user",
                "iat": now,
                "exp": now + timedelta(hours=1),
            }
            token = pyjwt.encode(payload, "wrong-secret", algorithm="HS256")
            result = verify_token(token)
            assert result is None

    def test_token_contains_required_claims(self, app):
        """トークンに必要なクレームが含まれること"""
        with app.app_context():
            user_id = str(uuid.uuid4())
            token = generate_token(user_id)
            payload = verify_token(token)
            assert "sub" in payload
            assert "iat" in payload
            assert "exp" in payload


class TestJWTRequiredDecorator:
    """jwt_requiredデコレータのテスト"""

    def test_missing_auth_header(self, app, client):
        """Authorizationヘッダーがない場合401を返すこと"""

        @app.route("/test-protected")
        @jwt_required
        def protected():
            return {"ok": True}

        response = client.get("/test-protected")
        assert response.status_code == 401
        data = response.get_json()
        assert "認証トークンが必要です" in data["error"]

    def test_invalid_auth_format(self, app, client):
        """不正な形式のAuthorizationヘッダーで401を返すこと"""

        @app.route("/test-protected2")
        @jwt_required
        def protected2():
            return {"ok": True}

        response = client.get(
            "/test-protected2", headers={"Authorization": "InvalidFormat"}
        )
        assert response.status_code == 401

    def test_valid_token_passes(self, app, client):
        """有効なトークンでエンドポイントにアクセスできること"""

        @app.route("/test-protected3")
        @jwt_required
        def protected3():
            from flask import request

            return {"user_id": request.current_user_id}

        with app.app_context():
            token = generate_token("test-user-id")

        response = client.get(
            "/test-protected3",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["user_id"] == "test-user-id"

    def test_expired_token_rejected(self, app, client):
        """期限切れトークンで401を返すこと"""

        @app.route("/test-protected4")
        @jwt_required
        def protected4():
            return {"ok": True}

        secret = app.config["JWT_SECRET_KEY"]
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "test-user",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
        }
        token = pyjwt.encode(payload, secret, algorithm="HS256")

        response = client.get(
            "/test-protected4",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 401


# ============================================================
# World ID認証のテスト
# ============================================================


class TestWorldIDAuth:
    """World ID OIDC認証のテスト"""

    def test_missing_config(self, app):
        """World ID設定が不足している場合エラーを返すこと"""
        with app.app_context():
            app.config["WORLD_ID_CLIENT_ID"] = ""
            app.config["WORLD_ID_CLIENT_SECRET"] = ""
            result = authenticate_with_world_id("code", "https://example.com/callback")
            assert result.success is False
            assert "設定が不足" in result.error_message

    @patch("app.services.world_id.requests.post")
    def test_token_exchange_failure(self, mock_post, app):
        """トークン交換失敗時にエラーを返すこと"""
        mock_post.return_value = MagicMock(status_code=400)

        with app.app_context():
            result = authenticate_with_world_id(
                "invalid-code", "https://example.com/callback"
            )
            assert result.success is False
            assert "認証に失敗" in result.error_message

    @patch("app.services.world_id.requests.post")
    def test_network_error(self, mock_post, app):
        """ネットワークエラー時にエラーを返すこと"""
        import requests

        mock_post.side_effect = requests.RequestException("Connection error")

        with app.app_context():
            result = authenticate_with_world_id(
                "code", "https://example.com/callback"
            )
            assert result.success is False
            assert "接続できません" in result.error_message

    @patch("app.services.world_id.requests.get")
    @patch("app.services.world_id.requests.post")
    def test_missing_id_token(self, mock_post, mock_get, app):
        """IDトークンがレスポンスに含まれない場合エラーを返すこと"""
        mock_post.return_value = MagicMock(
            status_code=200, json=MagicMock(return_value={})
        )

        with app.app_context():
            result = authenticate_with_world_id(
                "code", "https://example.com/callback"
            )
            assert result.success is False
            assert "IDトークンが取得できません" in result.error_message

    @patch("app.services.world_id.requests.get")
    @patch("app.services.world_id.requests.post")
    @patch("app.services.world_id.jwt.get_unverified_header")
    @patch("app.services.world_id.jwt.decode")
    @patch("app.services.world_id.jwt.algorithms.RSAAlgorithm.from_jwk")
    def test_successful_auth_new_user(
        self, mock_from_jwk, mock_decode, mock_header, mock_post, mock_get, app
    ):
        """新規ユーザーの認証が成功すること"""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"id_token": "test-id-token"}),
        )
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={"keys": [{"kid": "test-kid", "kty": "RSA"}]}
            ),
        )
        mock_get.return_value.raise_for_status = MagicMock()
        mock_header.return_value = {"kid": "test-kid"}
        mock_from_jwk.return_value = "mock-public-key"
        mock_decode.return_value = {"sub": "nullifier_hash_123"}

        with app.app_context():
            result = authenticate_with_world_id(
                "valid-code", "https://example.com/callback"
            )
            assert result.success is True
            assert result.world_id_nullifier == "nullifier_hash_123"
            assert result.user_id is None  # 新規ユーザー

    @patch("app.services.world_id.requests.get")
    @patch("app.services.world_id.requests.post")
    @patch("app.services.world_id.jwt.get_unverified_header")
    @patch("app.services.world_id.jwt.decode")
    @patch("app.services.world_id.jwt.algorithms.RSAAlgorithm.from_jwk")
    def test_successful_auth_existing_user(
        self, mock_from_jwk, mock_decode, mock_header, mock_post, mock_get, app, session
    ):
        """既存ユーザーの認証でuser_idが返ること"""
        # 既存ユーザーを作成
        user = _make_user(world_id_nullifier="existing_nullifier")
        session.add(user)
        session.commit()

        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"id_token": "test-id-token"}),
        )
        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={"keys": [{"kid": "test-kid", "kty": "RSA"}]}
            ),
        )
        mock_get.return_value.raise_for_status = MagicMock()
        mock_header.return_value = {"kid": "test-kid"}
        mock_from_jwk.return_value = "mock-public-key"
        mock_decode.return_value = {"sub": "existing_nullifier"}

        with app.app_context():
            result = authenticate_with_world_id(
                "valid-code", "https://example.com/callback"
            )
            assert result.success is True
            assert result.user_id == user.id
            assert result.world_id_nullifier == "existing_nullifier"


# ============================================================
# Xaman Wallet連携のテスト
# ============================================================


class TestXamanWallet:
    """Xaman Wallet連携のテスト"""

    @patch("app.services.xaman.requests.post")
    def test_link_wallet_success(self, mock_post, app, session):
        """ウォレット連携開始が成功すること"""
        from app.services.xaman import link_xaman_wallet

        user = _make_user()
        session.add(user)
        session.commit()

        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "uuid": "test-payload-uuid",
                    "next": {"always": "https://xaman.app/sign/test"},
                    "refs": {"qr_png": "https://xaman.app/qr/test.png"},
                }
            ),
        )

        with app.app_context():
            result = link_xaman_wallet(user.id)
            assert result is not None
            assert result["payload_uuid"] == "test-payload-uuid"
            assert result["next_url"] == "https://xaman.app/sign/test"
            assert result["qr_url"] == "https://xaman.app/qr/test.png"

    def test_link_wallet_user_not_found(self, app, session):
        """存在しないユーザーでNoneを返すこと"""
        from app.services.xaman import link_xaman_wallet

        with app.app_context():
            result = link_xaman_wallet("nonexistent-id")
            assert result is None

    @patch("app.services.xaman.requests.post")
    def test_link_wallet_already_linked(self, mock_post, app, session):
        """既にウォレット連携済みの場合Noneを返すこと"""
        from app.services.xaman import link_xaman_wallet

        user = _make_user(wallet_address="rN7n3473SaZBCG4dFL83w7p1W9cgPJKXuG")
        session.add(user)
        session.commit()

        with app.app_context():
            result = link_xaman_wallet(user.id)
            assert result is None

    @patch("app.services.xaman.requests.get")
    def test_complete_wallet_link_success(self, mock_get, app, session):
        """ウォレット連携完了が成功すること"""
        from app.services.xaman import complete_wallet_link

        user = _make_user()
        session.add(user)
        session.commit()

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "meta": {"signed": True},
                    "response": {"account": "rN7n3473SaZBCG4dFL83w7p1W9cgPJKXuG"},
                }
            ),
        )

        with app.app_context():
            result = complete_wallet_link(user.id, "test-payload-uuid")
            assert result is True
            updated_user = User.query.get(user.id)
            assert updated_user.wallet_address == "rN7n3473SaZBCG4dFL83w7p1W9cgPJKXuG"

    @patch("app.services.xaman.requests.get")
    def test_complete_wallet_link_not_signed(self, mock_get, app, session):
        """署名されていない場合Falseを返すこと"""
        from app.services.xaman import complete_wallet_link

        user = _make_user()
        session.add(user)
        session.commit()

        mock_get.return_value = MagicMock(
            status_code=200,
            json=MagicMock(
                return_value={
                    "meta": {"signed": False},
                    "response": {},
                }
            ),
        )

        with app.app_context():
            result = complete_wallet_link(user.id, "test-payload-uuid")
            assert result is False


# ============================================================
# ユーザー登録APIのテスト
# ============================================================


class TestRegisterAPI:
    """POST /auth/api/register のテスト"""

    def test_register_missing_body(self, client):
        """リクエストボディがない場合400を返すこと"""
        response = client.post(
            "/auth/api/register",
            json=None,
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_register_missing_user_type(self, client):
        """ユーザー種別がない場合400を返すこと"""
        response = client.post(
            "/auth/api/register",
            json={"username": "test", "display_name": "Test"},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "ユーザー種別は必須" in data["error"]

    def test_register_invalid_user_type(self, client):
        """無効なユーザー種別で400を返すこと"""
        response = client.post(
            "/auth/api/register",
            json={
                "user_type": "invalid",
                "username": "test_user",
                "display_name": "Test",
            },
        )
        assert response.status_code == 400

    def test_register_ai_agent_success(self, client, session):
        """AIエージェントの登録が成功すること"""
        response = client.post(
            "/auth/api/register",
            json={
                "user_type": "ai_agent",
                "username": "test_agent",
                "display_name": "テストエージェント",
                "specialty": "テクノロジー",
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["user"]["user_type"] == "ai_agent"
        assert "token" in data

    def test_register_external_agent_success(self, client, session):
        """外部エージェントの登録が成功しAPIキーが返ること"""
        response = client.post(
            "/auth/api/register",
            json={
                "user_type": "external_agent",
                "username": "ext_agent",
                "display_name": "外部エージェント",
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["user"]["user_type"] == "external_agent"
        assert "api_key" in data
        assert "token" in data

    def test_register_duplicate_username(self, client, session):
        """重複ユーザー名で409を返すこと"""
        # 最初の登録
        client.post(
            "/auth/api/register",
            json={
                "user_type": "ai_agent",
                "username": "duplicate_user",
                "display_name": "First",
            },
        )
        # 重複登録
        response = client.post(
            "/auth/api/register",
            json={
                "user_type": "ai_agent",
                "username": "duplicate_user",
                "display_name": "Second",
            },
        )
        assert response.status_code == 409

    @patch("app.routes.auth.authenticate_with_world_id")
    def test_register_human_success(self, mock_auth, client, session):
        """人間ユーザーの登録が成功すること"""
        mock_auth.return_value = AuthResult(
            success=True,
            world_id_nullifier="test_nullifier_hash",
        )

        response = client.post(
            "/auth/api/register",
            json={
                "user_type": "human",
                "username": "human_user",
                "display_name": "人間ユーザー",
                "authorization_code": "test-code",
                "redirect_uri": "https://example.com/callback",
            },
        )
        assert response.status_code == 201
        data = response.get_json()
        assert data["user"]["user_type"] == "human"
        assert "token" in data

    @patch("app.routes.auth.authenticate_with_world_id")
    def test_register_human_world_id_failure(self, mock_auth, client):
        """World ID認証失敗時に401を返すこと"""
        mock_auth.return_value = AuthResult(
            success=False,
            error_message="World ID認証に失敗しました",
        )

        response = client.post(
            "/auth/api/register",
            json={
                "user_type": "human",
                "username": "human_user",
                "display_name": "人間ユーザー",
                "authorization_code": "invalid-code",
                "redirect_uri": "https://example.com/callback",
            },
        )
        assert response.status_code == 401

    def test_register_human_missing_auth_code(self, client):
        """人間ユーザーで認可コードがない場合400を返すこと"""
        response = client.post(
            "/auth/api/register",
            json={
                "user_type": "human",
                "username": "human_user",
                "display_name": "人間ユーザー",
            },
        )
        assert response.status_code == 400

    @patch("app.routes.auth.authenticate_with_world_id")
    def test_register_human_duplicate_world_id(self, mock_auth, client, session):
        """既に登録済みのWorld IDで409を返すこと"""
        mock_auth.return_value = AuthResult(
            success=True,
            user_id="existing-user-id",
            world_id_nullifier="existing_nullifier",
        )

        response = client.post(
            "/auth/api/register",
            json={
                "user_type": "human",
                "username": "new_human",
                "display_name": "新しいユーザー",
                "authorization_code": "test-code",
                "redirect_uri": "https://example.com/callback",
            },
        )
        assert response.status_code == 409


# ============================================================
# ログインAPIのテスト
# ============================================================


class TestLoginAPI:
    """POST /auth/api/login のテスト"""

    def test_login_missing_body(self, client):
        """リクエストボディがない場合400を返すこと"""
        response = client.post(
            "/auth/api/login",
            json=None,
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_login_missing_credentials(self, client):
        """認証情報がない場合400を返すこと"""
        response = client.post(
            "/auth/api/login", json={"some_field": "value"}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "APIキー" in data["error"]

    def test_login_with_api_key_success(self, client, session):
        """APIキーでのログインが成功すること"""
        # 外部エージェントを登録
        reg_response = client.post(
            "/auth/api/register",
            json={
                "user_type": "external_agent",
                "username": "login_agent",
                "display_name": "ログインテスト",
            },
        )
        api_key = reg_response.get_json()["api_key"]

        # ログイン
        response = client.post(
            "/auth/api/login",
            json={"api_key": api_key},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data
        assert data["message"] == "ログインに成功しました"

    def test_login_with_invalid_api_key(self, client):
        """無効なAPIキーで401を返すこと"""
        response = client.post(
            "/auth/api/login",
            json={"api_key": "invalid-key"},
        )
        assert response.status_code == 401

    def test_login_inactive_user(self, client, session):
        """無効化されたユーザーで403を返すこと"""
        # ユーザーを作成して無効化
        user = _make_user(
            user_type="external_agent",
            api_key="test-api-key-inactive",
            is_active=False,
        )
        session.add(user)
        session.commit()

        response = client.post(
            "/auth/api/login",
            json={"api_key": "test-api-key-inactive"},
        )
        assert response.status_code == 403

    @patch("app.routes.auth.authenticate_with_world_id")
    def test_login_with_world_id_success(self, mock_auth, client, session):
        """World IDでのログインが成功すること"""
        # 既存ユーザーを作成
        user = _make_user(world_id_nullifier="login_nullifier")
        session.add(user)
        session.commit()

        mock_auth.return_value = AuthResult(
            success=True,
            user_id=user.id,
            world_id_nullifier="login_nullifier",
        )

        response = client.post(
            "/auth/api/login",
            json={
                "authorization_code": "test-code",
                "redirect_uri": "https://example.com/callback",
            },
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "token" in data

    @patch("app.routes.auth.authenticate_with_world_id")
    def test_login_world_id_not_registered(self, mock_auth, client):
        """未登録のWorld IDで404を返すこと"""
        mock_auth.return_value = AuthResult(
            success=True,
            world_id_nullifier="unregistered_nullifier",
        )

        response = client.post(
            "/auth/api/login",
            json={
                "authorization_code": "test-code",
                "redirect_uri": "https://example.com/callback",
            },
        )
        assert response.status_code == 404

    @patch("app.routes.auth.authenticate_with_world_id")
    def test_login_world_id_failure(self, mock_auth, client):
        """World ID認証失敗時に401を返すこと"""
        mock_auth.return_value = AuthResult(
            success=False,
            error_message="World ID認証に失敗しました",
        )

        response = client.post(
            "/auth/api/login",
            json={
                "authorization_code": "invalid-code",
                "redirect_uri": "https://example.com/callback",
            },
        )
        assert response.status_code == 401


# ============================================================
# AuthResult データクラスのテスト
# ============================================================


class TestAuthResult:
    """AuthResultデータクラスのテスト"""

    def test_success_result(self):
        """成功結果が正しく作成されること"""
        result = AuthResult(
            success=True,
            user_id="test-id",
            world_id_nullifier="test-nullifier",
        )
        assert result.success is True
        assert result.user_id == "test-id"
        assert result.error_message is None

    def test_failure_result(self):
        """失敗結果が正しく作成されること"""
        result = AuthResult(
            success=False,
            error_message="テストエラー",
        )
        assert result.success is False
        assert result.user_id is None
        assert result.error_message == "テストエラー"

    def test_default_values(self):
        """デフォルト値が正しいこと"""
        result = AuthResult(success=True)
        assert result.user_id is None
        assert result.wallet_address is None
        assert result.world_id_nullifier is None
        assert result.error_message is None
