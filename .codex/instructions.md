# Codex Instructions — AI Agent News Media Platform

Instructions for OpenAI Codex and OpenAI Agents SDK working on this project.

---

## What This Project Is

A Japanese-language AI news media platform built with Python/Flask. AI reporter agents (OpenClaw) automatically generate news articles. Articles earn XRP cryptocurrency rewards based on popularity. Fake news triggers progressive XRP penalties. Humans authenticate via Worldcoin World ID. Wallets connect via Xaman (XRPL).

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Fill in API keys in .env
python app.py          # starts on http://localhost:5000
pytest --tb=short      # run tests
```

---

## Stack

- **Python 3.10+**, **Flask 3.x**
- **SQLAlchemy** ORM, **Flask-Migrate** for migrations
- **PyJWT** for auth tokens, **Flask-Limiter** for rate limiting
- **Flask-Babel** for i18n (default locale: `ja`)
- **openclaw-sdk** — AI agent framework
- **xrpl-py** — XRP Ledger blockchain
- **x402-xrpl** — HTTP 402 auto-payment for agents
- **Xaman API** — wallet signing (xumm.app)
- **Worldcoin World ID** — human identity (OIDC)
- **Celery + Redis** — async tasks and caching
- **pytest + hypothesis** — testing

---

## Project Layout

```
app/__init__.py           ← create_app() factory
app/models/
  user.py                 ← User (human|ai_agent|external_agent)
  article.py              ← Article with status machine
  reward_transaction.py   ← XRPL tx records
  report.py               ← Fake news reports
app/routes/
  auth.py                 ← /auth/api/register, /auth/api/login
  agents.py               ← /agents/api/agents
app/services/
  jwt_auth.py             ← JWT tokens + @jwt_required decorator
  world_id.py             ← Worldcoin OIDC auth
  xaman.py                ← Xaman wallet linking
  agent_manager.py        ← OpenClaw agent lifecycle
  x402_payment.py         ← x402-xrpl payment sessions
tests/
  test_models.py
  test_auth.py
config.py                 ← DevelopmentConfig / TestingConfig / ProductionConfig
.env.example              ← env var template
```

---

## Rules to Follow

### Always
- Use `create_app("testing")` in test fixtures, never `create_app()` without args
- Use `@jwt_required` on all protected API routes
- Apply `csrf.exempt(blueprint)` to all API blueprints
- Return `jsonify({"error": "日本語メッセージ"}), status_code` for errors
- Use `current_app.config.get(...)` inside services (not module-level globals)
- Set `timeout=30` on all external HTTP requests
- Validate XRPL addresses: starts with `r`, length 25–35

### Never
- Never expose `wallet_seed` in API responses or `to_dict()`
- Never commit `.env` (only `.env.example`)
- Never skip `article.validate_status_transition()` before changing article status
- Never distribute rewards to articles with `status == "removed"`
- Never use `Flask(__name__)` directly — always use `create_app()`

---

## Key Patterns

### Adding a new Blueprint
```python
# app/routes/my_feature.py
from flask import Blueprint
from app import csrf
my_bp = Blueprint("my_feature", __name__)
csrf.exempt(my_bp)

# app/__init__.py — add to blueprint_configs:
("app.routes.my_feature", "my_bp", "/my-feature"),
```

### Protected endpoint
```python
from app.services.jwt_auth import jwt_required

@my_bp.route("/api/resource", methods=["GET"])
@jwt_required
def get_resource():
    user_id = request.current_user_id  # set by @jwt_required
    ...
```

### Admin-only endpoint
```python
current_user = User.query.get(request.current_user_id)
if not current_user or not current_user.is_admin:
    return jsonify({"error": "管理者権限が必要です"}), 403
```

### Agent x402 payment
```python
from app.services.x402_payment import create_agent_x402_session
session = create_agent_x402_session(agent.wallet_seed)
response = session.get("https://paid-news-api.example.com/data")
# 402 Payment Required is handled automatically via XRPL
```

### Test fixture pattern
```python
import pytest
from app import create_app, db

@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()
```

### Mocking external services
```python
from unittest.mock import patch, MagicMock

@patch("app.services.world_id.requests.post")
def test_something(mock_post, app):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"id_token": "test"})
    )
    ...
```

---

## Business Logic

### Reward formula
```python
reward = view_count * 0.001 + like_count * 0.005
if view_count >= 10000:
    reward += 10.0  # viral bonus
```

### Penalty formula (progressive)
```python
past_count = RewardTransaction.query.filter_by(
    user_id=author.id, tx_type="penalty"
).count()
penalty = 100.0 * (2.0 ** past_count)
author.reputation_score = max(0.0, author.reputation_score - 30.0)
if author.reputation_score <= 0.0:
    author.is_active = False
```

### Article status machine
```
draft ──→ published ──→ flagged ──→ removed
                   └──────────────→ removed
flagged ──→ published  (if report dismissed)
removed  (terminal — no further transitions)
```

---

## What Still Needs to Be Built

### Articles (Task 5)
- `app/routes/articles.py` — CRUD + search + popular ranking
- `app/services/article_service.py` — auto-generation, slug, related linking, view sync

### Rewards (Task 6)
- `app/routes/rewards.py` — balance + history endpoints
- `app/services/reward_service.py` — calculation, XRPL payment, batch distribution

### Reports & Penalties (Task 7)
- `app/routes/reports.py` — submit + review endpoints
- `app/services/report_service.py` — auto-flag, penalty processing

### Web UI (Task 8)
- `app/routes/main.py` — HTML page routes
- `app/templates/` — Jinja2 templates (Bootstrap 5, Japanese)

### Infrastructure (Task 9)
- `app/services/celery_app.py` — async task queue
- `app/services/redis_cache.py` — caching layer (TTL 5 min)
- `app/services/xrpl_client.py` — XRPL client with retry + fallback

### Tests (Task 10)
- `tests/test_articles.py`
- `tests/test_rewards.py`
- `tests/test_reports.py`
- `tests/test_property.py` — hypothesis property-based tests

---

## Environment Variables (required)

```bash
SECRET_KEY=
JWT_SECRET_KEY=
DATABASE_URL=postgresql://user:pass@localhost/dbname
OPENCLAW_API_KEY=
XAMAN_API_KEY=
XAMAN_API_SECRET=
WORLD_ID_CLIENT_ID=
WORLD_ID_CLIENT_SECRET=
PLATFORM_WALLET_ADDRESS=
PLATFORM_WALLET_SECRET=
XRPL_FACILITATOR_URL=https://xrpl-facilitator-testnet.t54.ai
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
```
