# Implementation Plan: Bolna AI Enhancement

## Overview

Incrementally transform the existing FastAPI + PostgreSQL voice agent into a production-ready platform. Each task builds on the previous one, wiring new modules into the running system as they are completed.

## Tasks

- [x] 1. Extend config and database schema
  - Add `ALLOWED_ORIGINS`, `CALLING_WINDOW_START`, `CALLING_WINDOW_END`, `CALLING_WINDOW_TZ`, and `MIN_CONNECTION_RATE` env vars to `config.py`
  - Add migration for 5 new PostgreSQL tables (`tenants`, `api_keys`, `campaign_templates`, `lead_interactions`, `follow_ups`) inside `pg_db.init_db()`
  - Add `role` column to `api_keys` table and helper functions: `create_tenant`, `create_api_key`, `get_api_key_by_hash`, `revoke_api_key`, `save_template`, `list_templates`, `clone_campaign`, `insert_interaction`, `upsert_follow_up`
  - Add composite indexes: `idx_contacts_score`, `idx_contacts_updated`, `idx_billing_month_tenant`
  - _Requirements: 5.1, 5.2, 9.1, 9.4_

- [x] 2. Implement auth middleware and rate limiter
  - [x] 2.1 Create `auth_middleware.py` with `APIKeyMiddleware` class
    - Read `X-API-Key` header or `Authorization: Bearer` token
    - Hash with SHA-256, look up in `api_keys` table, attach `tenant_id` and `role` to `request.state`
    - Skip auth for `/health`, `/exoml`, `/ws/*`, `/call-status`
    - Return HTTP 401 for missing/invalid keys
    - _Requirements: 6.4, 5.3_

  - [x] 2.2 Write unit tests for `APIKeyMiddleware`
    - Test valid key passes, invalid key returns 401, skipped paths bypass auth
    - _Requirements: 6.4_

  - [x] 2.3 Create `rate_limiter.py` with `SlidingWindowRateLimiter` class
    - In-memory sliding window per `tenant_id`; default 100 req/min, 10 req/min for upload endpoints
    - `check(tenant_id, endpoint) -> bool` and `RateLimitMiddleware` FastAPI middleware
    - Return HTTP 429 with `Retry-After` header on breach
    - _Requirements: 6.2, 6.3_

  - [x] 2.4 Write property test for rate limiter correctness (Property 6)
    - **Property 6: Rate limiter correctness**
    - After exactly `limit` requests within the window, the `(limit+1)`th request is rejected; after window expiry requests are accepted again
    - **Validates: Requirements 6.2, 6.3**

- [x] 3. Implement lead scorer module
  - [x] 3.1 Create `lead_scorer.py` with `score_lead(insights, duration, status) -> int`
    - Implement scoring algorithm from design: completion (+20), duration (up to +15), sentiment (+0/+10/+20), intent (+0/+15/+25), interest_level (up to +10), decision_maker (+10), budget (+10), follow_up (+15), engagement_score (up to +10)
    - Clamp result to `[0, 100]`
    - Add `category_from_score(score) -> str` returning `Hot/Warm/Cold/Not_Interested`
    - _Requirements: 3.2, 3.4_

  - [x] 3.2 Write property test for score bounds (Property 1)
    - **Property 1: Score bounds**
    - `score_lead(insights, duration, status)` always returns an integer in `[0, 100]` for any valid input combination
    - **Validates: Requirements 3.2**

  - [x] 3.3 Write property test for category consistency (Property 2)
    - **Property 2: Category consistency**
    - A lead scored 80–100 is always `Hot`; 60–79 `Warm`; 30–59 `Cold`; 0–29 `Not_Interested` — no overlap or gap
    - **Validates: Requirements 3.2**

  - [x] 3.4 Update `classifier.py` to import and use `lead_scorer.score_lead` and `lead_scorer.category_from_score` instead of the inline `calculate_lead_score` in `insights_analyzer.py`
    - _Requirements: 3.2_

- [x] 4. Enhance insights analyzer
  - [x] 4.1 Update `_ANALYSIS_PROMPT` in `insights_analyzer.py` to include `follow_up_recommended_at` (ISO timestamp), `objection_categories` list, and `talk_ratio` fields in the returned JSON
  - [x] 4.2 Update `analyze_call` return dict to expose `follow_up_recommended_at`, `objection_categories`, and `talk_ratio`
  - [x] 4.3 Remove `calculate_lead_score` from `insights_analyzer.py` and delegate to `lead_scorer`
  - _Requirements: 3.3, 3.6, 3.7, 7.5_

