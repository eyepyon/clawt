"""
World ID OIDC認証サービス

Worldcoin World IDによる人間認証を管理する。
認可コードフローでIDトークンを取得し、nullifier_hashで一意性を検証する。
"""

import logging
from dataclasses import dataclass
from typing import Optional

import jwt
import requests
from flask import current_app

from app import db
from app.models import User

logger = logging.getLogger(__name__)

# World ID OIDC エンドポイント
WORLD_ID_TOKEN_URL = "https://id.worldcoin.org/token"
WORLD_ID_JWKS_URL = "https://id.worldcoin.org/.well-known/jwks.json"
WORLD_ID_ISSUER = "https://id.worldcoin.org"


@dataclass
class AuthResult:
    """認証結果を表すデータクラス"""

    success: bool
    user_id: Optional[str] = None
    wallet_address: Optional[str] = None
    world_id_nullifier: Optional[str] = None
    error_message: Optional[str] = None


def authenticate_with_world_id(
    authorization_code: str, redirect_uri: str
) -> AuthResult:
    """
    World ID OIDCフローで人間認証を行う。

    認可コードをトークンエンドポイントで交換し、IDトークンを検証して
    nullifier_hashを取得する。重複登録チェックも行う。

    Args:
        authorization_code: World IDから取得した認可コード
        redirect_uri: World IDアプリに登録済みのリダイレクトURI

    Returns:
        AuthResult: 認証結果（成功時はnullifier_hashを含む）
    """
    client_id = current_app.config.get("WORLD_ID_CLIENT_ID", "")
    client_secret = current_app.config.get("WORLD_ID_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.error("World ID設定が不足しています")
        return AuthResult(
            success=False,
            error_message="World ID設定が不足しています",
        )

    # Step 1: トークンエンドポイントで認可コードを交換
    try:
        token_response = requests.post(
            WORLD_ID_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": authorization_code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error("World IDトークン交換でネットワークエラー: %s", str(e))
        return AuthResult(
            success=False,
            error_message="World ID認証サーバーに接続できません",
        )

    if token_response.status_code != 200:
        logger.warning(
            "World IDトークン交換失敗: status=%d", token_response.status_code
        )
        return AuthResult(
            success=False,
            error_message="World ID認証に失敗しました",
        )

    tokens = token_response.json()
    id_token = tokens.get("id_token")

    if not id_token:
        return AuthResult(
            success=False,
            error_message="IDトークンが取得できませんでした",
        )

    # Step 2: JWKSエンドポイントから公開鍵を取得してIDトークンを検証
    try:
        jwks_response = requests.get(WORLD_ID_JWKS_URL, timeout=30)
        jwks_response.raise_for_status()
        jwks_data = jwks_response.json()
    except requests.RequestException as e:
        logger.error("JWKS取得エラー: %s", str(e))
        return AuthResult(
            success=False,
            error_message="World ID公開鍵の取得に失敗しました",
        )

    try:
        # IDトークンのヘッダーからkidを取得
        unverified_header = jwt.get_unverified_header(id_token)
        kid = unverified_header.get("kid")

        # JWKSからkidに一致する鍵を取得
        public_key = None
        for key_data in jwks_data.get("keys", []):
            if key_data.get("kid") == kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
                break

        if public_key is None:
            return AuthResult(
                success=False,
                error_message="IDトークンの検証鍵が見つかりません",
            )

        # IDトークンを検証・デコード
        decoded = jwt.decode(
            id_token,
            public_key,
            algorithms=["RS256"],
            audience=client_id,
            issuer=WORLD_ID_ISSUER,
        )
    except jwt.ExpiredSignatureError:
        return AuthResult(
            success=False,
            error_message="IDトークンの有効期限が切れています",
        )
    except jwt.InvalidTokenError as e:
        logger.warning("IDトークン検証失敗: %s", str(e))
        return AuthResult(
            success=False,
            error_message="IDトークンの検証に失敗しました",
        )

    # Step 3: nullifier_hashを取得（subクレーム）
    nullifier_hash = decoded.get("sub")
    if not nullifier_hash:
        return AuthResult(
            success=False,
            error_message="nullifier_hashが取得できませんでした",
        )

    # Step 4: 重複チェック
    existing_user = User.query.filter_by(
        world_id_nullifier=nullifier_hash
    ).first()
    if existing_user:
        return AuthResult(
            success=True,
            user_id=existing_user.id,
            wallet_address=existing_user.wallet_address,
            world_id_nullifier=nullifier_hash,
        )

    # 新規ユーザーとして返却（登録は別途行う）
    return AuthResult(
        success=True,
        world_id_nullifier=nullifier_hash,
    )
