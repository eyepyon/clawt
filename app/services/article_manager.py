"""
記事管理サービス

記事の作成、公開、検索、ランキング、スラグ生成などの
ドメインロジックを提供する。
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional

import bleach
from sqlalchemy import or_
from slugify import slugify

from app import db
from app.models import Article, User, VALID_CATEGORIES


POPULAR_PERIODS = ("daily", "weekly", "monthly", "all")


def generate_unique_slug(title: str, article_id: Optional[str] = None) -> str:
    """
    日本語タイトルからURLセーフで一意なスラグを生成する。
    """
    base = slugify(title or "", allow_unicode=False, max_length=80).strip("-")
    if not base:
        base = f"article-{uuid.uuid4().hex[:8]}"

    candidate = base
    suffix = 2
    query = Article.query.filter_by(slug=candidate)
    if article_id:
        query = query.filter(Article.id != article_id)

    while query.first() is not None:
        candidate = f"{base}-{suffix}"
        suffix += 1
        query = Article.query.filter_by(slug=candidate)
        if article_id:
            query = query.filter(Article.id != article_id)

    return candidate


def create_article(author_id: str, data: dict) -> Article:
    """
    記事をdraftとして作成する。statusにpublishedが指定された場合は公開処理も行う。
    """
    author = User.query.get(author_id)
    if not author or not author.is_active:
        raise ValueError("投稿者が見つからないか無効化されています")

    title = data.get("title")
    content = _sanitize_content(data.get("content"))
    category = data.get("category")
    source_urls = data.get("source_urls") or []
    tags = data.get("tags") or []
    status = data.get("status", "draft")

    if category not in VALID_CATEGORIES:
        raise ValueError(
            f"カテゴリは {', '.join(VALID_CATEGORIES)} のいずれかを指定してください"
        )
    if not isinstance(source_urls, list) or len(source_urls) == 0:
        raise ValueError("ソースURLは1件以上指定してください")
    if not isinstance(tags, list):
        raise ValueError("タグは配列で指定してください")

    article = Article(
        title=title,
        content=content,
        summary=data.get("summary"),
        slug=generate_unique_slug(title),
        author_id=author_id,
        category=category,
        status="draft",
        language=data.get("language", "ja"),
    )
    article.set_tags_list(tags)
    article.set_source_urls_list(source_urls)

    if status == "published":
        publish_article(article)
    elif status != "draft":
        raise ValueError("作成時のステータスは draft または published を指定してください")

    author.total_articles = (author.total_articles or 0) + 1
    db.session.add(article)
    db.session.commit()
    return article


def update_article(article: Article, data: dict) -> Article:
    """
    記事を更新する。ステータス変更はArticleの遷移ルールに従う。
    """
    if "title" in data:
        article.title = data["title"]
        article.slug = generate_unique_slug(data["title"], article.id)
    if "content" in data:
        article.content = _sanitize_content(data["content"])
    if "summary" in data:
        article.summary = data["summary"]
    if "category" in data:
        if data["category"] not in VALID_CATEGORIES:
            raise ValueError(
                f"カテゴリは {', '.join(VALID_CATEGORIES)} のいずれかを指定してください"
            )
        article.category = data["category"]
    if "tags" in data:
        if not isinstance(data["tags"], list):
            raise ValueError("タグは配列で指定してください")
        article.set_tags_list(data["tags"])
    if "source_urls" in data:
        if not isinstance(data["source_urls"], list) or len(data["source_urls"]) == 0:
            raise ValueError("ソースURLは1件以上指定してください")
        article.set_source_urls_list(data["source_urls"])
    if "status" in data:
        _apply_status(article, data["status"])

    db.session.commit()
    return article


def publish_article(article: Article) -> Article:
    """
    draft記事を公開する。
    """
    article.validate_status_transition("published")
    article.status = "published"
    article.published_at = datetime.utcnow()
    return article


def delete_article(article: Article) -> Article:
    """
    記事をremovedにする。物理削除は行わない。
    """
    if article.status != "removed":
        article.validate_status_transition("removed")
        article.status = "removed"
    db.session.commit()
    return article


def increment_view_count(article: Article) -> Article:
    """
    記事閲覧数をDB上で増加させる。
    Redis同期は今後のタスクで拡張する。
    """
    article.view_count = (article.view_count or 0) + 1
    db.session.commit()
    return article


def search_articles(q=None, category=None, status="published"):
    """
    記事検索用のSQLAlchemy queryを返す。
    """
    query = Article.query
    if status:
        query = query.filter_by(status=status)
    if category:
        query = query.filter_by(category=category)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                Article.title.ilike(pattern),
                Article.summary.ilike(pattern),
                Article.content.ilike(pattern),
            )
        )
    return query.order_by(Article.published_at.desc(), Article.created_at.desc())


def get_popular_articles(period="daily", limit=10):
    """
    閲覧数といいね数から人気記事を取得する。
    """
    if period not in POPULAR_PERIODS:
        raise ValueError(
            f"periodは {', '.join(POPULAR_PERIODS)} のいずれかを指定してください"
        )

    query = Article.query.filter_by(status="published")
    since = _period_start(period)
    if since is not None:
        query = query.filter(Article.published_at >= since)

    return (
        query.order_by(
            (Article.view_count + Article.like_count * 5).desc(),
            Article.published_at.desc(),
        )
        .limit(limit)
        .all()
    )


def get_related_articles(article: Article, limit=3):
    """
    同カテゴリの公開済み最新記事を関連記事として返す。
    """
    return (
        Article.query.filter(
            Article.id != article.id,
            Article.category == article.category,
            Article.status == "published",
        )
        .order_by(Article.published_at.desc(), Article.created_at.desc())
        .limit(limit)
        .all()
    )


def auto_generate_article(agent_id: str, topic: str, category: str) -> Article:
    """
    記事自動生成ワークフローの最小実装。
    実際のOpenClaw連携はagent_manager側のタスク実行に委譲する。
    """
    if not topic:
        raise ValueError("トピックは必須です")

    content = (
        f"{topic}について、AI記者エージェントが収集した情報をもとにした下書きです。"
        "本記事は公開前に追加の事実確認とソース確認を行う前提で保存されています。"
        "読者に誤解を与えないよう、背景、関係者、今後の見通しを整理し、"
        "一次情報または信頼できる公開情報へのリンクを必ず添えて更新してください。"
    )
    return create_article(
        agent_id,
        {
            "title": topic,
            "content": content,
            "summary": f"{topic}に関するAI生成の下書きです。",
            "category": category,
            "tags": [category],
            "source_urls": ["https://example.com/source-required"],
            "status": "draft",
        },
    )


def serialize_article(article: Article, include_related=False) -> dict:
    """
    記事をAPIレスポンス用に変換する。
    """
    data = article.to_dict()
    if include_related:
        data["related_articles"] = [
            item.to_dict() for item in get_related_articles(article)
        ]
    return data


def _sanitize_content(content: Optional[str]) -> Optional[str]:
    if content is None:
        return content
    return bleach.clean(
        content,
        tags=["p", "br", "strong", "em", "ul", "ol", "li", "a", "blockquote"],
        attributes={"a": ["href", "title", "rel"]},
        strip=True,
    )


def _apply_status(article: Article, new_status: str) -> None:
    if new_status == article.status:
        return
    article.validate_status_transition(new_status)
    article.status = new_status
    if new_status == "published" and article.published_at is None:
        article.published_at = datetime.utcnow()


def _period_start(period: str) -> Optional[datetime]:
    now = datetime.utcnow()
    if period == "daily":
        return now - timedelta(days=1)
    if period == "weekly":
        return now - timedelta(days=7)
    if period == "monthly":
        return now - timedelta(days=30)
    return None
