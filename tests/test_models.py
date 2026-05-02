"""
データモデルのユニットテスト

User, Article, RewardTransaction, Reportモデルのバリデーションと
基本的なCRUD操作をテストする。
"""

import json
import uuid

import pytest

from app import create_app, db
from app.models import (
    User,
    Article,
    RewardTransaction,
    Report,
    VALID_USER_TYPES,
    VALID_SPECIALTIES,
    VALID_CATEGORIES,
    VALID_STATUSES,
    VALID_STATUS_TRANSITIONS,
    VALID_TX_TYPES,
    VALID_TX_STATUSES,
    VALID_REASONS,
    VALID_REPORT_STATUSES,
)


@pytest.fixture
def app():
    """テスト用Flaskアプリケーション"""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def session(app):
    """テスト用DBセッション"""
    with app.app_context():
        yield db.session


def _make_user(**kwargs):
    """テスト用ユーザーを作成するヘルパー"""
    defaults = {
        "id": str(uuid.uuid4()),
        "username": f"test_user_{uuid.uuid4().hex[:8]}",
        "display_name": "テストユーザー",
        "user_type": "human",
    }
    defaults.update(kwargs)
    return User(**defaults)


def _make_article(author_id, **kwargs):
    """テスト用記事を作成するヘルパー"""
    defaults = {
        "id": str(uuid.uuid4()),
        "title": "テスト記事タイトル",
        "content": "A" * 100,  # 最低100文字
        "slug": f"test-article-{uuid.uuid4().hex[:8]}",
        "author_id": author_id,
        "category": "テクノロジー",
    }
    defaults.update(kwargs)
    return Article(**defaults)


# ============================================================
# User モデルテスト
# ============================================================


class TestUserModel:
    """Userモデルのテスト"""

    def test_create_user(self, session):
        """ユーザーを正常に作成できること"""
        user = _make_user()
        session.add(user)
        session.commit()

        fetched = User.query.get(user.id)
        assert fetched is not None
        assert fetched.username == user.username
        assert fetched.user_type == "human"
        assert fetched.reputation_score == 100.0
        assert fetched.is_active is True

    def test_user_types(self, session):
        """全ユーザー種別で作成できること"""
        for user_type in VALID_USER_TYPES:
            user = _make_user(user_type=user_type)
            session.add(user)
        session.commit()
        assert User.query.count() == len(VALID_USER_TYPES)

    def test_invalid_user_type(self, session):
        """無効なユーザー種別でエラーになること"""
        with pytest.raises(ValueError, match="ユーザー種別"):
            _make_user(user_type="invalid")

    def test_username_too_short(self, session):
        """ユーザー名が短すぎるとエラーになること"""
        with pytest.raises(ValueError, match="3〜100文字"):
            _make_user(username="ab")

    def test_username_invalid_chars(self, session):
        """ユーザー名に無効な文字が含まれるとエラーになること"""
        with pytest.raises(ValueError, match="英数字とアンダースコア"):
            _make_user(username="user name!")

    def test_valid_wallet_address(self, session):
        """有効なウォレットアドレスを設定できること"""
        user = _make_user(wallet_address="rN7n3473SaZBCG4dFL83w7p1W9cgPJKXuG")
        session.add(user)
        session.commit()
        assert user.wallet_address == "rN7n3473SaZBCG4dFL83w7p1W9cgPJKXuG"

    def test_invalid_wallet_address_no_r(self, session):
        """rで始まらないウォレットアドレスでエラーになること"""
        with pytest.raises(ValueError, match="'r'で始まる"):
            _make_user(wallet_address="xN7n3473SaZBCG4dFL83w7p1W9")

    def test_invalid_wallet_address_too_short(self, session):
        """短すぎるウォレットアドレスでエラーになること"""
        with pytest.raises(ValueError, match="25〜35文字"):
            _make_user(wallet_address="rShort")

    def test_reputation_score_bounds(self, session):
        """評判スコアの範囲外でエラーになること"""
        with pytest.raises(ValueError, match="0.0〜1000.0"):
            _make_user(reputation_score=-1.0)
        with pytest.raises(ValueError, match="0.0〜1000.0"):
            _make_user(reputation_score=1001.0)

    def test_user_to_dict(self, session):
        """to_dict()が正しい辞書を返すこと"""
        user = _make_user()
        session.add(user)
        session.commit()

        d = user.to_dict()
        assert d["id"] == user.id
        assert d["username"] == user.username
        assert d["user_type"] == "human"
        assert "created_at" in d

    def test_user_defaults(self, session):
        """デフォルト値が正しく設定されること"""
        user = _make_user()
        session.add(user)
        session.commit()

        assert user.total_articles == 0
        assert user.total_rewards_xrp == 0.0
        assert user.total_penalties_xrp == 0.0
        assert user.is_verified is False
        assert user.is_admin is False
        assert user.language == "ja"


