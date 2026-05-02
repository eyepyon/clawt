# タスク: AIエージェント・ニュースメディアプラットフォーム

## タスク1: プロジェクト基盤セットアップ
- [x] 1.1 Flaskアプリケーションの初期構成を作成する（app.py、config.py、__init__.py）
- [x] 1.2 requirements.txtに全依存パッケージを定義する（Flask, Flask-SQLAlchemy, Flask-Migrate, Flask-Login, Flask-Limiter, Flask-WTF, Flask-Babel, openclaw-sdk, xrpl-py, PyJWT, requests, celery, redis, hypothesis, pytest, bleach, python-slugify）
- [x] 1.3 SQLAlchemyデータベース設定とFlask-Migrateの初期化を行う
- [x] 1.4 Flask-Babelによる日本語ローカライゼーション設定を行う
- [x] 1.5 環境変数管理（.env.example）を作成し、APIキー・シークレットのテンプレートを定義する
- [x] 1.6 プロジェクトディレクトリ構造を作成する（app/, app/models/, app/routes/, app/services/, app/templates/, app/static/, tests/）

## タスク2: データモデル実装
- [x] 2.1 Userモデルを実装する（id, username, display_name, user_type, wallet_address, world_id_nullifier, specialty, reputation_score, total_articles, total_rewards_xrp, total_penalties_xrp, is_active, is_verified, language, created_at, updated_at）
- [x] 2.2 Articleモデルを実装する（id, title, content, summary, slug, author_id, category, tags, source_urls, view_count, like_count, report_count, status, language, reward_distributed, created_at, published_at）
- [x] 2.3 RewardTransactionモデルを実装する（id, user_id, article_id, tx_type, amount_xrp, xrpl_tx_hash, status, reason, created_at, confirmed_at）
- [x] 2.4 Reportモデルを実装する（id, article_id, reporter_id, reason, description, evidence_urls, status, reviewer_id, resolution, created_at, reviewed_at）
- [x] 2.5 各モデルのバリデーションルールを実装する（username形式、wallet_address形式、reputation_score範囲、記事ステータス遷移）
- [x] 2.6 初期マイグレーションを作成・実行する

## タスク3: 認証・認可モジュール実装
- [x] 3.1 World ID OIDC認証フローを実装する（認可コード交換、IDトークン検証、nullifier_hash取得、重複チェック）
- [x] 3.2 Xaman Wallet連携を実装する（SignInペイロード作成、QRコード生成、署名検証コールバック、ウォレットアドレス取得）
- [x] 3.3 JWT発行・検証ミドルウェアを実装する（PyJWT使用、トークン有効期限管理）
- [x] 3.4 ユーザー登録APIを実装する（POST /api/register - human, ai_agent, external_agent対応）
- [x] 3.5 ログインAPIを実装する（POST /api/login - World ID / APIキー対応）
- [x] 3.6 認証レート制限を実装する（Flask-Limiter、5回/時間）

## タスク4: エージェント管理モジュール実装
- [-] 4.1 OpenClaw SDKを使用したエージェント作成機能を実装する（create_reporter_agent関数）
- [~] 4.2 エージェント一覧取得・ステータス確認APIを実装する（GET /api/agents, GET /api/agents/<id>）
- [~] 4.3 エージェントタスク割り当て・追跡機能を実装する（トレンド検索、記事作成、ソース検索）
- [~] 4.4 エージェント評判スコア管理を実装する（初期値100.0、減少ロジック、自動無効化）
- [~] 4.5 エージェント無効化機能を実装する（評判スコア0以下で自動無効化、手動無効化）
- [~] 4.6 OpenClaw MCPサーバー連携設定を行う（freema/openclaw-mcp）

## タスク5: 記事管理モジュール実装
- [~] 5.1 記事自動生成ワークフローを実装する（auto_generate_article関数 - トレンド検索→ソース収集→記事生成→関連記事リンク）
- [~] 5.2 記事CRUD APIを実装する（POST /api/articles, GET /api/articles/<id>, PUT /api/articles/<id>, DELETE /api/articles/<id>）
- [~] 5.3 記事公開ワークフローを実装する（draft→published ステータス遷移、published_at設定）
- [~] 5.4 記事検索・フィルタリングAPIを実装する（GET /api/articles?q=&category=&page=&per_page=）
- [~] 5.5 人気記事ランキングAPIを実装する（GET /api/articles/popular?period=daily|weekly|monthly）
- [~] 5.6 記事閲覧数カウント機能を実装する（Redisインメモリカウンター + 定期DB同期）
- [~] 5.7 関連記事リンク機能を実装する（同カテゴリの最新記事を自動リンク）
- [~] 5.8 記事スラグ生成機能を実装する（python-slugifyによる日本語タイトルからのURL生成）

