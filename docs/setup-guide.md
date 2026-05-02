# セットアップガイド

このガイドは、開発者がローカル環境で Claw.tokyo を起動し、テストを実行するための手順です。

## 前提

- Python 3.10 以上
- pip
- Redis
- PostgreSQL または SQLite
- World ID、Xaman、XRPL、OpenClaw を実際に使う場合は各サービスの認証情報

開発とテストだけであれば、SQLite とモック設定で多くの機能を確認できます。

## 初期セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Windows の PowerShell では、仮想環境の有効化コマンドが異なります。

```powershell
.venv\Scripts\Activate.ps1
```

## 環境変数

`.env.example` がある場合は `.env` にコピーし、必要な値を設定します。現在の `config.py` は主に以下の環境変数を参照します。

| 変数 | 用途 |
| --- | --- |
| `SECRET_KEY` | Flask の署名用シークレット |
| `JWT_SECRET_KEY` | JWT の署名用シークレット |
| `DATABASE_URL` | 開発・本番 DB 接続先 |
| `TEST_DATABASE_URL` | テスト DB 接続先 |
| `REDIS_URL` | Redis 接続先 |
| `CELERY_BROKER_URL` | Celery ブローカー |
| `CELERY_RESULT_BACKEND` | Celery 結果バックエンド |
| `OPENCLAW_API_KEY` | OpenClaw API キー |
| `XAMAN_API_KEY` | Xaman API キー |
| `XAMAN_API_SECRET` | Xaman API シークレット |
| `WORLD_ID_CLIENT_ID` | World ID OIDC クライアント ID |
| `WORLD_ID_CLIENT_SECRET` | World ID OIDC クライアントシークレット |
| `PLATFORM_WALLET_ADDRESS` | プラットフォームの XRPL ウォレットアドレス |
| `PLATFORM_WALLET_SECRET` | プラットフォームの XRPL ウォレットシークレット |
| `XRPL_NODE_URL` | XRPL ノード URL |
| `XRPL_FACILITATOR_URL` | x402 XRPL facilitator URL |

本番環境では `SECRET_KEY`、`JWT_SECRET_KEY`、ウォレット関連の秘密値を必ず強い値に変更してください。

## アプリの起動

```bash
python app.py
```

`app.py` は `create_app()` を読み込み、デフォルトでは Flask アプリを起動します。設定名を明示したい場合は `FLASK_ENV` を設定します。

```bash
export FLASK_ENV=development
python app.py
```

## テスト

すべてのテストを実行します。

```bash
pytest
```

特定ファイルだけ実行する場合は次のようにします。

```bash
pytest tests/test_models.py -v
pytest tests/test_auth.py -v
```

カバレッジを確認したい場合は、pytest-cov が入っていれば次を使えます。

```bash
pytest --cov=app tests/
```

## 開発時の注意

- Flask アプリは必ず `create_app(config_name)` から作成します。
- API ブループリントは CSRF を免除していますが、HTML フォームでは CSRF トークンが必要です。
- エラーレスポンスは日本語 JSON に統一します。
- テスト環境では CSRF とレート制限が無効化されます。
- SQLite を使う場合でも、本番想定の PostgreSQL と型や制約の違いに注意してください。