# ============================================================
# Article モデルテスト
# ============================================================


class TestArticleModel:
    """Articleモデルのテスト"""

    def test_create_article(self, session):
        """記事を正常に作成できること"""
        user = _make_user()
        session.add(user)
        session.commit()

        article = _make_article(author_id=user.id)
        session.add(article)
        session.commit()

        fetched = Article.query.get(article.id)
        assert fetched is not None
        assert fetched.status == "draft"
        assert fetched.author_id == user.id

    def test_title_too_long(self, session):
        """タイトルが長すぎるとエラーになること"""
        user = _make_user()
        session.add(user)
        session.commit()

        with pytest.raises(ValueError, match="500文字以内"):
            _make_article(author_id=user.id, title="A" * 501)

    def test_title_empty(self, session):
        """タイトルが空だとエラーになること"""
        user = _make_user()
        session.add(user)
        session.commit()

        with pytest.raises(ValueError, match="1文字以上"):
            _make_article(author_id=user.id, title="")

    def test_content_too_short(self, session):
        """本文が短すぎるとエラーになること"""
        user = _make_user()
        session.add(user)
        session.commit()

        with pytest.raises(ValueError, match="100文字以上"):
            _make_article(author_id=user.id, content="短い本文")

    def test_invalid_category(self, session):
        """無効なカテゴリでエラーになること"""
        user = _make_user()
        session.add(user)
        session.commit()

        with pytest.raises(ValueError, match="カテゴリは"):
            _make_article(author_id=user.id, category="invalid")

    def test_invalid_status(self, session):
        """無効なステータスでエラーになること"""
        user = _make_user()
        session.add(user)
        session.commit()

        with pytest.raises(ValueError, match="ステータスは"):
            _make_article(author_id=user.id, status="invalid")

    def test_status_transition_valid(self, session):
        """有効なステータス遷移が成功すること"""
        user = _make_user()
        session.add(user)
        session.commit()

        article = _make_article(author_id=user.id)
        session.add(article)
        session.commit()

        # draft -> published
        assert article.validate_status_transition("published") is True

    def test_status_transition_invalid(self, session):
        """無効なステータス遷移でエラーになること"""
        user = _make_user()
        session.add(user)
        session.commit()

        article = _make_article(author_id=user.id)
        session.add(article)
        session.commit()

        # draft -> removed は不可
        with pytest.raises(ValueError, match="遷移は許可されていません"):
            article.validate_status_transition("removed")

    def test_tags_json(self, session):
        """タグのJSON変換が正しく動作すること"""
        user = _make_user()
        session.add(user)
        session.commit()

        article = _make_article(author_id=user.id)
        article.set_tags_list(["AI", "テクノロジー", "ニュース"])
        session.add(article)
        session.commit()

        assert article.get_tags_list() == ["AI", "テクノロジー", "ニュース"]

    def test_source_urls_json(self, session):
        """ソースURLのJSON変換が正しく動作すること"""
        user = _make_user()
        session.add(user)
        session.commit()

        article = _make_article(author_id=user.id)
        article.set_source_urls_list(["https://example.com/1", "https://example.com/2"])
        session.add(article)
        session.commit()

        assert article.get_source_urls_list() == [
            "https://example.com/1",
            "https://example.com/2",
        ]

    def test_article_to_dict(self, session):
        """to_dict()が正しい辞書を返すこと"""
        user = _make_user()
        session.add(user)
        session.commit()

        article = _make_article(author_id=user.id)
        article.set_tags_list(["AI"])
        session.add(article)
        session.commit()

        d = article.to_dict()
        assert d["id"] == article.id
        assert d["tags"] == ["AI"]
        assert d["status"] == "draft"

    def test_article_author_relationship(self, session):
        """記事と著者のリレーションシップが正しいこと"""
        user = _make_user()
        session.add(user)
        session.commit()

        article = _make_article(author_id=user.id)
        session.add(article)
        session.commit()

        assert article.author.id == user.id
        assert user.articles.count() == 1


