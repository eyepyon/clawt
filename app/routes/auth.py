"""
認証ルート

ユーザー登録、ログイン、ウォレット連携のAPIエンドポイントを定義する。
World ID認証、APIキー認証、JWT発行を統合する。
"""

import secrets
import uuid

from flask import Blueprint, jsonify, request

from app import csrf, db, limiter
from app.models import User
from app.services.jwt_auth import generate_token, jwt_required
from app.services.world_id import AuthResult, authenticate_with_world_id

auth_bp = Blueprint("auth", __name__)

# API ルートは CSRF 保護を免除
csrf.exempt(auth_bp)


@auth_bp.route("/api/register", methods=["POST"])
@limiter.limit("5/hour")
def register():
    """
    ユーザー登録API

    POST /auth/api/register

    リクエストボディ:
        - user_type: "human" | "ai_agent" | "external_agent" (必須)
        - username: ユーザー名 (必須)
        - display_name: 表示名 (必須)
        - specialty: 専門分野 (任意)

    human の場合:
        - authorization_code: World ID認可コード (必須)
        - redirect_uri: リダイレクトURI (必須)

    external_agent の場合:
        - APIキーが自動生成される

    Returns:
        JSON: ユーザー情報とJWTトークン
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "リクエストボディが必要です"}), 400

    user_type = data.get("user_type")
    username = data.get("username")
    display_name = data.get("display_name")
    specialty = data.get("specialty")

    # 必須フィールドの検証
    if not user_type:
        return jsonify({"error": "ユーザー種別は必須です"}), 400
    if not username:
        return jsonify({"error": "ユーザー名は必須です"}), 400
    if not display_name:
        return jsonify({"error": "表示名は必須です"}), 400

    if user_type not in ("human", "ai_agent", "external_agent"):
        return (
            jsonify(
                {
                    "error": "ユーザー種別は human, ai_agent, external_agent のいずれかを指定してください"
                }
            ),
            400,
        )

    # ユーザー名の重複チェック
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "このユーザー名は既に使用されています"}), 409

    # ユーザー種別ごとの登録フロー
    if user_type == "human":
        return _register_human(data, username, display_name, specialty)
    elif user_type == "ai_agent":
        return _register_ai_agent(data, username, display_name, specialty)
    elif user_type == "external_agent":
        return _register_external_agent(data, username, display_name, specialty)

    return jsonify({"error": "不正なユーザー種別です"}), 400


def _register_human(data, username, display_name, specialty):
    """人間ユーザーの登録処理（World ID認証）"""
    authorization_code = data.get("authorization_code")
    redirect_uri = data.get("redirect_uri")

    if not authorization_code or not redirect_uri:
        return (
            jsonify(
                {"error": "人間ユーザーの登録にはWorld ID認可コードとリダイレクトURIが必要です"}
            ),
            400,
        )

    # World ID認証
    auth_result = authenticate_with_world_id(authorization_code, redirect_uri)

    if not auth_result.success:
        return (
            jsonify(
                {"error": auth_result.error_message or "World ID認証に失敗しました"}
            ),
            401,
        )

    # 既存ユーザーの場合（World IDで既に登録済み）
    if auth_result.user_id:
        return (
            jsonify(
                {"error": "このWorld IDは既に登録されています"}
            ),
            409,
        )

    # 新規ユーザー作成
    user_id = str(uuid.uuid4())
    try:
        user = User(
            id=user_id,
            username=username,
            display_name=display_name,
            user_type="human",
            world_id_nullifier=auth_result.world_id_nullifier,
            specialty=specialty,
            is_verified=True,
        )
        db.session.add(user)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

    # JWTトークン発行
    token = generate_token(user_id)

    return (
        jsonify(
            {
                "message": "ユーザー登録が完了しました",
                "user": user.to_dict(),
                "token": token,
            }
        ),
        201,
    )


def _register_ai_agent(data, username, display_name, specialty):
    """AIエージェントの登録処理"""
    user_id = str(uuid.uuid4())
    try:
        user = User(
            id=user_id,
            username=username,
            display_name=display_name,
            user_type="ai_agent",
            specialty=specialty,
            is_verified=True,
        )
        db.session.add(user)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

    # JWTトークン発行
    token = generate_token(user_id)

    return (
        jsonify(
            {
                "message": "AIエージェントの登録が完了しました",
                "user": user.to_dict(),
                "token": token,
            }
        ),
        201,
    )


def _register_external_agent(data, username, display_name, specialty):
    """外部エージェントの登録処理（APIキー自動生成）"""
    user_id = str(uuid.uuid4())
    api_key = secrets.token_urlsafe(32)

    try:
        user = User(
            id=user_id,
            username=username,
            display_name=display_name,
            user_type="external_agent",
            specialty=specialty,
            api_key=api_key,
            is_verified=True,
        )
        db.session.add(user)
        db.session.commit()
    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

    # JWTトークン発行
    token = generate_token(user_id)

    return (
        jsonify(
            {
                "message": "外部エージェントの登録が完了しました",
                "user": user.to_dict(),
                "api_key": api_key,
                "token": token,
            }
        ),
        201,
    )


@auth_bp.route("/api/login", methods=["POST"])
@limiter.limit("5/hour")
def login():
    """
    ログインAPI

    POST /auth/api/login

    World ID認証の場合:
        - authorization_code: World ID認可コード (必須)
        - redirect_uri: リダイレクトURI (必須)

    APIキー認証の場合:
        - api_key: APIキー (必須)

    Returns:
        JSON: ユーザー情報とJWTトークン
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "リクエストボディが必要です"}), 400

    # APIキーによるログイン
    api_key = data.get("api_key")
    if api_key:
        return _login_with_api_key(api_key)

    # World IDによるログイン
    authorization_code = data.get("authorization_code")
    redirect_uri = data.get("redirect_uri")
    if authorization_code and redirect_uri:
        return _login_with_world_id(authorization_code, redirect_uri)

    return (
        jsonify(
            {"error": "APIキーまたはWorld ID認可コードが必要です"}
        ),
        400,
    )


def _login_with_world_id(authorization_code, redirect_uri):
    """World IDによるログイン処理"""
    auth_result = authenticate_with_world_id(authorization_code, redirect_uri)

    if not auth_result.success:
        return (
            jsonify(
                {"error": auth_result.error_message or "World ID認証に失敗しました"}
            ),
            401,
        )

    if not auth_result.user_id:
        return (
            jsonify({"error": "ユーザーが登録されていません。先に登録してください。"}),
            404,
        )

    user = User.query.get(auth_result.user_id)
    if not user:
        return jsonify({"error": "ユーザーが見つかりません"}), 404

    if not user.is_active:
        return jsonify({"error": "このアカウントは無効化されています"}), 403

    # JWTトークン発行
    token = generate_token(user.id)

    return (
        jsonify(
            {
                "message": "ログインに成功しました",
                "user": user.to_dict(),
                "token": token,
            }
        ),
        200,
    )


def _login_with_api_key(api_key):
    """APIキーによるログイン処理"""
    user = User.query.filter_by(api_key=api_key).first()

    if not user:
        return jsonify({"error": "無効なAPIキーです"}), 401

    if not user.is_active:
        return jsonify({"error": "このアカウントは無効化されています"}), 403

    # JWTトークン発行
    token = generate_token(user.id)

    return (
        jsonify(
            {
                "message": "ログインに成功しました",
                "user": user.to_dict(),
                "token": token,
            }
        ),
        200,
    )
