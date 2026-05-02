"""
エージェント管理サービス

OpenClaw SDKを使用した記者エージェントの作成・管理・監視を行う。
エージェントのライフサイクル管理、タスク割り当て、評判スコア管理を提供する。
x402-xrplを使用したエージェント支払いセッション管理も含む。
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, Tuple

from flask import current_app

from app import db
from app.models import User, VALID_SPECIALTIES

logger = logging.getLogger(__name__)

# タスクステータス定数
VALID_TASK_STATUSES = ("pending", "running", "completed", "failed")
VALID_TASK_TYPES = ("search_trend", "write_article", "find_sources")

# インメモリタスクストア（将来的にはRedis/DBに移行）
_task_store: dict = {}


def create_reporter_agent(name: str, specialty: str, openclaw_config: dict) -> User:
    """
    OpenClaw SDKを使用して新しい記者エージェントを作成する。
    XRPLウォレットを自動生成し、wallet_addressとwallet_seedをDBに保存する。

    Args:
        name: エージェント名（1〜100文字）
        specialty: 専門分野（VALID_SPECIALTIESに含まれること）
        openclaw_config: OpenClaw設定辞書（api_keyを含む）

    Returns:
        User: 作成されたエージェントのUserオブジェクト

    Raises:
        ValueError: 入力バリデーションエラー
    """
    # 入力バリデーション
    if not name or len(name) > 100:
        raise ValueError("エージェント名は1〜100文字で入力してください")

    if specialty not in VALID_SPECIALTIES:
        raise ValueError(
            f"専門分野は {', '.join(VALID_SPECIALTIES)} のいずれかを指定してください"
        )

    # ユーザー名を生成（英数字とアンダースコアのみ）
    base_username = f"agent_{name.lower().replace(' ', '_').replace('-', '_')}"
    # 非ASCII文字を除去
    username = "".join(
        c for c in base_username if c.isascii() and (c.isalnum() or c == "_")
    )
    if len(username) < 3:
        username = f"agent_{uuid.uuid4().hex[:8]}"
    # ユーザー名の重複を回避
    if User.query.filter_by(username=username).first():
        username = f"{username}_{uuid.uuid4().hex[:6]}"

    # XRPLウォレット生成（アドレスとシードの両方を取得）
    wallet_address, wallet_seed = _generate_xrpl_wallet()

    # OpenClawエージェント作成（SDK利用可能時）
    _create_openclaw_agent(name, specialty, openclaw_config)

    # DBにエージェントプロファイル保存
    agent_id = str(uuid.uuid4())
    agent = User(
        id=agent_id,
        username=username,
        display_name=name,
        user_type="ai_agent",
        wallet_address=wallet_address,
        wallet_seed=wallet_seed,
        specialty=specialty,
        reputation_score=100.0,
        is_active=True,
        is_verified=True,
    )
    db.session.add(agent)
    db.session.commit()

    logger.info("記者エージェント '%s' を作成しました（ID: %s）", name, agent_id)
    return agent


def _generate_xrpl_wallet() -> Tuple[str, Optional[str]]:
    """
    XRPLテストネットウォレットを生成する。
    wallet_addressとwallet_seedの両方を返す。
    xrpl-pyが利用できない場合はフォールバックアドレスを生成する。

    Returns:
        Tuple[str, Optional[str]]: (ウォレットアドレス, ウォレットシード)
    """
    try:
        from xrpl.clients import JsonRpcClient
        from xrpl.wallet import generate_faucet_wallet

        client = JsonRpcClient("https://s.altnet.rippletest.net:51234")
        wallet = generate_faucet_wallet(client)
        logger.info("XRPLウォレットを生成しました: %s", wallet.classic_address)
        return wallet.classic_address, wallet.seed
    except Exception as e:
        logger.warning(
            "XRPLウォレット生成に失敗しました。フォールバックアドレスを使用します: %s",
            str(e),
        )
        # フォールバック: テスト用のダミーアドレス生成
        return f"r{uuid.uuid4().hex[:24].upper()}", None


def get_agent_x402_session(agent_id: str):
    """
    エージェント用のx402対応requestsセッションを取得する。
    エージェントのwallet_seedを使用してx402セッションを作成する。

    Args:
        agent_id: エージェントID

    Returns:
        x402対応のrequestsセッション

    Raises:
        ValueError: エージェントが見つからない、またはwallet_seedが未設定の場合
    """
    agent = User.query.get(agent_id)
    if not agent:
        raise ValueError("エージェントが見つかりません")
    if agent.user_type != "ai_agent":
        raise ValueError("指定されたユーザーはAIエージェントではありません")
    if not agent.wallet_seed:
        raise ValueError("エージェントのウォレットシードが設定されていません")

    from app.services.x402_payment import create_agent_x402_session

    return create_agent_x402_session(agent.wallet_seed)


def _create_openclaw_agent(name: str, specialty: str, openclaw_config: dict) -> None:
    """
    OpenClaw SDKでエージェントインスタンスを作成する。
    SDKが利用できない場合はグレースフルにスキップする。

    Args:
        name: エージェント名
        specialty: 専門分野
        openclaw_config: OpenClaw設定辞書
    """
    try:
        from openclaw import OpenClaw

        api_key = openclaw_config.get("api_key", "")
        if not api_key:
            logger.warning("OpenClaw APIキーが設定されていません。スキップします。")
            return

        claw = OpenClaw(api_key=api_key)
        claw.create_agent(
            name=name,
            instructions=(
                f"あなたは{specialty}専門のニュース記者です。"
                f"日本語で正確なニュース記事を作成してください。"
                f"情報源を必ず明記し、事実確認を徹底してください。"
            ),
            tools=["web_search", "article_writer", "source_verifier"],
        )
        logger.info("OpenClawエージェント '%s' を作成しました", name)
    except ImportError:
        logger.warning(
            "OpenClaw SDKが利用できません。エージェントはDB登録のみ行います。"
        )
    except Exception as e:
        logger.warning(
            "OpenClawエージェント作成に失敗しました: %s。DB登録のみ行います。",
            str(e),
        )


def assign_task(agent_id: str, task_type: str, params: dict) -> dict:
    """
    エージェントにタスクを割り当てる。

    Args:
        agent_id: エージェントID
        task_type: タスク種別（"search_trend", "write_article", "find_sources"）
        params: タスクパラメータ

    Returns:
        dict: タスク情報（task_id, agent_id, task_type, status, params, result）

    Raises:
        ValueError: バリデーションエラー
    """
    # エージェント存在確認
    agent = User.query.get(agent_id)
    if not agent:
        raise ValueError("エージェントが見つかりません")
    if agent.user_type != "ai_agent":
        raise ValueError("指定されたユーザーはAIエージェントではありません")
    if not agent.is_active:
        raise ValueError("このエージェントは無効化されています")

    # タスク種別バリデーション
    if task_type not in VALID_TASK_TYPES:
        raise ValueError(
            f"タスク種別は {', '.join(VALID_TASK_TYPES)} のいずれかを指定してください"
        )

    # タスク作成
    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "agent_id": agent_id,
        "task_type": task_type,
        "status": "pending",
        "params": params or {},
        "result": None,
        "created_at": datetime.utcnow().isoformat(),
    }
    _task_store[task_id] = task

    # OpenClaw SDKでタスク実行を試みる
    task["status"] = "running"
    try:
        result = _execute_openclaw_task(agent_id, task_type, params)
        task["status"] = "completed"
        task["result"] = result
    except Exception as e:
        logger.warning("タスク実行に失敗しました: %s", str(e))
        task["status"] = "failed"
        task["result"] = {"error": str(e)}

    _task_store[task_id] = task
    logger.info(
        "タスク '%s' をエージェント '%s' に割り当てました（ステータス: %s）",
        task_id,
        agent_id,
        task["status"],
    )
    return task


def get_task_status(task_id: str) -> Optional[dict]:
    """
    タスクのステータスを取得する。

    Args:
        task_id: タスクID

    Returns:
        dict: タスク情報。見つからない場合はNone。
    """
    return _task_store.get(task_id)


def _execute_openclaw_task(agent_id: str, task_type: str, params: dict) -> dict:
    """
    OpenClaw SDKを使用してタスクを実行する。
    SDKが利用できない場合はプレースホルダー結果を返す。

    Args:
        agent_id: エージェントID
        task_type: タスク種別
        params: タスクパラメータ

    Returns:
        dict: タスク実行結果
    """
    try:
        from openclaw import OpenClaw

        api_key = current_app.config.get("OPENCLAW_API_KEY", "")
        if not api_key:
            raise ValueError("OpenClaw APIキーが設定されていません")

        claw = OpenClaw(api_key=api_key)

        if task_type == "search_trend":
            return claw.run_tool(
                agent_id=agent_id,
                tool="web_search",
                params=params,
            )
        elif task_type == "write_article":
            return claw.run_tool(
                agent_id=agent_id,
                tool="article_writer",
                params=params,
            )
        elif task_type == "find_sources":
            return claw.run_tool(
                agent_id=agent_id,
                tool="source_verifier",
                params=params,
            )
    except ImportError:
        logger.warning("OpenClaw SDKが利用できません。プレースホルダー結果を返します。")
    except Exception as e:
        logger.warning("OpenClawタスク実行エラー: %s", str(e))

    # フォールバック: プレースホルダー結果
    return {
        "status": "completed_without_sdk",
        "task_type": task_type,
        "message": "OpenClaw SDKが利用できないため、プレースホルダー結果を返しました",
    }


def get_task(task_id: str) -> Optional[dict]:
    """
    タスク情報を取得する。

    Args:
        task_id: タスクID

    Returns:
        dict: タスク情報。見つからない場合はNone。
    """
    return _task_store.get(task_id)


def get_agent_tasks(agent_id: str) -> list:
    """
    エージェントに割り当てられたタスク一覧を取得する。

    Args:
        agent_id: エージェントID

    Returns:
        list: タスク情報のリスト
    """
    return [
        task for task in _task_store.values() if task["agent_id"] == agent_id
    ]


def update_reputation(agent_id: str, delta: float) -> User:
    """
    エージェントの評判スコアを更新する。
    deltaが正の場合は増加、負の場合は減少。
    スコアは0.0〜1000.0の範囲にクランプされる。
    スコアが0に達した場合、自動的にエージェントを無効化する。

    Args:
        agent_id: エージェントID
        delta: スコア変動量（正: 増加、負: 減少）

    Returns:
        User: 更新されたユーザーオブジェクト

    Raises:
        ValueError: バリデーションエラー
    """
    agent = User.query.get(agent_id)
    if not agent:
        raise ValueError("エージェントが見つかりません")
    if agent.user_type != "ai_agent":
        raise ValueError("指定されたユーザーはAIエージェントではありません")

    # 評判スコアを更新（0.0〜1000.0の範囲にクランプ）
    new_score = max(0.0, min(1000.0, agent.reputation_score + delta))
    agent.reputation_score = new_score

    # スコアが0で自動無効化
    if agent.reputation_score <= 0.0:
        agent.is_active = False
        logger.warning(
            "エージェント '%s' の評判スコアが0以下になったため、自動無効化しました",
            agent.username,
        )

    db.session.commit()
    logger.info(
        "エージェント '%s' の評判スコアを %.1f に更新しました（変動: %+.1f）",
        agent.username,
        agent.reputation_score,
        delta,
    )
    return agent


def decrease_reputation(agent_id: str, amount: float) -> User:
    """
    エージェントの評判スコアを減少させる。
    後方互換性のためにupdate_reputationのラッパーとして残す。

    Args:
        agent_id: エージェントID
        amount: 減少量（正の値）

    Returns:
        User: 更新されたユーザーオブジェクト

    Raises:
        ValueError: バリデーションエラー
    """
    if amount < 0:
        raise ValueError("減少量は0以上の値を指定してください")
    return update_reputation(agent_id, -amount)


def deactivate_agent(agent_id: str, reason: str = "管理者による手動無効化") -> bool:
    """
    エージェントを無効化する。

    Args:
        agent_id: エージェントID
        reason: 無効化理由

    Returns:
        bool: 無効化に成功した場合True

    Raises:
        ValueError: エージェントが見つからない、またはAIエージェントでない場合
    """
    agent = User.query.get(agent_id)
    if not agent:
        raise ValueError("エージェントが見つかりません")
    if agent.user_type != "ai_agent":
        raise ValueError("指定されたユーザーはAIエージェントではありません")
    if not agent.is_active:
        raise ValueError("このエージェントは既に無効化されています")

    agent.is_active = False
    db.session.commit()

    logger.info(
        "エージェント '%s' を無効化しました（理由: %s）",
        agent.username,
        reason,
    )
    return True
