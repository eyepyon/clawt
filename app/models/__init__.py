"""
データモデルパッケージ

SQLAlchemyモデル定義を格納する。
User, Article, RewardTransaction, Report等のモデルを含む。
"""

from app.models.user import User, VALID_USER_TYPES, VALID_SPECIALTIES  # noqa: F401
from app.models.article import (  # noqa: F401
    Article,
    VALID_CATEGORIES,
    VALID_STATUSES,
    VALID_STATUS_TRANSITIONS,
)
from app.models.reward_transaction import (  # noqa: F401
    RewardTransaction,
    VALID_TX_TYPES,
    VALID_TX_STATUSES,
)
from app.models.report import (  # noqa: F401
    Report,
    VALID_REASONS,
    VALID_REPORT_STATUSES,
)

__all__ = [
    "User",
    "VALID_USER_TYPES",
    "VALID_SPECIALTIES",
    "Article",
    "VALID_CATEGORIES",
    "VALID_STATUSES",
    "VALID_STATUS_TRANSITIONS",
    "RewardTransaction",
    "VALID_TX_TYPES",
    "VALID_TX_STATUSES",
    "Report",
    "VALID_REASONS",
    "VALID_REPORT_STATUSES",
]
