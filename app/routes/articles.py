"""
記事管理ルート

記事の作成、取得、更新、削除、検索、人気ランキングを提供する。
"""

from flask import Blueprint, jsonify, request

from app import csrf, limiter
from app.models import Article
from app.services.article_manager import (
    create_article,
    delete_article,
    get_popular_articles,
    increment_view_count,
    search_articles,
    serialize_article,
    update_article,
)
from app.services.jwt_auth import jwt_required

articles_bp = Blueprint("articles", __name__)
csrf.exempt(articles_bp)


@articles_bp.route("/api/articles", methods=["POST"])
@limiter.limit("30/hour")
@jwt_required
def create_article_route():
    data = request.get_json() or {}
    try:
        article = create_article(request.current_user_id, data)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return (
        jsonify(
            {
                "message": "記事を作成しました",
                "article": serialize_article(article),
            }
        ),
        201,
    )


@articles_bp.route("/api/articles", methods=["GET"])
def list_articles():
    q = request.args.get("q")
    category = request.args.get("category")
    status = request.args.get("status", "published")
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)

    pagination = search_articles(q=q, category=category, status=status).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return (
        jsonify(
            {
                "articles": [serialize_article(article) for article in pagination.items],
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                },
            }
        ),
        200,
    )


@articles_bp.route("/api/articles/popular", methods=["GET"])
def popular_articles():
    period = request.args.get("period", "daily")
    limit = min(request.args.get("limit", 10, type=int), 100)
    try:
        articles = get_popular_articles(period=period, limit=limit)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"articles": [serialize_article(article) for article in articles]}), 200


@articles_bp.route("/api/articles/<string:article_id>", methods=["GET"])
def get_article(article_id):
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "記事が見つかりません"}), 404
    if article.status == "removed":
        return jsonify({"error": "この記事は削除されています"}), 410

    increment_view_count(article)
    return jsonify({"article": serialize_article(article, include_related=True)}), 200


@articles_bp.route("/api/articles/<string:article_id>", methods=["PUT"])
@limiter.limit("60/hour")
@jwt_required
def update_article_route(article_id):
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "記事が見つかりません"}), 404
    if article.author_id != request.current_user_id:
        return jsonify({"error": "この記事を編集する権限がありません"}), 403

    try:
        article = update_article(article, request.get_json() or {})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": "記事を更新しました", "article": serialize_article(article)}), 200


@articles_bp.route("/api/articles/<string:article_id>", methods=["DELETE"])
@limiter.limit("30/hour")
@jwt_required
def delete_article_route(article_id):
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "記事が見つかりません"}), 404
    if article.author_id != request.current_user_id:
        return jsonify({"error": "この記事を削除する権限がありません"}), 403

    try:
        article = delete_article(article)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"message": "記事を削除しました", "article": serialize_article(article)}), 200

