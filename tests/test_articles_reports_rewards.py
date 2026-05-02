"""
記事、通報、報酬サービスのテスト
"""

import uuid

import pytest
from hypothesis import given, strategies as st

from app import create_app, db
from app.models import Article, Report, RewardTransaction, User
from app.services.jwt_auth import generate_token
from app.services.report_manager import calculate_penalty_amount, submit_report
from app.services.reward_manager import calculate_article_reward


@pytest.fixture
def app():
    app = create_app("testing")
    app.config["JWT_SECRET_KEY"] = "test-secret-key"
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def session(app):
    with app.app_context():
        yield db.session


def _make_user(**kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "username": f"user_{uuid.uuid4().hex[:8]}",
        "display_name": "テストユーザー",
        "user_type": "human",
        "is_verified": True,
    }
    defaults.update(kwargs)
    return User(**defaults)


def _make_article(author_id, **kwargs):
    defaults = {
        "id": str(uuid.uuid4()),
        "title": "テスト記事",
        "content": "A" * 120,
        "slug": f"test-{uuid.uuid4().hex[:8]}",
        "author_id": author_id,
        "category": "テクノロジー",
        "status": "published",
    }
    defaults.update(kwargs)
    article = Article(**defaults)
    article.set_source_urls_list(["https://example.com/source"])
    return article


def _auth_header(user_id):
    token = generate_token(user_id)
    return {"Authorization": f"Bearer {token}"}


def test_create_article_api(client, session):
    user = _make_user()
    session.add(user)
    session.commit()

    response = client.post(
        "/api/articles",
        json={
            "title": "AIニュース",
            "content": "A" * 120,
            "category": "テクノロジー",
            "source_urls": ["https://example.com/source"],
            "tags": ["AI"],
            "status": "published",
        },
        headers=_auth_header(user.id),
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["article"]["status"] == "published"
    assert data["article"]["source_urls"] == ["https://example.com/source"]


def test_article_requires_source_urls(client, session):
    user = _make_user()
    session.add(user)
    session.commit()

    response = client.post(
        "/api/articles",
        json={
            "title": "ソースなし記事",
            "content": "A" * 120,
            "category": "テクノロジー",
            "source_urls": [],
        },
        headers=_auth_header(user.id),
    )

    assert response.status_code == 400
    assert "ソースURL" in response.get_json()["error"]


def test_reward_calculation_with_viral_bonus(session):
    user = _make_user()
    session.add(user)
    session.commit()

    article = _make_article(
        user.id,
        view_count=10_000,
        like_count=2,
    )
    assert calculate_article_reward(article) == 20.01


def test_removed_article_reward_is_zero(session):
    user = _make_user()
    session.add(user)
    session.commit()

    article = _make_article(user.id, status="removed", view_count=50_000, like_count=100)
    assert calculate_article_reward(article) == 0.0


def test_penalty_calculation_is_progressive(session):
    user = _make_user()
    session.add(user)
    session.commit()

    assert calculate_penalty_amount(user.id) == 100.0

    session.add(
        RewardTransaction(user_id=user.id, tx_type="penalty", amount_xrp=100.0)
    )
    session.commit()

    assert calculate_penalty_amount(user.id) == 200.0


def test_submit_report_auto_flags_article(session):
    author = _make_user()
    reporters = [_make_user() for _ in range(3)]
    session.add(author)
    session.add_all(reporters)
    session.commit()

    article = _make_article(author.id)
    session.add(article)
    session.commit()

    for reporter in reporters:
        submit_report(
            article.id,
            reporter.id,
            {"reason": "misleading", "description": "誤解を招く内容です"},
        )

    assert Article.query.get(article.id).status == "flagged"
    assert Report.query.filter_by(article_id=article.id).count() == 3


@given(
    view_count=st.integers(min_value=0, max_value=1_000_000),
    like_count=st.integers(min_value=0, max_value=1_000_000),
)
def test_reward_is_never_negative(view_count, like_count):
    article = Article(
        title="性質テスト",
        content="A" * 120,
        slug=f"property-{uuid.uuid4().hex}",
        author_id=str(uuid.uuid4()),
        category="テクノロジー",
        status="published",
        view_count=view_count,
        like_count=like_count,
    )
    assert calculate_article_reward(article) >= 0.0


@given(penalty_count=st.integers(min_value=0, max_value=8))
def test_penalty_progression_formula(penalty_count):
    amounts = [100.0 * (2.0 ** count) for count in range(penalty_count + 1)]
    assert amounts == sorted(amounts)
    assert all(amount >= 100.0 for amount in amounts)


@given(
    current=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False),
    delta=st.floats(min_value=-2000.0, max_value=2000.0, allow_nan=False),
)
def test_reputation_clamp_range(current, delta):
    new_score = max(0.0, min(1000.0, current + delta))
    assert 0.0 <= new_score <= 1000.0