## タスク6: 報酬システム実装
- [~] 6.1 報酬計算ロジックを実装する（閲覧数×基本報酬 + いいね数×倍率 + バイラルボーナス）
- [~] 6.2 XRPL送金機能を実装する（xrpl-pyによるPaymentトランザクション、send_xrp_payment関数）
- [~] 6.3 日次報酬配布バッチを実装する（calculate_and_distribute_rewards関数、Celeryタスク）
- [~] 6.4 報酬トランザクション記録機能を実装する（XRPLハッシュ、金額、ステータスのDB保存）
- [~] 6.5 エージェント報酬残高・履歴取得APIを実装する（GET /api/rewards/<user_id>, GET /api/rewards/<user_id>/history）
- [~] 6.6 プラットフォームウォレット残高チェック機能を実装する（残高不足時の配布停止）
- [~] 6.7 XRPL MCP サーバー連携設定を行う（tamago-labs/xrpl-mcp）

## タスク7: 罰金・通報システム実装
- [~] 7.1 通報フォーム・提出APIを実装する（POST /api/reports - reason, description, evidence_urls）
- [~] 7.2 通報一覧・審査APIを実装する（GET /api/reports?status=pending, PUT /api/reports/<id>/review）
- [~] 7.3 自動フラグ機能を実装する（通報数閾値超過時の記事自動フラグ）
- [~] 7.4 フェイクニュース罰金処理を実装する（process_fake_news_report関数 - 累進罰金計算、XRPL送金、評判スコア減少）
- [~] 7.5 通報レート制限を実装する（1ユーザー10件/時間）
- [~] 7.6 削除記事への報酬配布禁止ロジックを実装する

## タスク8: Webインターフェース実装
- [~] 8.1 ベーステンプレート（base.html）と日本語UIレイアウトを作成する
- [~] 8.2 トップページを実装する（人気記事ランキング、新着記事、カテゴリ別記事）
- [~] 8.3 記事詳細ページを実装する（本文、著者情報、ソースリンク、関連記事、いいね/通報ボタン）
- [~] 8.4 ユーザーダッシュボードを実装する（投稿記事一覧、報酬履歴、評判スコア）
- [~] 8.5 管理者ダッシュボードを実装する（通報一覧、エージェント管理、報酬配布状況）
- [~] 8.6 通報フォームUIを実装する（理由選択、説明入力、証拠URL入力）
- [~] 8.7 ユーザー登録・ログインページを実装する（World ID連携、Xaman QRコード表示）
- [~] 8.8 XSS対策（bleach）とCSRF保護（Flask-WTF）を全テンプレートに適用する

## タスク9: セキュリティ・パフォーマンス・インフラ
- [~] 9.1 Flask-Limiterによる全APIエンドポイントのレート制限設定を行う
- [~] 9.2 Redis接続設定とキャッシュ戦略を実装する（人気記事ランキング、エージェントプロファイル、TTL: 5分）
- [~] 9.3 Celeryワーカー設定と非同期タスク定義を行う（報酬配布バッチ、記事生成、閲覧数同期）
- [~] 9.4 XRPL接続リトライ機構を実装する（指数バックオフ、最大3回、フォールバックノード）
- [~] 9.5 エラーハンドリングとログ設定を実装する（構造化ログ、エラー通知）
- [~] 9.6 権限管理を実装する（AIエージェント: 記事作成のみ、人間管理者: 全操作）

## タスク10: テスト
- [~] 10.1 pytest設定とテストフィクスチャを作成する（Flask テストクライアント、テストDB）
- [~] 10.2 報酬計算ロジックのユニットテストを作成する
- [~] 10.3 罰金計算ロジック（累進性）のユニットテストを作成する
- [~] 10.4 記事ステータス遷移のユニットテストを作成する
- [~] 10.5 hypothesisによるプロパティベーステストを作成する（報酬非負性、罰金累進性、評判スコア範囲）
- [~] 10.6 Flask APIエンドポイントの統合テストを作成する
- [~] 10.7 外部サービス連携のモックテストを作成する（OpenClaw、XRPL、World ID、Xaman）
