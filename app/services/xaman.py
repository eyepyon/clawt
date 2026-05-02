"""
Xaman Wallet連携サービス

Xaman (旧XUMM) Walletとの連携を管理する。
SignInペイロード作成、QRコード生成、署名検証、ウォレットアドレス取得を行う。
"""

import logging
from typing import Optional

import requests
from flask import current_app

from app import db
from app.models import User

logger = logging.getLogger(__name__)

# Xaman API エンドポイント
XAMAN_PAYLOAD_URL = "https://xumm.app/api/v1/platform/payload"


def _get_xaman_headers() -> dict:
    """Xaman API認証ヘッダーを取得する"""
    api_key = current_app.config.get("XAMAN_API_KEY", "")
    api_secret = current_app.config.get("XAMAN_API_SECRET", "")
    return {
        "X-API-Key": api_key,
        "X-API-Secret": api_secret,
        "Content-Type": "application/json",
    }


def link_xaman_wallet(user_id: str) -> Optional[dict]:
    """
    Xaman Walletとの連携を開始する。

    SignInペイロードを作成し、ユーザーがXaman Appで署名するための
    情報（ペイロードUUID、リダイレクトURL、QRコードURL）を返す。

    Args:
        user_id: ウォレットを連携するユーザーのID

    Returns:
        dict: payload_uuid, next_url, qr_url を含む辞書。
              エラー時はNone。
    """
    user = User.query.get(user_id)
    if user is None:
        logger.error("ユーザーが見つかりません: %s", user_id)
        return None

    if user.wallet_address:
        logger.warning(
            "ユーザー %s は既にウォレットを連携済みです", user_id
        )
        return None

    api_key = current_app.config.get("XAMAN_API_KEY", "")
    api_secret = current_app.config.get("XAMAN_API_SECRET", "")

    if not api_key or not api_secret:
        logger.error("Xaman API設定が不足しています")
        return None

    # SignInペイロード作成
    try:
        response = requests.post(
            XAMAN_PAYLOAD_URL,
            headers=_get_xaman_headers(),
            json={
                "txjson": {"TransactionType": "SignIn"},
                "options": {
                    "submit": False,
                },
            },
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error("Xaman APIへの接続エラー: %s", str(e))
        return None

    if response.status_code != 200:
        logger.warning(
            "Xamanペイロード作成失敗: status=%d", response.status_code
        )
        return None

    payload_data = response.json()

    return {
        "payload_uuid": payload_data.get("uuid"),
        "next_url": payload_data.get("next", {}).get("always"),
        "qr_url": payload_data.get("refs", {}).get("qr_png"),
    }


def complete_wallet_link(user_id: str, payload_uuid: str) -> bool:
    """
    Xaman署名完了後のコールバック処理を行う。

    ペイロードの署名結果を取得し、署名が完了していれば
    ウォレットアドレスをユーザーに紐付ける。

    Args:
        user_id: ウォレットを連携するユーザーのID
        payload_uuid: Xamanペイロードの UUID

    Returns:
        bool: ウォレット連携が成功した場合True
    """
    user = User.query.get(user_id)
    if user is None:
        logger.error("ユーザーが見つかりません: %s", user_id)
        return False

    # ペイロード結果取得
    try:
        result_url = f"{XAMAN_PAYLOAD_URL}/{payload_uuid}"
        response = requests.get(
            result_url,
            headers=_get_xaman_headers(),
            timeout=30,
        )
    except requests.RequestException as e:
        logger.error("Xamanペイロード結果取得エラー: %s", str(e))
        return False

    if response.status_code != 200:
        logger.warning(
            "Xamanペイロード結果取得失敗: status=%d", response.status_code
        )
        return False

    payload_result = response.json()

    # 署名検証
    meta = payload_result.get("meta", {})
    if not meta.get("signed"):
        logger.info(
            "ペイロード %s はまだ署名されていません", payload_uuid
        )
        return False

    # ウォレットアドレス取得
    wallet_address = payload_result.get("response", {}).get("account")
    if not wallet_address:
        logger.error("ウォレットアドレスが取得できませんでした")
        return False

    # ユーザーにウォレットアドレスを紐付け
    user.wallet_address = wallet_address
    db.session.commit()

    logger.info(
        "ユーザー %s にウォレット %s を連携しました",
        user_id,
        wallet_address,
    )
    return True