- [x] 5. Implement file processor pipeline
  - [x] 5.1 Create `file_processor.py` with `FileTypeDetector`, `ContactExtractor`, `ContactNormalizer`, and top-level `process_file(file_bytes, filename) -> tuple[list[Contact], list[str], str]`
    - Detect: csv / pdf-text / pdf-scan / image
    - CSV → existing `csv_parser.py`; PDF text → `pdfplumber`; PDF scan + image → `pytesseract`
    - Normalise phones to E.164 using `phonenumbers` with default region from `AGENT_LANGUAGE`
    - Dedup by phone; return `(contacts, warnings, method)`
    - _Requirements: 2.1, 2.3, 2.4, 2.5_

  - [x] 5.2 Write property test for file parser completeness (Property 5)
    - **Property 5: File parser completeness**
    - For any CSV with N valid phone rows, the parser returns exactly N contacts or raises `CSVParseError`
    - **Validates: Requirements 2.1, 2.4**

  - [x] 5.3 Write property test for phone normalisation idempotency (Property 4)
    - **Property 4: Phone normalisation idempotency**
    - Normalising an already-normalised E.164 phone number returns the same number unchanged
    - **Validates: Requirements 2.4**

- [x] 6. Implement event bus and SSE endpoint
  - [x] 6.1 Create `event_bus.py` with `EventBus` class
    - `publish(tenant_id, event: dict)` — fan-out to all subscriber queues for that tenant
    - `async subscribe(tenant_id) -> AsyncGenerator[dict, None]` — yields events from an `asyncio.Queue`
    - Module-level singleton `bus = EventBus()`
    - _Requirements: 1.4, 4.1_

  - [x] 6.2 Add `GET /api/events/stream` SSE endpoint to `main.py`
    - Accept `api_key` query param for browser SSE auth
    - Use `EventSourceResponse` (sse-starlette) to stream events from `bus.subscribe(tenant_id)`
    - _Requirements: 1.2, 1.4_

- [x] 7. Implement scheduler for calling windows
  - Create `scheduler.py` with `CallingWindowChecker`
    - `is_within_window(tz: str, start: str, end: str) -> bool` using `zoneinfo`
    - `get_seconds_until_window_open(tz, start, end) -> float`
    - _Requirements: 10.1, 10.2_

- [x] 8. Enhance campaign orchestrator
  - [x] 8.1 Add `calling_window` and `min_connection_rate` fields to campaign creation in `campaign_orchestrator_pg.py` and `pg_db.create_campaign`
  - [x] 8.2 In `_dispatch_loop`, call `CallingWindowChecker.is_within_window` before each dial; sleep until window opens if outside
  - [x] 8.3 Add connection-rate check every 50 calls; auto-pause and publish `campaign.auto_paused` event via `event_bus` if rate drops below `min_connection_rate`
  - [x] 8.4 Publish `campaign.status_changed` and `lead.call_completed` events via `event_bus` at appropriate points in the orchestrator
  - _Requirements: 10.1, 10.2, 10.7, 4.7_

- [x] 9. Checkpoint — core backend modules complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Add enhanced API routes to main.py
  - [x] 10.1 Wire `APIKeyMiddleware` and `RateLimitMiddleware` into the FastAPI app; update CORS to use `ALLOWED_ORIGINS` from config
  - [x] 10.2 Add campaign CRUD routes: `GET /api/campaigns`, `GET /api/campaigns/{id}`, `PUT /api/campaigns/{id}`, `POST /api/campaigns/{id}/clone`, `POST /api/campaigns/{id}/template`, `GET /api/campaigns/templates`
  - [x] 10.3 Add lead browse/management routes: `GET /api/leads`, `GET /api/leads/{id}`, `PUT /api/leads/{id}/category`, `GET /api/leads/{id}/history`
  - [x] 10.4 Add analytics routes: `GET /api/analytics/overview`, `GET /api/analytics/funnel`, `GET /api/analytics/sentiment`, `GET /api/analytics/topics`, `GET /api/analytics/timeline`
  - [x] 10.5 Add auth management routes: `POST /api/auth/login`, `POST /api/auth/api-keys`, `DELETE /api/auth/api-keys/{id}`
  - [x] 10.6 Add settings routes: `GET /api/settings`, `PUT /api/settings`
  - [x] 10.7 Enhance `GET /health` to return postgres/mongo/gemini status, version, and uptime
  - _Requirements: 6.1, 5.5, 4.3, 8.2_

  - [x] 10.8 Write property test for tenant isolation (Property 3)
    - **Property 3: Tenant isolation**
    - For any two tenants A and B, a query scoped to A never returns rows belonging to B
    - **Validates: Requirements 5.3**

