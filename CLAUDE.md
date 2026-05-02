# CLAUDE.md — Claude Code Instructions

This file is automatically read by Claude Code. It contains project-specific instructions for working on the AI Agent News Media Platform.

---

## Project Summary

Japanese AI-powered news media platform. Reporter agents (OpenClaw) auto-generate articles. Popular articles earn XRP rewards via XRPL. Fake news triggers progressive XRP penalties. Human identity verified via Worldcoin World ID. Wallets managed via Xaman.

**Language**: Python 3.10+ / Flask 3.x  
**DB**: SQLAlchemy (SQLite dev, PostgreSQL prod)  
**Locale**: Japanese (`ja`) as default throughout

---

## Build & Run

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your API keys

# Run development server (do NOT use flask run in watch mode during tasks)
python app.py

# Run tests (always use --tb=short for readable output)
pytest --tb=short

# Run with coverage
pytest --cov=app --tb=short tests/
```

---

## Architecture

### Application Factory
`create_app(config_name)` in `app/__init__.py` — always use this, never `Flask(__name__)` directly.

Config names: `"development"` (SQLite), `"testing"` (SQLite, CSRF off, rate limits off), `"production"` (PostgreSQL).

### Blueprint Registration
Blueprints are registered with try/except in `_register_blueprints()`. New blueprints go in `app/routes/` and must be added to `blueprint_configs` list in `app/__init__.py`.

### Extensions (imported from `app`)
```python
from app import db, migrate, login_manager, limiter, csrf, babel
```

---

## Code Conventions

### Models
- UUID string PKs: `default=lambda: str(uuid.uuid4())`
- Validation via `@validates` decorator — raises `ValueError` with Japanese message
- Always implement `to_dict()` — never expose `wallet_seed` in `to_dict()`
- JSON array fields use helper methods: `get_*_list()` / `set_*_list()`

### Routes / Blueprints
- All API blueprints: `csrf.exempt(blueprint_name)`
- Protected endpoints: `@jwt_required` decorator (sets `request.current_user_id`)
- Rate limits: `@limiter.limit("N/period")` on individual routes
- Error responses always JSON: `jsonify({"error": "日本語メッセージ"}), status_code`

### Services
- No Flask globals in service functions unless inside app context
- Use `current_app.config.get(...)` for config access inside services
- External HTTP calls: always set `timeout=30`
- Log with `logger = logging.getLogger(__name__)`

### x402 Payments
Agents use `wallet_seed` (stored in DB) to auto-pay for external APIs:
```python
from app.services.x402_payment import create_agent_x402_session
session = create_agent_x402_session(agent.wallet_seed)
response = session.get("https://paid-api.example.com/endpoint")
```

---

## Testing

Tests live in `tests/`. Use `create_app("testing")` fixture.

```python
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

- Mock all external services (OpenClaw, XRPL, World ID, Xaman) with `unittest.mock.patch`
- Property-based tests use `hypothesis`: `@given(st.integers(...))` etc.
- All test error messages should match Japanese strings in the actual code

---

## Important Constraints

1. **Never commit `.env`** — only `.env.example`
2. **Never expose `wallet_seed`** in API responses or logs
3. **All user-facing strings in Japanese** — error messages, UI text, log messages
4. **Status transitions are strict** — use `article.validate_status_transition(new_status)` before changing
5. **Reputation score clamped** — always `max(0.0, min(1000.0, score))`
6. **Removed articles get no rewards** — check `article.status != "removed"` before distributing
7. **XRPL addresses** start with `r`, 25–35 chars — validated in `User.validate_wallet_address()`

---

## Remaining Tasks (implement in order)

### Task 4 — Agent Management (partially done)
- `app/services/agent_manager.py` ✅ exists
- `app/routes/agents.py` ✅ exists
- Still needed: OpenClaw MCP server config (`freema/openclaw-mcp`)

### Task 5 — Article Management
Create `app/routes/articles.py` (blueprint: `articles_bp`, prefix `/articles`):
- `POST /articles/api/articles` — create article (auth required)
- `GET /articles/api/articles/<id>` — get article (increments view count via Redis)
- `PUT /articles/api/articles/<id>` — update article
- `DELETE /articles/api/articles/<id>` — soft delete (set status=removed)
- `GET /articles/api/articles` — search (`?q=&category=&page=&per_page=`)
- `GET /articles/api/articles/popular` — ranking (`?period=daily|weekly|monthly`)
- `POST /articles/api/articles/<id>/like` — increment like count

Create `app/services/article_service.py`:
- `auto_generate_article(agent_id, category)` — OpenClaw web_search → article_writer
- `generate_slug(title)` — use `python-slugify` with Japanese support
- `link_related_articles(article_id)` — same category, published, limit 5
- `sync_view_counts()` — flush Redis counters to DB (Celery task)

### Task 6 — Reward System
Create `app/services/reward_service.py`:
- `calculate_reward(article)` → float
  - `view_count × 0.001 + like_count × 0.005 + (10.0 if view_count >= 10000 else 0.0)`
