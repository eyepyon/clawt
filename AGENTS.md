# AI Agent News Media Platform — Agent Instructions

This file provides instructions for AI coding agents (Claude Code, OpenAI Codex, Gemini CLI, etc.) working on this codebase.

---

## Project Overview

A decentralized AI-powered Japanese news media platform where:
- **Reporter Agents** (OpenClaw-based) auto-generate news articles in Japanese
- **Reward System**: Popular articles earn XRP rewards via XRPL blockchain
- **Penalty System**: Fake news results in progressive XRP fines
- **Reporting System**: Users can report fake/misleading articles
- **Identity**: Worldcoin World ID for human verification
- **Wallet**: Xaman Wallet for XRPL transactions
- **Payments**: x402-xrpl for agent-to-API micropayments

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| Web Framework | Flask 3.x |
| ORM | Flask-SQLAlchemy + Flask-Migrate |
| Auth | PyJWT + Flask-Login + Flask-WTF (CSRF) |
| Rate Limiting | Flask-Limiter |
| i18n | Flask-Babel (default locale: `ja`) |
| AI Agents | openclaw-sdk |
| Blockchain | xrpl-py (XRPL / XRP Ledger) |
| Agent Payments | x402-xrpl (HTTP 402 auto-pay) |
| Wallet Auth | Xaman API (xumm.app) |
| Human Auth | Worldcoin World ID (OIDC) |
| Task Queue | Celery + Redis |
| Cache | Redis |
| Testing | pytest + hypothesis (property-based) |

---

## Project Structure

```
.
├── app.py                    # Entry point: imports create_app(), runs on port 5000
├── config.py                 # Config classes: DevelopmentConfig, TestingConfig, ProductionConfig
├── requirements.txt          # Pinned dependencies
├── .env.example              # Environment variable template (never commit .env)
├── babel.cfg                 # Flask-Babel extraction config
├── app/
│   ├── __init__.py           # create_app() factory, extension init, blueprint registration
│   ├── models/
│   │   ├── __init__.py       # Re-exports all models and constants
│   │   ├── user.py           # User model (human / ai_agent / external_agent)
│   │   ├── article.py        # Article model with status transitions
│   │   ├── reward_transaction.py  # XRPL reward/penalty transaction records
│   │   └── report.py         # Fake news report model
│   ├── routes/
│   │   ├── auth.py           # Blueprint: auth_bp — /auth/api/register, /auth/api/login
│   │   └── agents.py         # Blueprint: agents_bp — /agents/api/agents
│   ├── services/
│   │   ├── jwt_auth.py       # generate_token(), verify_token(), @jwt_required
│   │   ├── world_id.py       # authenticate_with_world_id() — Worldcoin OIDC
│   │   ├── xaman.py          # link_xaman_wallet(), complete_wallet_link()
│   │   ├── agent_manager.py  # create_reporter_agent(), assign_task(), update_reputation()
│   │   └── x402_payment.py   # create_x402_session(), make_paid_request()
│   ├── templates/            # Jinja2 HTML templates (Japanese UI)
│   ├── static/               # CSS, JS, images
│   └── translations/         # Flask-Babel translation files
└── tests/
    ├── test_models.py        # Unit tests for all models + validation
    └── test_auth.py          # Unit tests for auth flows + API endpoints
```

---

## Key Conventions

### Flask Application Factory
Always use `create_app(config_name)` — never instantiate Flask directly.
```python
from app import create_app
app = create_app("development")  # or "testing", "production"
```

### Database Models
- All primary keys are UUID strings (`str(uuid.uuid4())`)
- Use `@validates` decorator for field validation (raises `ValueError` on invalid input)
- All models have `to_dict()` for JSON serialization
- JSON array fields (`tags`, `source_urls`, `evidence_urls`) stored as TEXT, use helper methods:
  ```python
  article.set_tags_list(["AI", "Tech"])
  article.get_tags_list()  # → ["AI", "Tech"]
  ```

### Authentication
- JWT Bearer tokens required for all protected endpoints
- Decorator: `@jwt_required` (sets `request.current_user_id`)
- Human users: Worldcoin World ID OIDC flow
- AI/External agents: API key or JWT

### CSRF
- All API blueprints are CSRF-exempt: `csrf.exempt(blueprint)`
- HTML form routes must include CSRF tokens

### Rate Limiting
- Auth endpoints: `@limiter.limit("5/hour")`
- Report submission: `@limiter.limit("10/hour")`
- Apply via `@limiter.limit(...)` decorator

### Error Responses
All errors return JSON with Japanese messages:
```json
{"error": "エラーメッセージ"}
```

### x402 Agent Payments
Agents pay for external APIs automatically via XRPL:
```python
from app.services.x402_payment import create_agent_x402_session
session = create_agent_x402_session(agent.wallet_seed)
response = session.get("https://paid-api.example.com/data")
# 402 responses are handled automatically
```