# ============================================================
# RewardTransaction モデルテスト
# ============================================================


class TestRewardTransactionModel:
    """RewardTransactionモデルのテスト"""

    def test_create_reward(self, session):
        """報酬トランザクションを正常に作成できること"""
        user = _make_user()
        session.add(user)
        session.commit()

        tx = RewardTransaction(
            user_id=user.id,
            tx_type="reward",
            amount_xrp=1.5,
            reason="記事人気報酬",
        )
        session.add(tx)
        session.commit()

        fetched = RewardTransaction.query.get(tx.id)
        assert fetched is not None
        assert fetched.tx_type == "reward"
        assert fetched.amount_xrp == 1.5
        assert fetched.status == "pending"

    def test_invalid_tx_type(self, session):
        """無効なトランザクション種別でエラーになること"""
        user = _make_user()
        session.add(user)
        session.commit()

        with pytest.raises(ValueError, match="トランザクション種別"):
            RewardTransaction(
                user_id=user.id,
                tx_type="invalid",
                amount_xrp=1.0,
            )

    def test_negative_amount(self, session):
        """負の金額でエラーになること"""
        user = _make_user()
        session.add(user)
        session.commit()

        with pytest.raises(ValueError, match="0以上"):
            RewardTransaction(
                user_id=user.id,
                tx_type="reward",
                amount_xrp=-1.0,
            )

    def test_reward_transaction_to_dict(self, session):
        """to_dict()が正しい辞書を返すこと"""
        user = _make_user()
        session.add(user)
        session.commit()

        tx = RewardTransaction(
            user_id=user.id,
            tx_type="penalty",
            amount_xrp=100.0,
            reason="フェイクニュース罰金",
        )
        session.add(tx)
        session.commit()

        d = tx.to_dict()
        assert d["tx_type"] == "penalty"
        assert d["amount_xrp"] == 100.0

    def test_reward_user_relationship(self, session):
        """トランザクションとユーザーのリレーションシップが正しいこと"""
        user = _make_user()
        session.add(user)
        session.commit()

        tx = RewardTransaction(
            user_id=user.id,
            tx_type="reward",
            amount_xrp=5.0,
        )
        session.add(tx)
        session.commit()

        assert tx.user.id == user.id
        assert user.reward_transactions.count() == 1


# ============================================================
# Report モデルテスト
# ============================================================


