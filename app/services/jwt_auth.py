"""
JWT認証サービス

JWTトークンの発行・検証とエンドポイント保護デコレータを提供する。
PyJWTを使用し、HS256アルゴリズムでトークンを署名する。
"""

import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional

import jwt
from flask import current_app, jsonify, request

logger = logging.getLogger(__name__)


def generate_token(user_id: str) -> str:
    """
    ユーザーIDからJWTトークンを生成する。

    Args:
        user_id: トークンに含めるユーザーID

    Returns:
        str: エンコードされたJWTトークン
    """
    secret_key = current_app.config.get("JWT_SECRET_KEY")
    algorithm = current_app.config.get("JWT_ALGORITHM", "HS256")
    expires_delta = current_app.config.get(
        "JWT_ACCESS_TOKEN_EXPIRES", timedelta(hours=24)
    )

    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + expires_delta,
    }

    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token


def verify_token(token: str) -> Optional[dict]:
    """
    JWTトークンを検証し、ペイロードを返す。

    Args:
        token: 検証するJWTトークン

    Returns:
        dict: デコードされたペイロード。無効な場合はNone。
    """
    secret_key = current_app.config.get("JWT_SECRET_KEY")
    algorithm = current_app.config.get("JWT_ALGORITHM", "HS256")

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWTトークンの有効期限が切れています")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("無効なJWTトークン: %s", str(e))
        return None


def jwt_required(f):
    """
    JWT認証を要求するデコレータ。

    Authorizationヘッダーから Bearer トークンを取得し、
    検証に成功した場合のみエンドポイントを実行する。
    リクエストコンテキストに current_user_id を設定する。

    Usage:
        @app.route('/protected')
        @jwt_required
        def protected_endpoint():
            user_id = request.current_user_id
            ...
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return (
                jsonify({"error": "認証トークンが必要です"}),
                401,
            )

        # Bearer トークン形式を検証
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return (
                jsonify({"error": "認証トークンの形式が不正です"}),
                401,
            )

        token = parts[1]
        payload = verify_token(token)

        if payload is None:
            return (
                jsonify({"error": "認証トークンが無効または期限切れです"}),
                401,
            )

        # リクエストコンテキストにユーザーIDを設定
        request.current_user_id = payload.get("sub")
        return f(*args, **kwargs)

    return decorated
