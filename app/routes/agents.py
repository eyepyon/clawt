"""
エージェント管理ルート

記者エージェントの一覧取得、詳細確認、タスク割り当て、
無効化等のAPIエンドポイントを定義する。
"""

import logging

from flask import Blueprint, jsonify, request

from app import csrf, db, limiter
from app.models import User
from app.services.agent_manager import (
    assign_task,
    decrease_reputation,
    get_agent_tasks,
)
from app.services.jwt_auth import jwt_required

logger = logging.getLogger(__name__)

agents_bp = Blueprint("agents", __name__)

# API ルートは CSRF 保護を免除
csrf.exempt(agents_bp)


@agents_bp.route("/api/agents", methods=["GET"])
@jwt_required
def list_agents():
    """
    エージェント一覧取得API

    GET /agents/api/agents?active_only=true

    クエリパラメータ:
        - active_only: "true" の場合アクティブなエージェントのみ返す（デフォルト: false）

    Returns:
        JSON: エージェント一覧
    """
    active_only = request.args.get("active_only", "false").lower() == "true"

    query = User.query.filter_by(user_type="ai_agent")
    if active_only:
        query = query.filter_by(is_active=True)

    agents = query.order_by(User.created_at.desc()).all()

    return jsonify({
        "agents": [agent.to_dict() for agent in agents],
        "total": len(agents),
    }), 200


@agents_bp.route("/api/agents/<string:agent_id>", methods=["GET"])
@jwt_required
def get_agent(agent_id):
    """
    エージェント詳細取得API

    GET /agents/api/agents/<id>

    Returns:
        JSON: エージェント詳細情報（タスク一覧を含む）
    """
    agent = User.query.get(agent_id)
    if not agent:
        return jsonify({"error": "エージェントが見つかりません"}), 404

    if agent.user_type != "ai_agent":
        return jsonify({"error": "指定されたユーザーはAIエージェントではありません"}), 400

    agent_data = agent.to_dict()
    agent_data["tasks"] = get_agent_tasks(agent_id)

    return jsonify({"agent": agent_data}), 200


@agents_bp.route("/api/agents/<string:agent_id>/tasks", methods=["POST"])
@jwt_required
def create_task(agent_id):
    """
    エージェントタスク割り当てAPI

    POST /agents/api/agents/<id>/tasks

    リクエストボディ:
        - task_type: "search_trend" | "write_article" | "find_sources" (必須)
        - params: タスクパラメータ (任意)

    Returns:
        JSON: 作成されたタスク情報
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "リクエストボディが必要です"}), 400

    task_type = data.get("task_type")
    if not task_type:
        return jsonify({"error": "タスク種別は必須です"}), 400

    params = data.get("params", {})

    try:
        task = assign_task(agent_id, task_type, params)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({
        "message": "タスクを割り当てました",
        "task": task,
    }), 201


@agents_bp.route("/api/agents/<string:agent_id>/deactivate", methods=["PUT"])
@jwt_required
def deactivate_agent(agent_id):
    """
    エージェント無効化API（管理者のみ）

    PUT /agents/api/agents/<id>/deactivate

    リクエストボディ:
        - reason: 無効化理由 (任意)

    Returns:
        JSON: 更新されたエージェント情報
    """
    # 管理者権限チェック
    current_user = User.query.get(request.current_user_id)
    if not current_user or not current_user.is_admin:
        return jsonify({"error": "管理者権限が必要です"}), 403

    agent = User.query.get(agent_id)
    if not agent:
        return jsonify({"error": "エージェントが見つかりません"}), 404

    if agent.user_type != "ai_agent":
        return jsonify({"error": "指定されたユーザーはAIエージェントではありません"}), 400

    if not agent.is_active:
        return jsonify({"error": "このエージェントは既に無効化されています"}), 400

    data = request.get_json() or {}
    reason = data.get("reason", "管理者による手動無効化")

    agent.is_active = False
    db.session.commit()

    logger.info(
        "エージェント '%s' を無効化しました（理由: %s）",
        agent.username,
        reason,
    )

    return jsonify({
        "message": "エージェントを無効化しました",
        "agent": agent.to_dict(),
        "reason": reason,
    }), 200
