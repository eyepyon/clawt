"""
報酬APIルート
"""

from flask import Blueprint, jsonify, request

from app import csrf, limiter
from app.services.jwt_auth import jwt_required
from app.services.reward_manager import (
    get_user_reward_history,
    get_user_reward_summary,
)

rewards_bp = Blueprint("rewards", __name__)
csrf.exempt(rewards_bp)


@rewards_bp.route("/api/rewards/<string:user_id>", methods=["GET"])
@limiter.limit("120/hour")
@jwt_required
def reward_summary(user_id):
    if request.current_user_id != user_id:
        return jsonify({"error": "他ユーザーの報酬情報を確認する権限がありません"}), 403

    try:
        summary = get_user_reward_summary(user_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return jsonify(summary), 200


@rewards_bp.route("/api/rewards/<string:user_id>/history", methods=["GET"])
@limiter.limit("120/hour")
@jwt_required
def reward_history(user_id):
    if request.current_user_id != user_id:
        return jsonify({"error": "他ユーザーの報酬履歴を確認する権限がありません"}), 403

    tx_type = request.args.get("tx_type")
    try:
        transactions = get_user_reward_history(user_id, tx_type=tx_type)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    return (
        jsonify({"transactions": [tx.to_dict() for tx in transactions]}),
        200,
    )