---

## Data Models Reference

### User
```
id (UUID), username (3-100 chars, alphanumeric+underscore),
display_name, user_type (human|ai_agent|external_agent),
wallet_address (XRPL: starts with 'r', 25-35 chars),
wallet_seed (for x402 payments), world_id_nullifier (unique),
specialty, reputation_score (0.0-1000.0, default 100.0),
total_articles, total_rewards_xrp, total_penalties_xrp,
is_active, is_verified, is_admin, api_key, language (default "ja")
```

### Article
```
id (UUID), title (1-500 chars), content (min 100 chars),
summary, slug (URL-safe), author_id (FK→users),
category (政治|経済|テクノロジー|科学|スポーツ|エンタメ|国際|社会|文化|健康),
tags (JSON), source_urls (JSON, min 1),
view_count, like_count, report_count,
status (draft→published→flagged→removed), language (default "ja"),
reward_distributed, created_at, published_at
```

### RewardTransaction
```
id (UUID), user_id (FK→users), article_id (FK→articles),
tx_type (reward|penalty), amount_xrp (≥0),
xrpl_tx_hash, status (pending|submitted|confirmed|failed),
reason, created_at, confirmed_at
```

### Report
```
id (UUID), article_id (FK→articles), reporter_id (FK→users),
reason (fake_news|misleading|spam|hate_speech|other),
description (non-empty), evidence_urls (JSON),
status (pending|reviewing|confirmed|dismissed),
reviewer_id (FK→users), resolution, created_at, reviewed_at
```

---

## API Endpoints

### Auth (`/auth`)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/api/register` | Register user (human/ai_agent/external_agent) |
| POST | `/auth/api/login` | Login via World ID or API key |

### Agents (`/agents`)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/agents/api/agents` | List agents (`?active_only=true`) |
| GET | `/agents/api/agents/<id>` | Get agent details + tasks |
| POST | `/agents/api/agents` | Create new reporter agent |
| POST | `/agents/api/agents/<id>/tasks` | Assign task to agent |
| GET | `/agents/api/agents/tasks/<task_id>` | Get task status |
| PUT | `/agents/api/agents/<id>/deactivate` | Deactivate agent (admin only) |

### Planned Endpoints (not yet implemented)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/articles` | Create article |
| GET | `/api/articles/<id>` | Get article |
| GET | `/api/articles/popular` | Popular articles ranking |
| POST | `/api/reports` | Submit fake news report |
| GET | `/api/rewards/<user_id>` | Get reward balance |

---

## Business Logic

### Reward Calculation
```
reward = (view_count × 0.001) + (like_count × 0.001 × 5.0) + viral_bonus
viral_bonus = 10.0 XRP if view_count >= 10,000 else 0.0
```

### Penalty Calculation (progressive)
```
penalty = 100.0 × (2.0 ^ past_penalty_count)
reputation_score -= 30.0  (clamped to 0.0)
if reputation_score <= 0: user.is_active = False
```

### Article Status Transitions
```
draft → published
published → flagged | removed
flagged → removed | published (if report dismissed)
removed → (terminal state)
```

### Agent Reputation
- Initial: 100.0
- Range: 0.0 – 1000.0
- Auto-deactivated when score ≤ 0

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# Required for production
SECRET_KEY=
JWT_SECRET_KEY=
DATABASE_URL=postgresql://...
OPENCLAW_API_KEY=
XAMAN_API_KEY=
XAMAN_API_SECRET=
WORLD_ID_CLIENT_ID=
WORLD_ID_CLIENT_SECRET=
PLATFORM_WALLET_ADDRESS=
PLATFORM_WALLET_SECRET=
XRPL_FACILITATOR_URL=https://xrpl-facilitator-testnet.t54.ai

# Optional (have defaults)
FLASK_ENV=development
REDIS_URL=redis://localhost:6379/0
XRPL_NODE_URL=https://s.altnet.rippletest.net:51234
```

---

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app tests/

# Specific test file
pytest tests/test_models.py -v
pytest tests/test_auth.py -v
```

Tests use `config_name="testing"` which:
- Uses SQLite in-memory DB
- Disables CSRF
- Disables rate limiting

---

## Remaining Work (Tasks 4–10)

The following modules still need implementation:

- **Task 4**: Agent management routes (partially done in `app/routes/agents.py`)
- **Task 5**: Article CRUD, auto-generation, search, ranking, slug generation
- **Task 6**: XRPL reward distribution, batch processing, balance checks
- **Task 7**: Report submission/review, auto-flagging, penalty processing
- **Task 8**: HTML templates (Japanese UI), dashboard pages
- **Task 9**: Redis caching, Celery workers, XRPL retry logic
- **Task 10**: Full test suite with hypothesis property-based tests

See `tasks.md` in `.kiro/specs/ai-agent-news-media/` for detailed task breakdown.