class TestReportModel:
    """Reportモデルのテスト"""

    def test_create_report(self, session):
        """通報を正常に作成できること"""
        user = _make_user()
        reporter = _make_user()
        session.add_all([user, reporter])
        session.commit()

        article = _make_article(author_id=user.id)
        session.add(article)
        session.commit()

        report = Report(
            article_id=article.id,
            reporter_id=reporter.id,
            reason="fake_news",
            description="この記事は虚偽の情報を含んでいます",
        )
        session.add(report)
        session.commit()

        fetched = Report.query.get(report.id)
        assert fetched is not None
        assert fetched.reason == "fake_news"
        assert fetched.status == "pending"

    def test_invalid_reason(self, session):
        """無効な通報理由でエラーになること"""
        with pytest.raises(ValueError, match="通報理由"):
            Report(
                article_id=str(uuid.uuid4()),
                reporter_id=str(uuid.uuid4()),
                reason="invalid_reason",
                description="テスト",
            )

    def test_empty_description(self, session):
        """空の説明でエラーになること"""
        with pytest.raises(ValueError, match="説明を入力"):
            Report(
                article_id=str(uuid.uuid4()),
                reporter_id=str(uuid.uuid4()),
                reason="fake_news",
                description="",
            )

    def test_evidence_urls_json(self, session):
        """証拠URLのJSON変換が正しく動作すること"""
        user = _make_user()
        reporter = _make_user()
        session.add_all([user, reporter])
        session.commit()

        article = _make_article(author_id=user.id)
        session.add(article)
        session.commit()

        report = Report(
            article_id=article.id,
            reporter_id=reporter.id,
            reason="misleading",
            description="誤解を招く内容です",
        )
        report.set_evidence_urls_list(["https://evidence.example.com/1"])
        session.add(report)
        session.commit()

        assert report.get_evidence_urls_list() == ["https://evidence.example.com/1"]

    def test_report_to_dict(self, session):
        """to_dict()が正しい辞書を返すこと"""
        user = _make_user()
        reporter = _make_user()
        session.add_all([user, reporter])
        session.commit()

        article = _make_article(author_id=user.id)
        session.add(article)
        session.commit()

        report = Report(
            article_id=article.id,
            reporter_id=reporter.id,
            reason="spam",
            description="スパム記事です",
        )
        session.add(report)
        session.commit()

        d = report.to_dict()
        assert d["reason"] == "spam"
        assert d["status"] == "pending"

    def test_report_relationships(self, session):
        """通報のリレーションシップが正しいこと"""
        user = _make_user()
        reporter = _make_user()
        session.add_all([user, reporter])
        session.commit()

        article = _make_article(author_id=user.id)
        session.add(article)
        session.commit()

        report = Report(
            article_id=article.id,
            reporter_id=reporter.id,
            reason="fake_news",
            description="虚偽の情報です",
        )
        session.add(report)
        session.commit()

        assert report.reporter.id == reporter.id
        assert report.article.id == article.id
        assert article.reports.count() == 1
        assert reporter.submitted_reports.count() == 1


# ============================================================
# Constants テスト
# ============================================================


class TestConstants:
    """定数のテスト"""

    def test_valid_user_types(self):
        assert "human" in VALID_USER_TYPES
        assert "ai_agent" in VALID_USER_TYPES
        assert "external_agent" in VALID_USER_TYPES

    def test_valid_categories(self):
        assert "テクノロジー" in VALID_CATEGORIES
        assert "政治" in VALID_CATEGORIES
        assert len(VALID_CATEGORIES) == 10

    def test_valid_statuses(self):
        assert "draft" in VALID_STATUSES
        assert "published" in VALID_STATUSES
        assert "flagged" in VALID_STATUSES
        assert "removed" in VALID_STATUSES

    def test_valid_status_transitions(self):
        assert "published" in VALID_STATUS_TRANSITIONS["draft"]
        assert "flagged" in VALID_STATUS_TRANSITIONS["published"]
        assert "removed" in VALID_STATUS_TRANSITIONS["published"]
        assert len(VALID_STATUS_TRANSITIONS["removed"]) == 0

    def test_valid_reasons(self):
        assert "fake_news" in VALID_REASONS
        assert "misleading" in VALID_REASONS
        assert "spam" in VALID_REASONS
        assert "hate_speech" in VALID_REASONS
        assert "other" in VALID_REASONS
