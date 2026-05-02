"""
アプリケーション設定モジュール

環境ごとの設定クラスを定義する。
すべての機密情報は環境変数から読み込む。
"""

import os
from datetime import timedelta


class Config:
    """基本設定クラス（全環境共通）"""

    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # SQLAlchemy
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES_HOURS", "24"))
    )
    JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")

    # Redis
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Celery
    CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND = os.environ.get(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/2"
    )

    # XRPL
    XRPL_NODE_URL = os.environ.get(
        "XRPL_NODE_URL", "https://s.altnet.rippletest.net:51234"
    )
    XRPL_FALLBACK_NODE_URL = os.environ.get(
        "XRPL_FALLBACK_NODE_URL", "https://s.devnet.rippletest.net:51234"
    )

    # OpenClaw
    OPENCLAW_API_KEY = os.environ.get("OPENCLAW_API_KEY", "")

    # Xaman Wallet
    XAMAN_API_KEY = os.environ.get("XAMAN_API_KEY", "")
    XAMAN_API_SECRET = os.environ.get("XAMAN_API_SECRET", "")

    # Worldcoin World ID (OIDC)
    WORLD_ID_CLIENT_ID = os.environ.get("WORLD_ID_CLIENT_ID", "")
    WORLD_ID_CLIENT_SECRET = os.environ.get("WORLD_ID_CLIENT_SECRET", "")

    # Flask-Babel
    BABEL_DEFAULT_LOCALE = "ja"
    BABEL_DEFAULT_TIMEZONE = "Asia/Tokyo"

    # Flask-Limiter
    RATELIMIT_STORAGE_URI = os.environ.get(
        "RATELIMIT_STORAGE_URI", "redis://localhost:6379/3"
    )
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "200/hour")

    # Rate limits
    AUTH_RATE_LIMIT = "5/hour"
    REPORT_RATE_LIMIT = "10/hour"

    # Platform wallet
    PLATFORM_WALLET_ADDRESS = os.environ.get("PLATFORM_WALLET_ADDRESS", "")
    PLATFORM_WALLET_SECRET = os.environ.get("PLATFORM_WALLET_SECRET", "")


class DevelopmentConfig(Config):
    """開発環境設定"""

    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///dev.db"
    )


class TestingConfig(Config):
    """テスト環境設定"""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///test.db"
    )
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    """本番環境設定"""

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/ai_news_media"
    )
    XRPL_NODE_URL = os.environ.get(
        "XRPL_NODE_URL", "https://xrplcluster.com"
    )
    XRPL_FALLBACK_NODE_URL = os.environ.get(
        "XRPL_FALLBACK_NODE_URL", "https://s1.ripple.com:51234"
    )


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
