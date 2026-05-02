"""
報酬トランザクションモデル

XRPLでの報酬配布・罰金徴収のトランザクション記録を管理するモデル。
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import validates

from app import db

# 有効なトランザクション種別
VALID_TX_TYPES = ("reward", "penalty")

# 有効なトランザクションステータス
VALID_TX_STATUSES = ("pending", "submitted", "confirmed", "failed")


class RewardTransaction(db.Model):
    """報酬トランザクションモデル"""

    __tablename__ = "reward_transactions"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=False
    )
    article_id = db.Column(
        db.String(36), db.ForeignKey("articles.id"), nullable=True
    )
    tx_type = db.Column(
        db.String(20), nullable=False
    )  # "reward" or "penalty"
    amount_xrp = db.Column(db.Float, nullable=False)
    xrpl_tx_hash = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(20), default="pending")
    reason = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)

    @validates("tx_type")
    def validate_tx_type(self, key, tx_type):
        """トランザクション種別のバリデーション"""
        if tx_type not in VALID_TX_TYPES:
            raise ValueError(
                f"トランザクション種別は {', '.join(VALID_TX_TYPES)} のいずれかを指定してください"
            )
        return tx_type

    @validates("status")
    def validate_status(self, key, status):
        """ステータスのバリデーション"""
        if status not in VALID_TX_STATUSES:
            raise ValueError(
                f"ステータスは {', '.join(VALID_TX_STATUSES)} のいずれかを指定してください"
            )
        return status

    @validates("amount_xrp")
    def validate_amount_xrp(self, key, amount_xrp):
        """金額のバリデーション: 正の値"""
        if amount_xrp is None or amount_xrp < 0:
            raise ValueError("金額は0以上の値を指定してください")
        return amount_xrp

    def to_dict(self):
        """JSON用の辞書表現を返す"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "article_id": self.article_id,
            "tx_type": self.tx_type,
            "amount_xrp": self.amount_xrp,
            "xrpl_tx_hash": self.xrpl_tx_hash,
            "status": self.status,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "confirmed_at": (
                self.confirmed_at.isoformat() if self.confirmed_at else None
            ),
        }

    def __repr__(self):
        return f"<RewardTransaction {self.tx_type} {self.amount_xrp} XRP ({self.status})>"
