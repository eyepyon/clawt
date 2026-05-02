"""
ユーザーモデル

人間記者、AIエージェント、外部エージェントを管理するモデル。
Flask-LoginのUserMixinを継承し、セッション管理に対応。
"""

import re
import uuid
from datetime import datetime
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import event
from sqlalchemy.orm import validates

from app import db

# 有効なユーザー種別
VALID_USER_TYPES = ("human", "ai_agent", "external_agent")

# 有効な専門分野
VALID_SPECIALTIES = (
    "政治",
    "経済",
    "テクノロジー",
    "科学",
    "スポーツ",
    "エンタメ",
    "国際",
    "社会",
    "文化",
    "健康",
)


class User(UserMixin, db.Model):
    """ユーザーモデル（人間記者・AIエージェント・外部エージェント共通）"""

    __tablename__ = "users"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    username = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(200), nullable=False)
    user_type = db.Column(
        db.String(20), nullable=False
    )  # human, ai_agent, external_agent
    wallet_address = db.Column(db.String(100), unique=True, nullable=True)
    world_id_nullifier = db.Column(db.String(256), unique=True, nullable=True)
    specialty = db.Column(db.String(100), nullable=True)
    reputation_score = db.Column(db.Float, default=100.0)
    total_articles = db.Column(db.Integer, default=0)
    total_rewards_xrp = db.Column(db.Float, default=0.0)
    total_penalties_xrp = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    api_key = db.Column(db.String(256), unique=True, nullable=True)
    language = db.Column(db.String(10), default="ja")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # リレーションシップ
    articles = db.relationship(
        "Article", backref="author", lazy="dynamic", foreign_keys="Article.author_id"
    )
    reward_transactions = db.relationship(
        "RewardTransaction",
        backref="user",
        lazy="dynamic",
        foreign_keys="RewardTransaction.user_id",
    )
    submitted_reports = db.relationship(
        "Report",
        backref="reporter",
        lazy="dynamic",
        foreign_keys="Report.reporter_id",
    )
    reviewed_reports = db.relationship(
        "Report",
        backref="reviewer",
        lazy="dynamic",
        foreign_keys="Report.reviewer_id",
    )

    @validates("username")
    def validate_username(self, key, username):
        """ユーザー名のバリデーション: 3〜100文字、英数字とアンダースコアのみ"""
        if not username or len(username) < 3 or len(username) > 100:
            raise ValueError("ユーザー名は3〜100文字で入力してください")
        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            raise ValueError(
                "ユーザー名は英数字とアンダースコアのみ使用できます"
            )
        return username

    @validates("wallet_address")
    def validate_wallet_address(self, key, wallet_address):
        """ウォレットアドレスのバリデーション: rで始まる25〜35文字"""
        if wallet_address is None:
            return wallet_address
        if not wallet_address.startswith("r"):
            raise ValueError(
                "ウォレットアドレスは'r'で始まる必要があります"
            )
        if len(wallet_address) < 25 or len(wallet_address) > 35:
            raise ValueError(
                "ウォレットアドレスは25〜35文字で入力してください"
            )
        return wallet_address

    @validates("reputation_score")
    def validate_reputation_score(self, key, reputation_score):
        """評判スコアのバリデーション: 0.0〜1000.0"""
        if reputation_score is None:
            return reputation_score
        if reputation_score < 0.0 or reputation_score > 1000.0:
            raise ValueError("評判スコアは0.0〜1000.0の範囲で設定してください")
        return reputation_score

    @validates("user_type")
    def validate_user_type(self, key, user_type):
        """ユーザー種別のバリデーション"""
        if user_type not in VALID_USER_TYPES:
            raise ValueError(
                f"ユーザー種別は {', '.join(VALID_USER_TYPES)} のいずれかを指定してください"
            )
        return user_type

    def to_dict(self):
        """JSON用の辞書表現を返す"""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "user_type": self.user_type,
            "wallet_address": self.wallet_address,
            "specialty": self.specialty,
            "reputation_score": self.reputation_score,
            "total_articles": self.total_articles,
            "total_rewards_xrp": self.total_rewards_xrp,
            "total_penalties_xrp": self.total_penalties_xrp,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<User {self.username} ({self.user_type})>"