- `send_xrp_payment(from_wallet, to_address, amount)` → tx_hash (use xrpl-py)
- `calculate_and_distribute_rewards(period="daily")` → list[RewardTransaction]
  - Check platform balance before each payment
  - Skip articles with `status == "removed"`
- `get_xrpl_balance(address)` → float

Create `app/routes/rewards.py` (blueprint: `rewards_bp`, prefix `/rewards`):
- `GET /rewards/api/rewards/<user_id>` — balance + stats
- `GET /rewards/api/rewards/<user_id>/history` — transaction history

### Task 7 — Report & Penalty System
Create `app/routes/reports.py` (blueprint: `reports_bp`, prefix `/reports`):
- `POST /reports/api/reports` — submit report (rate limit: 10/hour)
- `GET /reports/api/reports` — list reports (`?status=pending`, admin only)
- `PUT /reports/api/reports/<id>/review` — review report (admin only)

Create `app/services/report_service.py`:
- `submit_report(article_id, reporter_id, reason, description, evidence_urls)` → Report
  - Auto-flag article if `report_count >= 5`
- `process_fake_news_report(report_id, reviewer_id, decision, resolution)` → tuple
  - If confirmed: remove article, calculate progressive penalty, send XRPL tx, decrease reputation
  - Penalty formula: `100.0 × (2.0 ^ past_penalty_count)`
  - Reputation decrease: `-30.0` (auto-deactivate if ≤ 0)

### Task 8 — Web UI (Japanese)
Create Jinja2 templates in `app/templates/`:
- `base.html` — Bootstrap 5, Japanese meta, navbar, footer
- `index.html` — popular articles, latest articles, category filter
- `article.html` — full article, author info, source links, related articles, like/report buttons
- `dashboard.html` — user's articles, reward history, reputation score
- `admin.html` — report queue, agent management, reward distribution status
- `report_form.html` — reason dropdown, description textarea, evidence URLs
- `auth/login.html` — World ID button, API key input
- `auth/register.html` — user type selection, World ID flow, Xaman QR

Create `app/routes/main.py` (blueprint: `main_bp`, prefix `""`):
- `GET /` — index page
- `GET /articles/<slug>` — article detail
- `GET /dashboard` — user dashboard (login required)
- `GET /admin` — admin dashboard (admin required)
- `GET /report/<article_id>` — report form

### Task 9 — Infrastructure
- `app/services/celery_app.py` — Celery instance, periodic tasks
- `app/services/redis_cache.py` — cache helpers (TTL 5 min for rankings/profiles)
- `app/services/xrpl_client.py` — XRPL client with retry (exponential backoff, max 3, fallback node)

### Task 10 — Tests
Add to `tests/`:
- `test_rewards.py` — reward calculation, XRPL payment (mocked), batch distribution
- `test_reports.py` — report submission, review flow, penalty processing
- `test_articles.py` — CRUD, status transitions, slug generation, search
- `test_property.py` — hypothesis tests:
  - Reward always ≥ 0
  - Penalty increases with offense count
  - Reputation stays in [0.0, 1000.0]
  - Status transitions are valid

---

## File Checklist (what exists vs. what's needed)

| File | Status |
|------|--------|
| `app/__init__.py` | ✅ Done |
| `config.py` | ✅ Done |
| `app.py` | ✅ Done |
| `requirements.txt` | ✅ Done |
| `.env.example` | ✅ Done |
| `app/models/user.py` | ✅ Done |
| `app/models/article.py` | ✅ Done |
| `app/models/reward_transaction.py` | ✅ Done |
| `app/models/report.py` | ✅ Done |
| `app/services/jwt_auth.py` | ✅ Done |
| `app/services/world_id.py` | ✅ Done |
| `app/services/xaman.py` | ✅ Done |
| `app/services/agent_manager.py` | ✅ Done |
| `app/services/x402_payment.py` | ✅ Done |
| `app/routes/auth.py` | ✅ Done |
| `app/routes/agents.py` | ✅ Done |
| `tests/test_models.py` | ✅ Done |
| `tests/test_auth.py` | ✅ Done |
| `app/routes/articles.py` | ❌ Needed |
| `app/routes/reports.py` | ❌ Needed |
| `app/routes/rewards.py` | ❌ Needed |
| `app/routes/main.py` | ❌ Needed |
| `app/services/article_service.py` | ❌ Needed |
| `app/services/reward_service.py` | ❌ Needed |
| `app/services/report_service.py` | ❌ Needed |
| `app/services/celery_app.py` | ❌ Needed |
| `app/services/redis_cache.py` | ❌ Needed |
| `app/services/xrpl_client.py` | ❌ Needed |
| `app/templates/` | ❌ Needed |
| `tests/test_rewards.py` | ❌ Needed |
| `tests/test_reports.py` | ❌ Needed |
| `tests/test_articles.py` | ❌ Needed |
| `tests/test_property.py` | ❌ Needed |
