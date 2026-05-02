"""
報酬管理サービス

記事の人気度に基づく報酬計算と、報酬・罰金履歴取得を提供する。
XRPLの実送金は今後のバッチ処理で利用する。
"""

from app.models import Article, RewardTransaction, User


VIEW_REWARD_XRP = 0.001
LIKE_REWARD_MULTIPLIER = 5.0
VIRAL_VIEW_THRESHOLD = 10_000
VIRAL_BONUS_XRP = 10.0


def calculate_article_reward(article: Article) -> float:
    """
    記事の閲覧数・いいね数・バイラルボーナスから報酬額を計算する。
    """
    if article.status == "removed":
        return 0.0

    view_count = max(0, article.view_count or 0)
    like_count = max(0, article.like_count or 0)
    reward = (view_count * VIEW_REWARD_XRP) + (
        like_count * VIEW_REWARD_XRP * LIKE_REWARD_MULTIPLIER
    )
    if view_count >= VIRAL_VIEW_THRESHOLD:
        reward += VIRAL_BONUS_XRP
    return round(reward, 6)


def calculate_distributable_reward(article: Article) -> float:
    """
    既に分配済みの報酬を差し引いた、追加配布可能額を返す。
    """
    reward = calculate_article_reward(article)
    distributed = max(0.0, article.reward_distributed or 0.0)
    return round(max(0.0, reward - distributed), 6)


def get_user_reward_summary(user_id: str) -> dict:
    """
    ユーザーの報酬・罰金サマリーを返す。
    """
    user = User.query.get(user_id)
    if not user:
        raise ValueError("ユーザーが見つかりません")

    rewards = RewardTransaction.query.filter_by(
        user_id=user_id,
        tx_type="reward",
    ).all()
    penalties = RewardTransaction.query.filter_by(
        user_id=user_id,
        tx_type="penalty",
    ).all()

    return {
        "user": user.to_dict(),
        "total_rewards_xrp": sum(tx.amount_xrp for tx in rewards),
        "total_penalties_xrp": sum(tx.amount_xrp for tx in penalties),
        "pending_rewards_xrp": sum(
            tx.amount_xrp for tx in rewards if tx.status in ("pending", "submitted")
        ),
        "confirmed_rewards_xrp": sum(
            tx.amount_xrp for tx in rewards if tx.status == "confirmed"
        ),
    }


def get_user_reward_history(user_id: str, tx_type=None):
    """
    ユーザーの報酬・罰金履歴を新しい順に返す。
    """
    if not User.query.get(user_id):
        raise ValueError("ユーザーが見つかりません")

    query = RewardTransaction.query.filter_by(user_id=user_id)
    if tx_type:
        query = query.filter_by(tx_type=tx_type)
    return query.order_by(RewardTransaction.created_at.desc()).all()

