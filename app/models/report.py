"""
通報モデル

フェイクニュース等の通報受付・審査・処理を管理するモデル。
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import validates

from app import db

# 有効な通報理由
VALID_REASONS = ("fake_news", "misleading", "spam", "hate_speech", "other")

# 有効な通報ステータス
VALID_REPORT_STATUSES = ("pending", "reviewing", "confirmed", "dismissed")


class Report(db.Model):
    """通報モデル"""

    __tablename__ = "reports"

    id = db.Column(
        db.String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    article_id = db.Column(
        db.String(36), db.ForeignKey("articles.id"), nullable=False
    )
    reporter_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=False
    )
    reason = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=False)
    evidence_urls = db.Column(db.Text, nullable=True)  # JSON配列
    status = db.Column(db.String(20), default="pending")
    reviewer_id = db.Column(
        db.String(36), db.ForeignKey("users.id"), nullable=True
    )
    resolution = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    @validates("reason")
    def validate_reason(self, key, reason):
        """通報理由のバリデーション"""
        if reason not in VALID_REASONS:
            raise ValueError(
                f"通報理由は {', '.join(VALID_REASONS)} のいずれかを指定してください"
            )
        return reason

    @validates("status")
    def validate_status(self, key, status):
        """ステータスのバリデーション"""
        if status not in VALID_REPORT_STATUSES:
            raise ValueError(
                f"ステータスは {', '.join(VALID_REPORT_STATUSES)} のいずれかを指定してください"
            )
        return status

    @validates("description")
    def validate_description(self, key, description):
        """説明のバリデーション: 空でないこと"""
        if not description or len(description.strip()) == 0:
            raise ValueError("通報の説明を入力してください")
        return description

    def get_evidence_urls_list(self):
        """証拠URLをリストとして取得する"""
        if not self.evidence_urls:
            return []
        try:
            return json.loads(self.evidence_urls)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_evidence_urls_list(self, urls_list):
        """リストから証拠URLを設定する"""
        self.evidence_urls = json.dumps(urls_list, ensure_ascii=False)

    def to_dict(self):
        """JSON用の辞書表現を返す"""
        return {
            "id": self.id,
            "article_id": self.article_id,
            "reporter_id": self.reporter_id,
            "reason": self.reason,
            "description": self.description,
            "evidence_urls": self.get_evidence_urls_list(),
            "status": self.status,
            "reviewer_id": self.reviewer_id,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "reviewed_at": (
                self.reviewed_at.isoformat() if self.reviewed_at else None
            ),
        }

    def __repr__(self):
        return f"<Report {self.reason} ({self.status})>"
