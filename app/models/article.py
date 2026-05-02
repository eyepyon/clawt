"""
記事モデル

ニュース記事の管理モデル。
ステータス遷移、カテゴリ管理、JSON配列フィールドを含む。
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import validates

from app import db

# 有効なカテゴリ
VALID_CATEGORIES = (
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

# 有効なステータス
VALID_STATUSES = ("draft", "published", "flagged", "removed")

# 有効なステータス遷移
VALID_STATUS_TRANSITIONS = {
    "draft": {"published"},
    "published": {"flagged", "removed"},
    "flagged": {"removed", "published"},  # 通報却下時に復帰可能
    "removed": set(),  # 終端状態
}


class Article(db.Model):
    """記事モデル"""

    __tablename__ = "articles"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    summary = db.Column(db.String(1000), nullable=True)
    slug = db.Column(db.String(600), unique=True, nullable=False)
    author_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=False
    )
    category = db.Column(db.String(50), nullable=False)
    tags = db.Column(db.Text, nullable=True)  # JSON配列として保存
    source_urls = db.Column(db.Text, nullable=True)  # JSON配列として保存
    view_count = db.Column(db.Integer, default=0)
    like_count = db.Column(db.Integer, default=0)
    report_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="draft")
    language = db.Column(db.String(10), default="ja")
    reward_distributed = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    published_at = db.Column(db.DateTime, nullable=True)

    # リレーションシップ
    reward_transactions = db.relationship(
        "RewardTransaction",
        backref="article",
        lazy="dynamic",
        foreign_keys="RewardTransaction.article_id",
    )
    reports = db.relationship(
        "Report",
        backref="article",
        lazy="dynamic",
        foreign_keys="Report.article_id",
    )

    @validates("title")
    def validate_title(self, key, title):
        """タイトルのバリデーション: 1〜500文字"""
        if not title or len(title) < 1:
            raise ValueError("タイトルは1文字以上で入力してください")
        if len(title) > 500:
            raise ValueError("タイトルは500文字以内で入力してください")
        return title

    @validates("content")
    def validate_content(self, key, content):
        """本文のバリデーション: 最低100文字"""
        if not content or len(content) < 100:
            raise ValueError("本文は100文字以上で入力してください")
        return content

    @validates("category")
    def validate_category(self, key, category):
        """カテゴリのバリデーション"""
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"カテゴリは {', '.join(VALID_CATEGORIES)} のいずれかを指定してください"
            )
        return category

    @validates("status")
    def validate_status(self, key, status):
        """ステータスのバリデーション"""
        if status not in VALID_STATUSES:
            raise ValueError(
                f"ステータスは {', '.join(VALID_STATUSES)} のいずれかを指定してください"
            )
        return status

    def validate_status_transition(self, new_status):
        """ステータス遷移のバリデーション"""
        current = self.status or "draft"
        allowed = VALID_STATUS_TRANSITIONS.get(current, set())
        if new_status not in allowed:
            raise ValueError(
                f"ステータス '{current}' から '{new_status}' への遷移は許可されていません。"
                f"許可されている遷移先: {', '.join(allowed) if allowed else 'なし'}"
            )
        return True

    def get_tags_list(self):
        """タグをリストとして取得する"""
        if not self.tags:
            return []
        try:
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tags_list(self, tags_list):
        """リストからタグを設定する"""
        self.tags = json.dumps(tags_list, ensure_ascii=False)

    def get_source_urls_list(self):
        """ソースURLをリストとして取得する"""
        if not self.source_urls:
            return []
        try:
            return json.loads(self.source_urls)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_source_urls_list(self, urls_list):
        """リストからソースURLを設定する"""
        self.source_urls = json.dumps(urls_list, ensure_ascii=False)

    def to_dict(self):
        """JSON用の辞書表現を返す"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "slug": self.slug,
            "author_id": self.author_id,
            "category": self.category,
            "tags": self.get_tags_list(),
            "source_urls": self.get_source_urls_list(),
            "view_count": self.view_count,
            "like_count": self.like_count,
            "report_count": self.report_count,
            "status": self.status,
            "language": self.language,
            "reward_distributed": self.reward_distributed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "published_at": (
                self.published_at.isoformat() if self.published_at else None
            ),
        }

    def __repr__(self):
        return f"<Article {self.title[:50]} ({self.status})>"
