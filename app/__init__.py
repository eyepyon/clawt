"""
AIエージェント・ニュースメディアプラットフォーム

Flaskアプリケーションファクトリ
"""

import logging
import os
from logging.handlers import RotatingFileHandler

from flask import Flask, jsonify, request
from flask_babel import Babel
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import config_by_name

# エクステンションのインスタンス化
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)
csrf = CSRFProtect()
babel = Babel()


def get_locale():
    """リクエストに基づいてロケールを決定する"""
    return request.accept_languages.best_match(["ja", "en"]) or "ja"


def create_app(config_name=None):
    """
    Flaskアプリケーションファクトリ

    Args:
        config_name: 設定名 ('development', 'testing', 'production')
                     未指定の場合は環境変数 FLASK_ENV から取得

    Returns:
        Flask: 設定済みのFlaskアプリケーション
    """
    app = Flask(__name__)

    # 設定の読み込み
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # エクステンションの初期化
    _init_extensions(app)

    # ブループリントの登録
    _register_blueprints(app)

    # エラーハンドラの設定
    _register_error_handlers(app)

    # ログの設定
    _configure_logging(app)

    return app


def _init_extensions(app):
    """Flaskエクステンションを初期化する"""
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    babel.init_app(app, locale_selector=get_locale)

    # Flask-Login設定
    login_manager.login_view = "auth.login"
    login_manager.login_message = "このページにアクセスするにはログインが必要です。"

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User

        return User.query.get(user_id)


def _register_blueprints(app):
    """ブループリントを登録する（存在しない場合はスキップ）"""
    blueprint_configs = [
        ("app.routes.auth", "auth_bp", "/auth"),
        ("app.routes.agents", "agents_bp", "/agents"),
        ("app.routes.articles", "articles_bp", "/articles"),
        ("app.routes.rewards", "rewards_bp", "/rewards"),
        ("app.routes.reports", "reports_bp", "/reports"),
        ("app.routes.main", "main_bp", ""),
    ]

    for module_path, bp_name, url_prefix in blueprint_configs:
        try:
            module = __import__(module_path, fromlist=[bp_name])
            blueprint = getattr(module, bp_name)
            app.register_blueprint(blueprint, url_prefix=url_prefix)
        except (ImportError, AttributeError):
            app.logger.debug(
                "ブループリント '%s' はまだ利用できません。スキップします。",
                module_path,
            )


def _register_error_handlers(app):
    """エラーハンドラを登録する"""

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"error": "不正なリクエストです", "status": 400}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"error": "認証が必要です", "status": 401}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"error": "アクセスが拒否されました", "status": 403}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"error": "リソースが見つかりません", "status": 404}), 404

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return (
            jsonify({"error": "リクエスト制限を超えました", "status": 429}),
            429,
        )

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({"error": "内部サーバーエラー", "status": 500}), 500


def _configure_logging(app):
    """ログ設定を行う"""
    if app.testing:
        return

    log_level = logging.DEBUG if app.debug else logging.INFO

    # コンソールハンドラ
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    console_handler.setFormatter(console_formatter)

    # ファイルハンドラ（本番環境用）
    if not app.debug:
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/app.log", maxBytes=10_240_000, backupCount=10
        )
        file_handler.setLevel(logging.WARNING)
        file_formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s (%(pathname)s:%(lineno)d): "
            "%(message)s"
        )
        file_handler.setFormatter(file_formatter)
        app.logger.addHandler(file_handler)

    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)
    app.logger.info("AIエージェント・ニュースメディアプラットフォーム起動")