- [x] 11. Build React frontend scaffold
  - [x] 11.1 Create `voice_agent/frontend/package.json` with React 18, Vite, TailwindCSS, Recharts, React Query, React Router v6, Zustand, and sse-starlette client deps
  - [x] 11.2 Create `voice_agent/frontend/vite.config.ts` with proxy to `http://localhost:8000` for `/api` and `/campaign`
  - [x] 11.3 Create `voice_agent/frontend/src/api/client.ts` — typed fetch wrapper that attaches `X-API-Key` header from localStorage and handles 401/429 responses
  - [x] 11.4 Create `voice_agent/frontend/src/hooks/useSSE.ts` — `EventSource` hook that reconnects on error and exposes latest event
  - [x] 11.5 Create `voice_agent/frontend/src/hooks/useCampaign.ts` — React Query hooks for campaign CRUD and status polling (3 s fallback)
  - _Requirements: 1.1, 1.2_

- [x] 12. Build shared UI components
  - [x] 12.1 Create `StatsGrid.tsx` — animated metric cards for Total, Hot, Warm, Cold, In-Progress counts
  - [x] 12.2 Create `CampaignTable.tsx` — sortable/filterable table with status badges and action buttons
  - [x] 12.3 Create `LeadScoreBar.tsx` — 0–100 score bar with colour gradient (red→yellow→green)
  - [x] 12.4 Create `SentimentBadge.tsx` — positive/neutral/negative pill with colour coding
  - [x] 12.5 Create `FunnelChart.tsx` — Recharts funnel from Pending → Completed → Hot
  - [x] 12.6 Create `CallTimeline.tsx` — per-lead call history list with transcript preview expand/collapse
  - [x] 12.7 Create `FileUploadZone.tsx` — drag-and-drop zone with upload progress bar and OCR method indicator
  - _Requirements: 1.1, 1.3, 1.5, 2.2_

- [x] 13. Build frontend pages
  - [x] 13.1 Create `Dashboard.tsx` — live stats via `useSSE` + `StatsGrid`, recent campaigns table, top leads list; auto-refresh every 3 s
  - [x] 13.2 Create `Campaigns.tsx` — paginated campaign list using `CampaignTable`; create campaign modal with `FileUploadZone`
  - [x] 13.3 Create `CampaignDetail.tsx` — campaign stats, leads table with `LeadScoreBar` + `SentimentBadge`, drill-down to lead detail
  - [x] 13.4 Create `Analytics.tsx` — `FunnelChart`, sentiment distribution bar, intent breakdown, topics word cloud using Recharts
  - [x] 13.5 Create `Leads.tsx` — filterable lead browser (by campaign, category, score range)
  - [x] 13.6 Create `LeadDetail.tsx` — full insight view: `CallTimeline`, score breakdown, follow-up scheduling
  - [x] 13.7 Create `Billing.tsx` — monthly summary, tier info, per-campaign breakdown table
  - [x] 13.8 Create `Settings.tsx` — API key management (create/revoke), agent persona fields, webhook config
  - [x] 13.9 Create `App.tsx` with React Router routes and sidebar navigation; redirect `/` to `/dashboard`
  - _Requirements: 1.1, 1.3, 1.5, 1.6, 4.3, 4.6, 7.2_

- [x] 14. Checkpoint — frontend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Add Docker production infrastructure
  - [x] 15.1 Create `voice_agent/Dockerfile` with multi-stage build: `builder` stage installs Python deps; `runtime` stage copies app and runs uvicorn
  - [x] 15.2 Create `voice_agent/docker-compose.yml` with services: `api` (FastAPI on port 8000), `frontend` (Nginx serving built React dist), optional `mongo` for local dev; include health checks and env_file reference
  - [x] 15.3 Add graceful shutdown lifespan context manager to `main.py` (replaces `@app.on_event("startup")`) that closes DB pool and logs shutdown
  - [x] 15.4 Replace `logging.basicConfig` in `main.py` with `structlog` JSON output including `tenant_id`, `campaign_id`, `lead_id` context fields
  - _Requirements: 8.1, 8.2, 8.4, 8.3_

- [x] 16. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

  - [x] 16.1 Write property test for campaign stats consistency (Property 7)
    - **Property 7: Campaign stats consistency**
    - `stats.total == stats.pending + stats.dialing + stats.in_progress + stats.completed + stats.failed + stats.not_picked + stats.cancelled` at all times
    - **Validates: Requirements 9.1, 4.1**

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate the 7 universal correctness properties defined in the design
- Unit tests validate specific examples and edge cases
- The `client_id` columns in existing tables are treated as `tenant_id` — no data migration needed
