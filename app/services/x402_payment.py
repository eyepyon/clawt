"""
x402 Payment Protocol サービス (XRPL)

x402-xrplライブラリを使用して、エージェントがXRPLで自動支払いを行う機能を提供する。
HTTP 402 Payment Required レスポンスを自動的に処理し、
XRPL上で支払いを実行してリクエストをリトライする。

参考: https://xrpl-x402.t54.ai/docs/client-guides/python
"""

import logging
from typing import Optional

from flask import current_app

logger = logging.getLogger(__name__)


def create_x402_session(wallet_seed: str, rpc_url: Optional[str] = None):
    """
    x402対応のrequestsセッションを作成する。

    このセッションは通常のrequests.Sessionと同様に使用でき、
    HTTP 402レスポンスを受け取った場合に自動的にXRPL支払いを実行し、
    支払い証明付きでリクエストをリトライする。

    Args:
        wallet_seed: XRPLウォレットのシード（秘密鍵）
        rpc_url: XRPL RPCノードのURL（省略時はconfig値を使用）

    Returns:
        x402対応のrequestsセッション

    Raises:
        ImportError: x402-xrplパッケージがインストールされていない場合
        ValueError: wallet_seedが無効な場合
    """
    try:
        from x402_xrpl.clients import x402_requests
        from xrpl.wallet import Wallet
    except ImportError:
        logger.error(
            "x402-xrplパッケージがインストールされていません。"
            "pip install x402-xrpl を実行してください。"
        )
        raise

    if not wallet_seed:
        raise ValueError("ウォレットシードが指定されていません")

    if rpc_url is None:
        rpc_url = current_app.config.get(
            "XRPL_TESTNET_RPC_URL",
            "https://s.altnet.rippletest.net:51234/",
        )

    network_filter = current_app.config.get("XRPL_X402_NETWORK", "xrpl:1")
    scheme_filter = current_app.config.get("XRPL_X402_SCHEME", "exact")

    # ウォレットをシードから復元
    wallet = Wallet.from_seed(wallet_seed)
    logger.info(
        "x402セッション作成: ウォレット %s", wallet.classic_address
    )

    # x402対応セッションを作成
    session = x402_requests(
        wallet,
        rpc_url=rpc_url,
        network_filter=network_filter,
        scheme_filter=scheme_filter,
    )

    return session


def create_platform_x402_session(rpc_url: Optional[str] = None):
    """
    プラットフォームウォレットを使用したx402セッションを作成する。

    プラットフォームが外部の有料APIにアクセスする際に使用する。

    Args:
        rpc_url: XRPL RPCノードのURL（省略時はconfig値を使用）

    Returns:
        x402対応のrequestsセッション
    """
    platform_seed = current_app.config.get("PLATFORM_WALLET_SECRET", "")
    if not platform_seed:
        raise ValueError(
            "プラットフォームウォレットシードが設定されていません。"
            "PLATFORM_WALLET_SECRET環境変数を設定してください。"
        )

    return create_x402_session(platform_seed, rpc_url)


def create_agent_x402_session(agent_wallet_seed: str, rpc_url: Optional[str] = None):
    """
    エージェント専用のx402セッションを作成する。

    各記者エージェントが独自のウォレットで有料リソースにアクセスし、
    自動的にXRPLで支払いを行うためのセッション。

    Args:
        agent_wallet_seed: エージェントのXRPLウォレットシード
        rpc_url: XRPL RPCノードのURL（省略時はconfig値を使用）

    Returns:
        x402対応のrequestsセッション

    使用例:
        session = create_agent_x402_session(agent.wallet_seed)
        # 有料APIに自動支払いでアクセス
        response = session.get("https://paid-api.example.com/news-data")
        # 402レスポンスが返された場合、自動的にXRPLで支払い→リトライ
    """
    return create_x402_session(agent_wallet_seed, rpc_url)


def make_paid_request(
    wallet_seed: str,
    url: str,
    method: str = "GET",
    rpc_url: Optional[str] = None,
    **kwargs,
):
    """
    x402支払い対応のHTTPリクエストを実行する。

    ワンショットで有料リソースにアクセスする場合に使用する。
    セッションを再利用する場合は create_x402_session() を使用すること。

    Args:
        wallet_seed: XRPLウォレットのシード
        url: リクエスト先URL
        method: HTTPメソッド（GET, POST等）
        rpc_url: XRPL RPCノードのURL
        **kwargs: requests.request()に渡す追加引数

    Returns:
        requests.Response: HTTPレスポンス
    """
    session = create_x402_session(wallet_seed, rpc_url)

    response = session.request(method, url, **kwargs)

    logger.info(
        "x402リクエスト完了: %s %s -> status=%d",
        method,
        url,
        response.status_code,
    )

    # 支払い確認情報をログ出力
    if "PAYMENT-RESPONSE" in response.headers:
        try:
            from x402_xrpl.clients import decode_payment_response

            payment_info = decode_payment_response(
                response.headers["PAYMENT-RESPONSE"]
            )
            logger.info(
                "x402支払い完了: tx=%s",
                payment_info.get("transaction", "N/A"),
            )
        except Exception as e:
            logger.warning("支払いレスポンスのデコードに失敗: %s", str(e))

    return response
