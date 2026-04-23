# Design Document — Bolna AI Enhancement

## Overview

This document describes the technical architecture for transforming the existing Gemini + Exotel/LiveKit voice agent into a production-ready platform with a modern React dashboard, AI-powered analytics, advanced file processing, multi-tenant support, and robust infrastructure — matching the capabilities of the Bolna AI platform.

The design builds directly on the existing FastAPI backend, PostgreSQL (Neon) database, MongoDB (call insights), and the React frontend skeleton already present in `voice_agent/frontend/`.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend (Vite)                    │
│  Dashboard │ Campaigns │ Analytics │ Leads │ Billing │ Settings │
└────────────────────────┬────────────────────────────────────────┘
                         │ REST + SSE (real-time events)
┌────────────────────────▼────────────────────────────────────────┐
│                    FastAPI Backend (main.py)                     │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Campaign    │  │  Analytics   │  │  Auth / Rate-Limit   │  │
│  │  Orchestrator│  │  Engine      │  │  Middleware          │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────┘  │
│         │                 │                                      │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────────────────────┐  │
│  │  OCR / File  │  │  Lead Scorer │  │  Webhook Handler     │  │
│  │  Parser      │  │  (Gemini)    │  │  (Exotel callbacks)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└──────────┬──────────────────┬──────────────────────────────────┘
           │                  │
    ┌──────▼──────┐   ┌───────▼──────┐
    │ PostgreSQL  │   │   MongoDB    │
    │ (Neon)      │   │  (Insights)  │
    │ campaigns   │   │ call_insights│
    │ contacts    │   │ lead_info    │
    │ billing     │   └──────────────┘
    │ api_keys    │
    │ tenants     │
    └─────────────┘
           │
    ┌──────▼──────────────────────────┐
    │  Voice Layer                    │
    │  Exotel WebSocket (/ws/exotel)  │
    │  LiveKit Rooms (/livekit/*)     │
    │  GeminiBridge (Live API)        │
    └─────────────────────────────────┘
```

---

## Component Design

### 1. React Frontend

**Tech stack:** React 18, Vite, TailwindCSS, Recharts, React Query, React Router v6

**Page structure:**
```
/                    → redirect to /dashboard
/dashboard           → Overview: live stats, recent campaigns, top leads
/campaigns           → Campaign list + create/manage
/campaigns/:id       → Campaign detail: leads table, per-call drill-down
/analytics           → Charts: funnel, sentiment, intent, topics
/leads               → Lead browser: filter by category, score, campaign
/leads/:id           → Lead detail: transcript, score breakdown, follow-up
/billing             → Monthly summary, tier info, per-campaign breakdown
/settings            → API keys, agent persona, webhook config
```

**Real-time updates:** Server-Sent Events (SSE) endpoint `GET /api/events/stream` pushes campaign status changes and call completions. React Query polls as fallback every 3 s.

**State management:** React Query for server state; Zustand for UI state (sidebar, filters, active campaign).

**Key components:**
- `<StatsGrid>` — animated metric cards (Total, Hot, Warm, Cold, In-Progress)
- `<CampaignTable>` — sortable/filterable table with status badges
- `<LeadScoreBar>` — 0–100 score with colour gradient
- `<SentimentBadge>` — positive/neutral/negative pill
- `<FunnelChart>` — Recharts funnel from Pending → Completed → Hot
- `<CallTimeline>` — per-lead call history with transcript preview
- `<FileUploadZone>` — drag-and-drop with progress and OCR method indicator

---

### 2. Enhanced API Layer

New and modified endpoints added to `main.py`:

```
# Auth
POST /api/auth/login              → issue session token
POST /api/auth/api-keys           → create API key for tenant
DELETE /api/auth/api-keys/:id     → revoke API key

# Campaigns (enhanced)
GET  /api/campaigns               → list all campaigns (paginated)
GET  /api/campaigns/:id           → campaign detail + stats
PUT  /api/campaigns/:id           → update name / config
POST /api/campaigns/:id/clone     → clone campaign with new name
POST /api/campaigns/:id/template  → save as template
GET  /api/campaigns/templates     → list saved templates

# Leads (enhanced)
GET  /api/leads                   → browse leads (filter: campaign, category, score)
GET  /api/leads/:id               → lead detail with full insight
PUT  /api/leads/:id/category      → manual override of lead category
GET  /api/leads/:id/history       → interaction history

# Analytics
GET  /api/analytics/overview      → aggregate stats across all campaigns
GET  /api/analytics/funnel        → conversion funnel data
GET  /api/analytics/sentiment     → sentiment distribution
GET  /api/analytics/topics        → top topics across campaigns
GET  /api/analytics/timeline      → calls-per-day time series

# SSE
GET  /api/events/stream           → SSE stream for live updates

# Settings
GET  /api/settings                → current agent persona + config
PUT  /api/settings                → update persona, language, product name
```

**Authentication middleware** (`auth_middleware.py`):
- Reads `X-API-Key` header or `Authorization: Bearer <token>`
- Looks up key in `api_keys` PostgreSQL table
- Attaches `tenant_id` to request state
- Skips auth for `/health`, `/exoml`, `/ws/*`, `/call-status`

**Rate limiting** (`rate_limiter.py`):
- Uses in-memory sliding window per `tenant_id`
- Default: 100 req/min per tenant, 10 req/min for upload endpoints
- Returns `HTTP 429` with `Retry-After` header on breach

---

### 3. Database Schema Additions

New tables added via migration in `pg_db.py`:

```sql
-- Multi-tenant accounts
CREATE TABLE tenants (
    tenant_id   VARCHAR(255) PRIMARY KEY,
    name        VARCHAR(500) NOT NULL,
    plan        VARCHAR(50)  NOT NULL DEFAULT 'starter',
    parent_id   VARCHAR(255) REFERENCES tenants(tenant_id),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- API keys per tenant
CREATE TABLE api_keys (
    key_id      VARCHAR(255) PRIMARY KEY,
    tenant_id   VARCHAR(255) NOT NULL REFERENCES tenants(tenant_id),
    key_hash    VARCHAR(255) NOT NULL UNIQUE,  -- SHA-256 of raw key
    name        VARCHAR(255),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_used   TIMESTAMPTZ,
    revoked     BOOLEAN      NOT NULL DEFAULT FALSE
);

-- Campaign templates
CREATE TABLE campaign_templates (
    template_id     VARCHAR(255) PRIMARY KEY,
    tenant_id       VARCHAR(255) NOT NULL,
    name            VARCHAR(500) NOT NULL,
    concurrency_limit INTEGER,
    inter_call_delay_ms INTEGER,
    script_config   JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Lead interaction history
CREATE TABLE lead_interactions (
    id          SERIAL PRIMARY KEY,
    lead_id     VARCHAR(255) NOT NULL,
    tenant_id   VARCHAR(255) NOT NULL,
    type        VARCHAR(50)  NOT NULL,  -- 'call', 'note', 'email'
    summary     TEXT,
    metadata    JSONB DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Follow-up tasks
CREATE TABLE follow_ups (
    id              SERIAL PRIMARY KEY,
    lead_id         VARCHAR(255) NOT NULL,
    campaign_id     VARCHAR(255),
    tenant_id       VARCHAR(255) NOT NULL,
    scheduled_at    TIMESTAMPTZ NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Indexes added to existing tables:**
```sql
CREATE INDEX idx_contacts_score ON contacts((extra->>'lead_score')::int DESC);
CREATE INDEX idx_contacts_updated ON contacts(updated_at DESC);
CREATE INDEX idx_billing_month_tenant ON billing(tenant_id, month);
```

**Existing `client_id` columns** are aliased to `tenant_id` in the new layer — no data migration needed, just a config rename.

---

### 4. AI Analytics Engine

The existing `insights_analyzer.py` + `classifier.py` pipeline is extended:

**`insights_analyzer.py` enhancements:**
- Structured Gemini prompt returns JSON with all scoring fields
- Adds `follow_up_recommended_at` (ISO timestamp) based on intent level
- Adds `objection_categories` list (price, timing, authority, need)
- Adds `talk_ratio` (agent vs. prospect speaking time estimate)

**Lead scoring algorithm** (implemented in `lead_scorer.py`):

```python
def score_lead(insights: dict, duration: float, status: str) -> int:
    score = 0
    if status == "Completed":           score += 20
    score += min(15, int(duration / 20))          # up to 15 pts for 5-min call
    sentiment = insights.get("sentiment", {}).get("overall", "")
    if sentiment == "positive":         score += 20
    elif sentiment == "neutral":        score += 10
    intent = insights.get("buying_intent", {}).get("level", "")
    if intent == "high":                score += 25
    elif intent == "medium":            score += 15
    score += min(10, insights.get("interest_level", 0) * 2)
    if insights.get("extracted", {}).get("decision_maker"): score += 10
    if insights.get("extracted", {}).get("budget"):         score += 10
    if insights.get("follow_up_required"):                  score += 15
    score += min(10, insights.get("engagement_score", 0))
    return min(100, score)
```

**Lead categories from score:**
| Score | Category |
|-------|----------|
| 80–100 | Hot |
| 60–79  | Warm |
| 30–59  | Cold |
| 0–29   | Not_Interested |

---

### 5. File Processing and OCR

The existing `ocr_parser.py` is refactored into a proper pipeline:

**`file_processor.py`** (new module):
```
UploadedFile
    │
    ▼
FileTypeDetector  →  csv / pdf-text / pdf-scan / image
    │
    ├── CSV         → CSVParser (existing csv_parser.py)
    ├── PDF (text)  → pdfplumber text extraction
    ├── PDF (scan)  → Tesseract OCR via pytesseract
    └── Image       → Tesseract OCR via pytesseract
    │
    ▼
ContactExtractor
    │  regex: phone, email
    │  NLP:   name, company (spaCy NER or simple heuristics)
    ▼
ContactNormalizer
    │  E.164 phone normalisation (phonenumbers library)
    │  dedup by phone
    ▼
List[Contact]
```

**Phone normalisation** uses the `phonenumbers` library with default region `IN` (configurable via `AGENT_LANGUAGE`).

**Error handling:** Each stage returns `(contacts, warnings, method)`. Partial failures surface as warnings, not hard errors, so a partially-readable PDF still returns whatever contacts were found.

---

### 6. Multi-Tenant Architecture

**Tenant isolation strategy:** Row-level filtering via `tenant_id` on every query. No separate schemas — simpler to operate on Neon's shared-tier plan.

**Tenant resolution:**
1. API key lookup → `tenant_id`
2. `CLIENT_ID` env var used as default `tenant_id` for single-tenant deployments (backward compatible)

**Role-based access (RBAC):**
```
admin   → full access including tenant management and billing
manager → campaigns, leads, analytics, settings (no tenant mgmt)
agent   → read-only leads and campaign status
```

Roles stored in `api_keys.role` column. Middleware enforces per-endpoint role requirements via a `@require_role("manager")` decorator.

**Sub-accounts:** A tenant with `parent_id` set is a sub-account. Sub-accounts inherit the parent's billing tier but have isolated campaign/lead data.

---

### 7. Production Infrastructure

**Docker setup** (`Dockerfile` + `docker-compose.yml`):
```dockerfile
# Multi-stage build
FROM python:3.11-slim AS builder
# install deps into /install

FROM python:3.11-slim AS runtime
COPY --from=builder /install /usr/local
COPY voice_agent/ /app
WORKDIR /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`docker-compose.yml` services: `api` (FastAPI), `frontend` (Nginx serving built React), optional `mongo` for local dev.

**Health checks** (`/health` enhanced):
```json
{
  "status": "ok",
  "postgres": "ok",
  "mongo": "ok",
  "gemini": "ok",
  "version": "2.0.0",
  "uptime_seconds": 3600
}
```

**Graceful shutdown:** FastAPI lifespan context manager closes DB pool and in-flight WebSocket sessions on SIGTERM.

**Structured logging:** Replace `logging.basicConfig` with `structlog` JSON output — each log line includes `tenant_id`, `campaign_id`, `lead_id` where available.

---

### 8. SSE Real-Time Events

New `event_bus.py` module:
```python
# In-process pub/sub using asyncio.Queue per connected client
class EventBus:
    def publish(self, tenant_id: str, event: dict): ...
    async def subscribe(self, tenant_id: str) -> AsyncGenerator[dict, None]: ...
```

Events published:
- `campaign.status_changed` — when campaign transitions state
- `lead.call_completed` — when a call finishes with classification + score
- `lead.insight_ready` — when Gemini analysis completes

Frontend subscribes via `EventSource('/api/events/stream')` with `X-API-Key` in query param (SSE doesn't support custom headers in browsers).

---

### 9. Campaign Automation

**Time-zone aware scheduling** (`scheduler.py`):
- Campaigns store `calling_window: {start: "09:00", end: "18:00", tz: "Asia/Kolkata"}`
- Orchestrator checks window before each dial; pauses automatically outside window
- Uses `zoneinfo` (stdlib Python 3.9+) for timezone conversion

**Campaign templates:**
- Stored in `campaign_templates` table
- `POST /api/campaigns/:id/template` saves current campaign config as template
- `POST /api/campaigns/start` accepts optional `template_id` to pre-fill config

**Campaign cloning:**
- `POST /api/campaigns/:id/clone` creates new campaign with same config, no leads
- Returns new `campaign_id` for immediate use

**Auto-pause on threshold:**
- Campaign config stores `min_connection_rate: float` (e.g. 0.3 = 30%)
- Orchestrator checks rate every 50 calls; pauses + emits alert event if below threshold

---

### 10. Security

**API key storage:** Raw key shown once at creation; only SHA-256 hash stored in DB.

**Webhook signature verification:** Exotel callback requests verified via HMAC-SHA256 of payload using `EXOTEL_API_TOKEN` as secret.

**CORS:** Tightened to explicit `ALLOWED_ORIGINS` env var list (replaces hardcoded localhost).

**Input validation:** All Pydantic models use `Field(max_length=...)` constraints. File uploads validated for MIME type (not just extension).

**Secrets in env:** No secrets in code. `.env.example` documents all required vars.

---

## Data Flow: Call → Insight → Dashboard

```
1. CampaignOrchestrator dials lead via Exotel/LiveKit
2. GeminiBridge streams audio ↔ Gemini Live API
3. On call end → ExotelCallHandler / LiveKitCallHandler calls on_call_end_callback
4. classifier.classify_and_analyze(transcript, duration, status, lead_id)
   ├── insights_analyzer.analyze_call() → Gemini text API → structured JSON
   ├── lead_scorer.score_lead() → 0-100 score
   └── call_insights.upsert_insight() → MongoDB
5. pg_db.update_contact_call_result() → PostgreSQL contacts table
6. billing.record_call() → PostgreSQL billing table
7. event_bus.publish("lead.call_completed", {...}) → SSE stream
8. React frontend receives SSE event → React Query cache invalidated → UI updates
```

---

## Correctness Properties

The following properties must hold and will be validated with property-based tests:

1. **Score bounds:** `score_lead(insights, duration, status)` always returns an integer in `[0, 100]` for any valid input combination.

2. **Category consistency:** A lead scored 80–100 is always categorised as `Hot`; 60–79 as `Warm`; 30–59 as `Cold`; 0–29 as `Not_Interested`. No overlap or gap.

3. **Tenant isolation:** For any two tenants `A` and `B`, a query scoped to `A` never returns rows belonging to `B`. Verified by inserting rows for both tenants and asserting disjoint result sets.

4. **Phone normalisation idempotency:** Normalising an already-normalised E.164 phone number returns the same number unchanged.

5. **File parser completeness:** For any CSV with `N` valid phone rows, the parser returns exactly `N` contacts (no silent drops) or raises a typed `CSVParseError`.

6. **Rate limiter correctness:** After exactly `limit` requests within the window, the `(limit+1)`th request is rejected with HTTP 429. After the window expires, requests are accepted again.

7. **Campaign stats consistency:** `stats.total == stats.pending + stats.dialing + stats.in_progress + stats.completed + stats.failed + stats.not_picked + stats.cancelled` at all times.

---

## File Structure Changes

```
voice_agent/
├── main.py                    # enhanced: new routes, SSE, auth middleware
├── config.py                  # enhanced: ALLOWED_ORIGINS, CALLING_WINDOW_*
├── auth_middleware.py          # NEW: API key auth + RBAC
├── rate_limiter.py             # NEW: sliding window rate limiter
├── event_bus.py                # NEW: in-process SSE pub/sub
├── lead_scorer.py              # NEW: scoring algorithm (extracted from insights_analyzer)
├── file_processor.py           # NEW: unified OCR pipeline (replaces ocr_parser.py)
├── scheduler.py                # NEW: time-zone aware calling window checks
├── pg_db.py                    # enhanced: new tables + migration helpers
├── campaign_orchestrator_pg.py # enhanced: auto-pause, calling window, template support
├── insights_analyzer.py        # enhanced: richer prompt, follow-up timing
├── classifier.py               # enhanced: uses lead_scorer
├── billing.py                  # unchanged (already solid)
├── call_insights.py            # unchanged
├── Dockerfile                  # NEW
├── docker-compose.yml          # NEW
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── Dashboard.tsx
    │   │   ├── Campaigns.tsx
    │   │   ├── CampaignDetail.tsx
    │   │   ├── Analytics.tsx
    │   │   ├── Leads.tsx
    │   │   ├── LeadDetail.tsx
    │   │   ├── Billing.tsx
    │   │   └── Settings.tsx
    │   ├── components/
    │   │   ├── StatsGrid.tsx
    │   │   ├── CampaignTable.tsx
    │   │   ├── LeadScoreBar.tsx
    │   │   ├── SentimentBadge.tsx
    │   │   ├── FunnelChart.tsx
    │   │   ├── CallTimeline.tsx
    │   │   └── FileUploadZone.tsx
    │   ├── hooks/
    │   │   ├── useSSE.ts
    │   │   └── useCampaign.ts
    │   └── api/
    │       └── client.ts       # typed API client (fetch wrapper)
    ├── package.json
    └── vite.config.ts
```
