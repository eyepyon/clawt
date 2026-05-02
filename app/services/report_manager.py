"""
通報・罰金管理サービス
"""

from datetime import datetime

from app import db
from app.models import Article, Report, RewardTransaction, User, VALID_REASONS


AUTO_FLAG_REPORT_THRESHOLD = 3
BASE_PENALTY_XRP = 100.0
PENALTY_MULTIPLIER = 2.0
REPUTATION_PENALTY = 30.0


def submit_report(article_id: str, reporter_id: str, data: dict) -> Report:
    """
    記事通報を作成し、閾値を超えた記事を自動フラグする。
    """
    article = Article.query.get(article_id)
    if not article:
        raise ValueError("記事が見つかりません")
    if article.status == "removed":
        raise ValueError("削除済みの記事は通報できません")
    if not User.query.get(reporter_id):
        raise ValueError("通報者が見つかりません")

    reason = data.get("reason")
    if reason not in VALID_REASONS:
        raise ValueError(
            f"通報理由は {', '.join(VALID_REASONS)} のいずれかを指定してください"
        )

    report = Report(
        article_id=article_id,
        reporter_id=reporter_id,
        reason=reason,
        description=data.get("description"),
    )
    evidence_urls = data.get("evidence_urls") or []
    if not isinstance(evidence_urls, list):
        raise ValueError("証拠URLは配列で指定してください")
    report.set_evidence_urls_list(evidence_urls)

    article.report_count = (article.report_count or 0) + 1
    if article.report_count >= AUTO_FLAG_REPORT_THRESHOLD and article.status == "published":
        article.status = "flagged"

    db.session.add(report)
    db.session.commit()
    return report


def review_report(report_id: str, reviewer_id: str, status: str, resolution=None) -> Report:
    """
    管理者が通報を審査する。
    confirmedの場合は罰金処理、dismissedの場合は必要に応じて公開状態へ戻す。
    """
    reviewer = User.query.get(reviewer_id)
    if not reviewer or not reviewer.is_admin:
        raise PermissionError("管理者権限が必要です")

    report = Report.query.get(report_id)
    if not report:
        raise ValueError("通報が見つかりません")
    if status not in ("confirmed", "dismissed"):
        raise ValueError("審査結果は confirmed または dismissed を指定してください")

    report.status = status
    report.reviewer_id = reviewer_id
    report.resolution = resolution
    report.reviewed_at = datetime.utcnow()

    if status == "confirmed":
        process_fake_news_report(report)
    elif status == "dismissed" and report.article.status == "flagged":
        report.article.status = "published"

    db.session.commit()
    return report


def list_reports(status=None):
    """
    通報一覧を新しい順に返す。
    """
    query = Report.query
    if status:
        query = query.filter_by(status=status)
    return query.order_by(Report.created_at.desc())


def calculate_penalty_amount(user_id: str) -> float:
    """
    過去の罰金回数に基づいて累進罰金額を計算する。
    """
    past_penalty_count = RewardTransaction.query.filter_by(
        user_id=user_id,
        tx_type="penalty",
    ).count()
    return BASE_PENALTY_XRP * (PENALTY_MULTIPLIER ** past_penalty_count)


def process_fake_news_report(report: Report) -> RewardTransaction:
    """
    確認済み通報に対して、記事削除、罰金記録、評判減点を行う。
    """
    article = report.article
    author = article.author
    penalty = calculate_penalty_amount(author.id)

    if article.status != "removed":
        if article.status in ("published", "flagged"):
            article.status = "removed"
        elif article.status == "draft":
            article.status = "removed"

    author.reputation_score = max(0.0, (author.reputation_score or 0.0) - REPUTATION_PENALTY)
    author.total_penalties_xrp = (author.total_penalties_xrp or 0.0) + penalty
    if author.reputation_score <= 0.0:
        author.is_active = False

    tx = RewardTransaction(
        user_id=author.id,
        article_id=article.id,
        tx_type="penalty",
        amount_xrp=penalty,
        status="pending",
        reason=f"通報確認による罰金: {report.reason}",
    )
    db.session.add(tx)
    return tx

