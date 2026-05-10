"""
Sales Voice Agent — FastAPI server.

Endpoints:
  GET  /health              — health check
  GET  /exoml               — ExoML Voicebot Applet for Exotel
  POST /call-status         — Exotel call status callback
  POST /outbound            — trigger a single outbound call
  WS   /ws/exotel           — Exotel AgentStream WebSocket
  POST /livekit/create-room — create LiveKit room (if USE_LIVEKIT=true)
  POST /campaign/upload     — upload CSV/PDF/image of leads
  POST /campaign/start      — start campaign
  POST /campaign/pause      — pause campaign
  POST /campaign/resume     — resume campaign
  POST /campaign/stop       — stop campaign
  GET  /campaign/status     — campaign status + per-lead data
  GET  /campaign/results    — download results CSV
  GET  /leads/{id}/info     — extracted lead info
  GET  /api/insights/*      — call insights API
  GET  /api/credits/*       — credits API
  GET  /api/analytics/*     — analytics API
  GET  /api/events/stream   — SSE real-time event stream
  GET  /dashboard           — simple HTML monitoring dashboard
"""
import asyncio
import hashlib
import importlib
import json
import logging
import os
import time as _time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import psycopg2.extras
import uvicorn
from fastapi import FastAPI, WebSocket, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from config import (
    SERVER_HOST, SERVER_PORT, PUBLIC_URL,
    AGENT_NAME, COMPANY_NAME, USE_LIVEKIT, CLIENT_ID,
    ALLOWED_ORIGINS,
)
from auth_middleware import APIKeyMiddleware
from rate_limiter import RateLimitMiddleware
from exotel_handler import ExotelCallHandler, _session_pool
from outbound import make_outbound_call
from campaign_orchestrator_pg import orchestrator
from campaign_models import Lead, LeadStatus
from csv_parser import CSVParseError
from lead_info import get as get_lead_info
from ocr_parser import parse_file_to_contacts, SUPPORTED_EXTENSIONS
from call_insights import (
    get_insight, get_insights_by_campaign,
    get_insights_by_category, get_dashboard_summary,
)
import credit_service
from credit_service import DuplicateIdempotencyKeyError
import pg_db
from event_bus import bus

if USE_LIVEKIT:
    from livekit_handler import create_livekit_room

import structlog
import uuid

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        pg_db.init_db()
        logger.info("PostgreSQL initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize PostgreSQL", error=str(e))
        raise

    # Start Gemini session pool in background — persists across the yield
    await _session_pool.start()

    yield

    # Shutdown
    logger.info("Shutting down — closing DB pool")
    try:
        pool = pg_db._pool
        if pool:
            pool.closeall()
            logger.info("PostgreSQL connection pool closed")
    except Exception as e:
        logger.error("Error closing DB pool", error=str(e))


app = FastAPI(
    title=f"{COMPANY_NAME} Sales Voice Agent",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(APIKeyMiddleware)
app.add_middleware(RateLimitMiddleware)

_START_TIME = _time.time()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    uptime = int(_time.time() - _START_TIME)

    # Check postgres
    postgres_status = "ok"
    try:
        pg_db.get_pool()
        with pg_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
    except Exception:
        postgres_status = "error"

    # Check mongo
    mongo_status = "ok"
    try:
        from db import get_db
        get_db().command("ping")
    except Exception:
        mongo_status = "error"

    # Check gemini (just verify API key is set)
    from config import GEMINI_API_KEY
    gemini_status = "ok" if GEMINI_API_KEY else "not_configured"

    return {
        "status": "ok",
        "postgres": postgres_status,
        "mongo": mongo_status,
        "gemini": gemini_status,
        "version": "2.0.0",
        "uptime_seconds": uptime,
        "agent": AGENT_NAME,
        "company": COMPANY_NAME,
    }


# ── ExoML endpoint ────────────────────────────────────────────────────────────

@app.get("/exoml")
async def exoml(
    request: Request,
    lead_name: str = "there",
    lead_company: str = "",
    call_context: str = "",
    prompt_type: str = "sales",
    outbound: str = "false",
    org_id: str = "",
):
    # Parse CustomField if present
    custom_field = request.query_params.get("CustomField", "")
    if custom_field:
        from urllib.parse import parse_qs
        parsed = parse_qs(custom_field)
        lead_name    = parsed.get("lead_name",    [lead_name])[0]
        lead_company = parsed.get("lead_company", [lead_company])[0]
        call_context = parsed.get("call_context", [call_context])[0]
        prompt_type  = parsed.get("prompt_type",  [prompt_type])[0]
        outbound     = parsed.get("outbound",     [outbound])[0]
        org_id       = parsed.get("org_id",       [org_id])[0]

    # Resolve org config — use tenant_id from auth if no explicit org_id
    if not org_id:
        org_id = getattr(request.state, "tenant_id", CLIENT_ID)
    resolved_org_config = _org_config_mod.get_org_config(org_id) if org_id else None

    # Store params keyed by CallSid so the WS handler can look them up reliably
    call_sid = request.query_params.get("CallSid", "")
    if call_sid:
        import call_store
        from prompts import build_outbound_intro
        from gemini_bridge import GeminiBridge

        is_outbound = outbound.lower() == "true"
        outbound_intro = build_outbound_intro(lead_name, prompt_type) if is_outbound else None

        try:
            bridge = GeminiBridge(
                call_sid=call_sid,
                lead_name=lead_name,
                lead_company=lead_company,
                call_context=call_context,
                outbound_intro=outbound_intro,
                prompt_type=prompt_type,
                org_config=resolved_org_config,
            )
            await bridge.start(send_greeting=False)

            if outbound_intro:
                trigger = (
                    f"IMPORTANT: The lead's name is {lead_name!r}. Call type: {prompt_type}.\n"
                    f"Say exactly and only: \"{outbound_intro}\" — nothing else. Wait for the customer to respond before saying anything more."
                )
            else:
                trigger = f"IMPORTANT: The lead's name is {lead_name!r}. Call type: {prompt_type}. Say exactly and only: \"Hello.\" — nothing else. Wait for the customer to respond."
            await bridge._session.send_realtime_input(text=trigger)

            call_store.store_bridge(call_sid, bridge)
            logger.info(f"[{call_sid}] Gemini session pre-started + greeting triggered: lead={lead_name!r}, prompt_type={prompt_type!r}, org_id={org_id!r}")
        except Exception as e:
            logger.error(f"[{call_sid}] Failed to pre-start Gemini session: {e}")
            call_store.store(call_sid, {
                "lead_name": lead_name, "lead_company": lead_company,
                "call_context": call_context, "prompt_type": prompt_type, "outbound": outbound,
            })

    ws_url = PUBLIC_URL.replace("https://", "wss://").replace("http://", "ws://")
    ws_url += f"/ws/exotel?call_sid={call_sid}"
    return JSONResponse({"url": ws_url})


# ── Call status callback ──────────────────────────────────────────────────────

# In-memory set of numbers currently being called — prevents duplicate simultaneous calls
_active_call_numbers: set[str] = set()


@app.post("/call-status")
async def call_status(request: Request):
    form = await request.form()
    data = dict(form)
    logger.info(f"Call status: {data}")

    call_sid = data.get("CallSid", "")
    status = data.get("Status", "")

    # Release dedup lock when call reaches a terminal state
    terminal_statuses = {"completed", "failed", "busy", "no-answer", "canceled", "cancelled"}
    if status.lower() in terminal_statuses:
        # Exotel sends CallFrom as the customer number
        raw_number = data.get("CallFrom", data.get("From", ""))
        normalised = raw_number.strip().lstrip("+").lstrip("0")
        _active_call_numbers.discard(normalised)

    # Exotel sends CallDuration (seconds) in the status callback
    duration = float(data.get("CallDuration") or data.get("Duration") or 0)

    if orchestrator._current_campaign_id is not None:
        await orchestrator.on_call_status_callback(
            call_sid=call_sid,
            status=status,
            duration=duration,
        )

    # Finalize credit deduction when the call reaches a terminal state.
    # Resolve tenant_id from the call record; fall back to CLIENT_ID.
    if status.lower() in terminal_statuses and call_sid:
        try:
            tenant_id = CLIENT_ID
            if call_sid:
                contact = pg_db.get_contact_by_call_sid(call_sid)
                if contact:
                    # Look up the campaign to get the tenant (client_id)
                    campaign = pg_db.get_campaign(contact.get("campaign_id", ""))
                    if campaign:
                        tenant_id = campaign.get("client_id", CLIENT_ID)
            credit_service.finalize_call(tenant_id, call_sid, duration)
        except Exception as exc:
            logger.warning(f"credit_service.finalize_call failed for call_sid={call_sid!r}: {exc}")

    return JSONResponse({"received": True})


# ── Outbound call ─────────────────────────────────────────────────────────────


class OutboundCallRequest(BaseModel):
    to: str
    from_number: str
    lead_name: str = "there"
    lead_company: str = ""
    call_context: str = ""
    record: bool = True
    prompt_type: str = "sales"  # sales, feedback, insurance_only, followup, objection, callback


@app.post("/outbound")
async def trigger_outbound(req: OutboundCallRequest, request: Request):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)

    # Step 1: Check balance before placing the call — return 402 if zero.
    # Requirements: 3.1, 3.2
    balance = credit_service.get_balance(tenant_id)
    if balance == 0:
        raise HTTPException(
            status_code=402,
            detail="Insufficient credits. Please purchase credits to continue making calls.",
        )

    # Normalise number for dedup check
    normalised = req.to.strip().lstrip("+").lstrip("0")
    if normalised in _active_call_numbers:
        raise HTTPException(
            status_code=429,
            detail=f"A call to {req.to} is already active. Wait for it to complete before placing another."
        )
    _active_call_numbers.add(normalised)
    try:
        # Step 2: Place the call — Exotel returns the real call_sid.
        result = await make_outbound_call(
            to=req.to,
            from_=req.from_number,
            lead_name=req.lead_name,
            lead_company=req.lead_company,
            call_context=req.call_context,
            record=req.record,
            prompt_type=req.prompt_type,
        )

        # Step 3: Reserve 1 credit using the real Exotel call_sid.
        # This is slightly racy (balance could drop to 0 between check and reserve)
        # but acceptable for MVP — check_and_reserve will raise InsufficientCreditsError
        # if another concurrent call consumed the last credit.
        call_sid = result.get("call_sid", "")
        if call_sid and call_sid != "unknown":
            try:
                credit_service.check_and_reserve(tenant_id, call_sid)
            except credit_service.InsufficientCreditsError:
                # Balance was consumed between check and reserve — log but don't fail
                # the call since it's already been placed.
                logger.warning(
                    f"Credit reservation failed after call placed: tenant={tenant_id!r}, "
                    f"call_sid={call_sid!r} — balance exhausted between check and reserve"
                )
            except credit_service.DuplicateReservationError:
                # Already reserved (shouldn't happen for a fresh call_sid, but safe to ignore)
                pass

        return {"status": "call_placed", "exotel_response": result}
    except HTTPException:
        _active_call_numbers.discard(normalised)
        raise
    except Exception as e:
        _active_call_numbers.discard(normalised)
        logger.error(f"Outbound call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Standalone call transcript logger ────────────────────────────────────────

_TRANSCRIPT_DIR = os.path.join(os.path.dirname(__file__), "transcripts")
os.makedirs(_TRANSCRIPT_DIR, exist_ok=True)

async def _standalone_call_end(call_sid: str, transcript: str, collected_info):
    """Save transcript + collected info to a timestamped file after every standalone call."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = os.path.join(_TRANSCRIPT_DIR, f"{ts}_{call_sid}.txt")
    lines = [
        f"Call SID : {call_sid}",
        f"Time     : {datetime.now(timezone.utc).isoformat()}",
        f"",
        f"─── TRANSCRIPT ───────────────────────────────────────────",
        transcript.strip() if transcript.strip() else "(no transcript captured)",
        f"",
        f"─── COLLECTED INFO ───────────────────────────────────────",
        str(collected_info) if collected_info else "(none)",
    ]
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    logger.info(f"[{call_sid}] Transcript saved → {filename}")


# ── Exotel WebSocket ──────────────────────────────────────────────────────────

@app.websocket("/ws/exotel")
async def exotel_ws(websocket: WebSocket):
    await websocket.accept()
    logger.info(f"WebSocket connection accepted from {websocket.client}")
    
    on_call_end = None
    lead_id = ""
    initial_info = None

    if orchestrator._current_campaign_id is not None:
        campaign = pg_db.get_campaign(orchestrator._current_campaign_id)
        if campaign and campaign["status"] in ("Running", "Paused"):
            on_call_end = orchestrator.on_call_end_callback

    # Standalone call — wire up transcript logger so every call is saved to disk
    if on_call_end is None:
        on_call_end = _standalone_call_end

    # Try to get lead info from query params (for campaign calls)
    call_sid_param = websocket.query_params.get("callSid", "")
    if call_sid_param and orchestrator._current_campaign_id is not None:
        lead = pg_db.get_contact_by_call_sid(call_sid_param)
        if lead:
            lead_id = lead["lead_id"]
            initial_info = get_lead_info(lead_id)
    
    # Look up call params stored at /exoml time via call_store
    call_sid_param = websocket.query_params.get("call_sid", "")
    import call_store
    stored = call_store.pop(call_sid_param) if call_sid_param else {}

    lead_name    = stored.get("lead_name",    "there")
    prompt_type  = stored.get("prompt_type",  "sales")
    lead_company = stored.get("lead_company", "")
    is_outbound  = stored.get("outbound",     "false").lower() == "true"

    logger.info(f"WebSocket handler: lead={lead_name!r}, prompt_type={prompt_type!r}, outbound={is_outbound}, sid={call_sid_param!r}")

    handler = ExotelCallHandler(
        websocket,
        on_call_end=on_call_end,
        lead_id=lead_id,
        initial_info=initial_info,
        prompt_type=prompt_type,
        lead_name=lead_name,
        lead_company=lead_company,
        is_outbound=is_outbound,
    )
    await handler.run()


# ── LiveKit ───────────────────────────────────────────────────────────────────

class LiveKitCallRequest(BaseModel):
    lead_id: str = ""
    lead_name: str = "there"
    lead_company: str = ""
    call_context: str = ""


@app.post("/livekit/create-room")
async def livekit_create_room(req: LiveKitCallRequest):
    if not USE_LIVEKIT:
        raise HTTPException(status_code=400, detail="LiveKit is not enabled. Set USE_LIVEKIT=true in .env")
    try:
        on_call_end = None
        initial_info = None
        if orchestrator._current_campaign_id is not None:
            campaign = pg_db.get_campaign(orchestrator._current_campaign_id)
            if campaign and campaign["status"] in ("Running", "Paused"):
                on_call_end = orchestrator.on_call_end_callback
        if req.lead_id:
            initial_info = get_lead_info(req.lead_id)
        room_details = await create_livekit_room(
            lead_id=req.lead_id,
            lead_name=req.lead_name,
            lead_company=req.lead_company,
            call_context=req.call_context,
            initial_info=initial_info,
            on_call_end=on_call_end,
        )
        return {"status": "room_created", **room_details}
    except Exception as e:
        logger.error(f"Failed to create LiveKit room: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Campaign ──────────────────────────────────────────────────────────────────

@app.post("/campaign/upload")
async def campaign_upload(file: UploadFile = File(...)):
    try:
        filename = file.filename or ""
        ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
        if f".{ext}" not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Supported: CSV, PDF, JPG, PNG, GIF, BMP, TIFF",
            )
        file_bytes = await file.read()
        contacts, method = parse_file_to_contacts(file_bytes, filename)
        if not contacts:
            raise HTTPException(
                status_code=400,
                detail=f"No valid contacts found in {filename} (method: {method})",
            )
        leads = [
            Lead(
                lead_id=str(uuid.uuid4()),
                name=c.get("name", ""),
                phone=c["phone"],
                company=c.get("company", ""),
                extra={"email": c.get("email", ""), "source": c.get("source", "")},
                status=LeadStatus.PENDING,
            )
            for c in contacts if c.get("phone")
        ]
        upload_id = orchestrator.store_pending_leads(leads, ["name", "phone", "company", "email"])
        return {
            "campaign_id": upload_id,
            "lead_count": len(leads),
            "skipped": len(contacts) - len(leads),
            "processing_method": method,
        }
    except CSVParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class CampaignStartRequest(BaseModel):
    name: str
    concurrency_limit: int
    virtual_number: str
    inter_call_delay_ms: int = 500


@app.post("/campaign/start")
async def campaign_start(req: CampaignStartRequest):
    if not orchestrator._pending_leads:
        raise HTTPException(status_code=400, detail="No leads uploaded. Upload a file first.")
    try:
        leads = orchestrator._pending_leads[:]
        columns = orchestrator._pending_columns[:]
        orchestrator._pending_leads = []
        orchestrator._pending_columns = []
        campaign = orchestrator.create(
            name=req.name,
            concurrency_limit=req.concurrency_limit,
            virtual_number=req.virtual_number,
            inter_call_delay_ms=req.inter_call_delay_ms,
            leads=leads,
            original_columns=columns,
        )
        await orchestrator.start()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "started", "campaign_id": campaign["campaign_id"]}


@app.post("/campaign/pause")
async def campaign_pause():
    if orchestrator._current_campaign_id is None:
        raise HTTPException(status_code=404, detail="No active campaign.")
    await orchestrator.pause()
    return {"status": "paused"}


@app.post("/campaign/resume")
async def campaign_resume():
    if orchestrator._current_campaign_id is None:
        raise HTTPException(status_code=404, detail="No active campaign.")
    await orchestrator.resume()
    return {"status": "resumed"}


@app.post("/campaign/stop")
async def campaign_stop():
    if orchestrator._current_campaign_id is None:
        raise HTTPException(status_code=404, detail="No active campaign.")
    await orchestrator.stop()
    return {"status": "stopped"}


@app.get("/campaign/status")
async def campaign_status():
    if orchestrator._current_campaign_id is None:
        raise HTTPException(status_code=404, detail="No active campaign.")
    return orchestrator.get_status()


@app.get("/campaign/results")
async def campaign_results():
    if orchestrator._current_campaign_id is None:
        raise HTTPException(status_code=404, detail="No active campaign.")
    return Response(
        content=orchestrator.get_results_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="results.csv"'},
    )


# ── Lead info ─────────────────────────────────────────────────────────────────

@app.get("/leads/{lead_id}/info")
async def lead_info_endpoint(lead_id: str):
    info = get_lead_info(lead_id)
    if info is None:
        raise HTTPException(status_code=404, detail="No info found for this lead.")
    return info


# ── Insights API ──────────────────────────────────────────────────────────────

@app.get("/api/insights/dashboard")
async def insights_dashboard(campaign_id: str = ""):
    return {"success": True, "data": get_dashboard_summary(campaign_id)}


@app.get("/api/insights/leads/{category}")
async def insights_leads_by_category(category: str, campaign_id: str = ""):
    category_map = {
        "hot": "Hot", "warm": "Warm", "cold": "Cold",
        "not_interested": "Not_Interested", "not-interested": "Not_Interested",
    }
    db_category = category_map.get(category.lower(), category)
    leads = get_insights_by_category(db_category, campaign_id)
    return {"success": True, "data": {"leads": leads}}


@app.get("/api/insights/campaign/{campaign_id}")
async def insights_by_campaign(campaign_id: str):
    return {"success": True, "data": get_insights_by_campaign(campaign_id)}


@app.get("/api/insights/lead/{lead_id}")
async def insight_detail(lead_id: str):
    insight = get_insight(lead_id)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    return {"success": True, "data": insight}


# ── Billing API (credits-based — monthly billing removed) ────────────────────

@app.get("/api/billing")
@app.get("/api/billing/summary")
async def billing_summary(request: Request, month: str = ""):
    """Credits summary — kept for backwards compatibility with the frontend.

    Returns credit balance and pricing instead of the old monthly billing data.
    """
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    data = credit_service.get_balance_with_pricing(tenant_id)
    return {"success": True, "data": data}


class BillingEstimateRequest(BaseModel):
    num_contacts: int
    avg_duration_min: float = 2.0  # minutes; 1 credit = 1 minute = 60 seconds


@app.post("/api/billing/estimate")
async def billing_estimate(req: BillingEstimateRequest, request: Request):
    """Estimate credits needed for a batch of calls.

    1 credit = 60 seconds (1 minute). Usage is decimal — no rounding up.
    A 1.5-minute call costs 1.5 credits exactly.
    Returns estimated credits and INR cost at the tenant's price_per_credit.
    """
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    price_per_credit = pg_db.get_credit_pricing(tenant_id)
    estimated_credits = round(req.num_contacts * req.avg_duration_min, 4)
    estimated_cost = round(estimated_credits * price_per_credit, 2)
    return {
        "success": True,
        "data": {
            "num_contacts": req.num_contacts,
            "avg_duration_min": req.avg_duration_min,
            "estimated_credits": estimated_credits,
            "price_per_credit": price_per_credit,
            "estimated_cost_inr": estimated_cost,
        },
    }


class PurchaseRequest(BaseModel):
    amount: int
    description: str = ""
    idempotency_key: str | None = None


class AdminAdjustRequest(BaseModel):
    tenant_id: str
    amount: int
    description: str


# ── SSE event stream ──────────────────────────────────────────────────────────

@app.get("/api/events/stream")
async def events_stream(request: Request, api_key: str = ""):
    """
    Server-Sent Events endpoint for real-time event streaming.

    Browsers cannot set custom headers for SSE, so the API key is accepted
    as a query parameter. Falls back to CLIENT_ID from config if omitted.
    """
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        try:
            pool = pg_db.get_pool()
            record = pg_db.get_api_key_by_hash(pool, key_hash)
        except Exception:
            logger.exception("DB error during SSE API key lookup")
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        if not record:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        tenant_id = record["tenant_id"]
    else:
        tenant_id = CLIENT_ID

    async def event_generator():
        async for event in bus.subscribe(tenant_id):
            if await request.is_disconnected():
                break
            yield {"data": json.dumps(event)}

    return EventSourceResponse(event_generator())


# ── Simple HTML dashboard ─────────────────────────────────────────────────────

@app.get("/dashboard")
async def dashboard():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lead Dialer Dashboard</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:system-ui,sans-serif;background:#f5f5f5;color:#222}
  header{background:#1a1a2e;color:#fff;padding:16px 24px}
  header h1{font-size:1.3rem}
  .container{max-width:1100px;margin:24px auto;padding:0 16px;display:grid;gap:20px}
  .card{background:#fff;border-radius:8px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
  .card h2{font-size:1rem;margin-bottom:14px;color:#444;text-transform:uppercase;letter-spacing:.05em}
  label{display:block;font-size:.85rem;margin-bottom:4px;color:#555}
  input[type=text],input[type=number],input[type=file]{width:100%;padding:8px 10px;border:1px solid #ccc;border-radius:5px;font-size:.9rem;margin-bottom:12px}
  .row{display:flex;gap:12px;flex-wrap:wrap}
  .row .field{flex:1;min-width:160px}
  button{padding:8px 18px;border:none;border-radius:5px;cursor:pointer;font-size:.9rem;font-weight:600;transition:opacity .15s}
  button:hover{opacity:.85}
  .btn-primary{background:#2563eb;color:#fff}
  .btn-warning{background:#d97706;color:#fff}
  .btn-success{background:#16a34a;color:#fff}
  .btn-danger{background:#dc2626;color:#fff}
  .btn-neutral{background:#6b7280;color:#fff}
  .btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:4px}
  .status-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:.8rem;font-weight:700;text-transform:uppercase}
  .status-idle{background:#e5e7eb;color:#374151}
  .status-running{background:#dcfce7;color:#166534}
  .status-paused{background:#fef9c3;color:#854d0e}
  .status-finished{background:#dbeafe;color:#1e40af}
  .stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:10px}
  .stat-box{background:#f9fafb;border:1px solid #e5e7eb;border-radius:6px;padding:10px;text-align:center}
  .stat-box .val{font-size:1.6rem;font-weight:700;color:#1a1a2e}
  .stat-box .lbl{font-size:.72rem;color:#6b7280;margin-top:2px;text-transform:uppercase}
  table{width:100%;border-collapse:collapse;font-size:.85rem}
  th{background:#f3f4f6;text-align:left;padding:8px 10px;border-bottom:2px solid #e5e7eb}
  td{padding:7px 10px;border-bottom:1px solid #f0f0f0}
  tr:hover td{background:#fafafa}
  .lead-status{font-weight:600}
  .ls-pending{color:#6b7280}.ls-dialing{color:#2563eb}.ls-in_progress{color:#7c3aed}
  .ls-completed{color:#16a34a}.ls-failed{color:#dc2626}.ls-not_picked{color:#d97706}.ls-cancelled{color:#9ca3af}
  .cls-hot{color:#dc2626;font-weight:700}.cls-warm{color:#d97706;font-weight:700}.cls-cold{color:#2563eb;font-weight:700}
  #error-msg{background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;border-radius:6px;padding:10px 14px;margin-bottom:12px;display:none}
  #success-msg{background:#dcfce7;color:#166534;border:1px solid #86efac;border-radius:6px;padding:10px 14px;margin-bottom:12px;display:none}
  #download-link{display:inline-block;padding:8px 18px;background:#0f766e;color:#fff;border-radius:5px;text-decoration:none;font-weight:600;font-size:.9rem;margin-top:12px}
  .section-header{display:flex;align-items:center;gap:12px;margin-bottom:14px}
  .section-header h2{margin-bottom:0}
</style>
</head>
<body>
<header><h1>Lead Dialer Dashboard</h1></header>
<div class="container">
  <div id="error-msg"></div>
  <div id="success-msg"></div>

  <div class="card">
    <h2>Upload &amp; Configure Campaign</h2>
    <div class="row">
      <div class="field">
        <label>CSV / PDF / Image</label>
        <input type="file" id="csv-file" accept=".csv,.pdf,.jpg,.jpeg,.png,.gif,.bmp,.tiff" onchange="csvUploaded=false">
      </div>
      <div class="field" style="display:flex;align-items:flex-end;padding-bottom:12px">
        <button class="btn-neutral" onclick="uploadFile()">Upload</button>
      </div>
    </div>
    <div class="row">
      <div class="field"><label>Campaign Name</label><input type="text" id="cfg-name" placeholder="My Campaign"></div>
      <div class="field"><label>Virtual Number</label><input type="text" id="cfg-number" placeholder="+91XXXXXXXXXX"></div>
      <div class="field"><label>Concurrency (1–50)</label><input type="number" id="cfg-concurrency" value="5" min="1" max="50"></div>
      <div class="field"><label>Inter-call Delay (ms)</label><input type="number" id="cfg-delay" value="500" min="0" max="5000"></div>
    </div>
    <div class="btn-row">
      <button class="btn-primary" onclick="startCampaign()">Start</button>
      <button class="btn-warning" onclick="pauseCampaign()">Pause</button>
      <button class="btn-success" onclick="resumeCampaign()">Resume</button>
      <button class="btn-danger" onclick="stopCampaign()">Stop</button>
    </div>
  </div>

  <div class="card">
    <div class="section-header">
      <h2>Campaign Status</h2>
      <span id="status-badge" class="status-badge status-idle">Idle</span>
    </div>
    <div class="stats-grid">
      <div class="stat-box"><div class="val" id="s-total">—</div><div class="lbl">Total</div></div>
      <div class="stat-box"><div class="val" id="s-pending">—</div><div class="lbl">Pending</div></div>
      <div class="stat-box"><div class="val" id="s-dialing">—</div><div class="lbl">Dialing</div></div>
      <div class="stat-box"><div class="val" id="s-in_progress">—</div><div class="lbl">In Progress</div></div>
      <div class="stat-box"><div class="val" id="s-completed">—</div><div class="lbl">Completed</div></div>
      <div class="stat-box"><div class="val" id="s-failed">—</div><div class="lbl">Failed</div></div>
      <div class="stat-box"><div class="val" id="s-not_picked">—</div><div class="lbl">Not Picked</div></div>
      <div class="stat-box"><div class="val" id="s-cancelled">—</div><div class="lbl">Cancelled</div></div>
      <div class="stat-box"><div class="val" id="s-hot">—</div><div class="lbl">Hot 🔥</div></div>
      <div class="stat-box"><div class="val" id="s-warm">—</div><div class="lbl">Warm</div></div>
      <div class="stat-box"><div class="val" id="s-cold">—</div><div class="lbl">Cold</div></div>
    </div>
    <div id="download-row" style="display:none">
      <a id="download-link" href="/campaign/results">Download Results CSV</a>
    </div>
  </div>

  <div class="card">
    <h2>Leads</h2>
    <div style="overflow-x:auto">
      <table>
        <thead><tr><th>Name</th><th>Phone</th><th>Status</th><th>Classification</th><th>Duration (s)</th></tr></thead>
        <tbody id="leads-tbody"><tr><td colspan="5" style="color:#9ca3af;text-align:center;padding:20px">No campaign data yet.</td></tr></tbody>
      </table>
    </div>
  </div>
</div>

<script>
const TERMINAL = new Set(["Completed","Failed","Not_Picked","Cancelled"]);
let csvUploaded = false;

function showError(msg){const el=document.getElementById("error-msg");el.textContent=msg;el.style.display="block";setTimeout(()=>el.style.display="none",8000)}
function showSuccess(msg){const el=document.getElementById("success-msg");el.textContent=msg;el.style.display="block";setTimeout(()=>el.style.display="none",5000)}

async function apiCall(method,path,body){
  try{
    const opts={method,headers:{}};
    if(body){opts.body=JSON.stringify(body);opts.headers["Content-Type"]="application/json"}
    const res=await fetch(path,opts);
    const data=await res.json().catch(()=>({}));
    if(!res.ok){showError(data.detail||res.statusText);return null}
    return data;
  }catch(e){showError("Network error: "+e.message);return null}
}

async function uploadFile(){
  const fi=document.getElementById("csv-file");
  if(!fi.files.length){showError("Select a file first.");return}
  const fd=new FormData();fd.append("file",fi.files[0]);
  try{
    const res=await fetch("/campaign/upload",{method:"POST",body:fd});
    const data=await res.json().catch(()=>({}));
    if(!res.ok){showError(data.detail||res.statusText);return}
    csvUploaded=true;
    showSuccess(`Uploaded ${data.lead_count} leads (skipped: ${data.skipped}, method: ${data.processing_method}). Configure and click Start.`);
  }catch(e){showError("Upload failed: "+e.message)}
}

async function startCampaign(){
  if(!csvUploaded){showError("Upload a file first.");return}
  const name=document.getElementById("cfg-name").value.trim();
  const virtual_number=document.getElementById("cfg-number").value.trim();
  const concurrency_limit=parseInt(document.getElementById("cfg-concurrency").value,10);
  const inter_call_delay_ms=parseInt(document.getElementById("cfg-delay").value,10);
  if(!name){showError("Campaign name is required.");return}
  if(!virtual_number){showError("Virtual number is required.");return}
  const r=await apiCall("POST","/campaign/start",{name,concurrency_limit,virtual_number,inter_call_delay_ms});
  if(r){csvUploaded=false;showSuccess("Campaign started.")}
}

async function pauseCampaign(){const r=await apiCall("POST","/campaign/pause");if(r)showSuccess("Paused.")}
async function resumeCampaign(){const r=await apiCall("POST","/campaign/resume");if(r)showSuccess("Resumed.")}
async function stopCampaign(){const r=await apiCall("POST","/campaign/stop");if(r)showSuccess("Stopped.")}

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}

function updateDashboard(data){
  const badge=document.getElementById("status-badge");
  const st=(data.status||"Idle").toLowerCase();
  badge.textContent=data.status||"Idle";
  badge.className="status-badge status-"+st;
  const stats=data.stats||{};
  ["total","pending","dialing","in_progress","completed","failed","not_picked","cancelled","hot","warm","cold"].forEach(f=>{
    const el=document.getElementById("s-"+f);
    if(el)el.textContent=stats[f]!==undefined?stats[f]:"—";
  });
  const leads=data.leads||[];
  document.getElementById("download-row").style.display=leads.some(l=>TERMINAL.has(l.status))?"block":"none";
  const tbody=document.getElementById("leads-tbody");
  if(!leads.length){tbody.innerHTML='<tr><td colspan="5" style="color:#9ca3af;text-align:center;padding:20px">No leads.</td></tr>';return}
  tbody.innerHTML=leads.map(l=>{
    const dur=l.call_duration_seconds!=null?l.call_duration_seconds.toFixed(1):"—";
    const cls=l.classification||"—";
    const sc="ls-"+l.status.toLowerCase();
    const cc=l.classification?"cls-"+l.classification.toLowerCase():"";
    return`<tr><td>${esc(l.name||"")}</td><td>${esc(l.phone||"")}</td><td><span class="lead-status ${sc}">${esc(l.status)}</span></td><td><span class="${cc}">${esc(cls)}</span></td><td>${dur}</td></tr>`;
  }).join("");
}

async function pollStatus(){
  try{
    const res=await fetch("/campaign/status");
    if(res.status===404){updateDashboard({status:"Idle",stats:{},leads:[]});return}
    if(!res.ok)return;
    updateDashboard(await res.json());
  }catch(_){}
}

pollStatus();
setInterval(pollStatus,3000);
</script>
</body>
</html>"""
    return Response(content=html, media_type="text/html")


# ── Campaign CRUD routes ──────────────────────────────────────────────────────

@app.get("/api/campaigns")
async def list_campaigns_api(request: Request, page: int = 1, limit: int = 20):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    campaigns = pg_db.list_campaigns(tenant_id, limit=limit)
    return {"success": True, "data": campaigns, "page": page}


class CreateCampaignRequest(BaseModel):
    name: str
    description: str = ""
    concurrency_limit: int = 5
    virtual_number: str = ""
    inter_call_delay_ms: int = 500


@app.post("/api/campaigns")
async def create_campaign_api(req: CreateCampaignRequest, request: Request):
    """Create a new campaign record (without leads — leads uploaded separately)."""
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    campaign_id = str(uuid.uuid4())
    pg_db.create_campaign(
        campaign_id=campaign_id,
        client_id=tenant_id,
        name=req.name,
        concurrency_limit=req.concurrency_limit,
        virtual_number=req.virtual_number or "",
        inter_call_delay_ms=req.inter_call_delay_ms,
        original_columns=[],
    )
    campaign = pg_db.get_campaign(campaign_id)
    return {"success": True, "data": dict(campaign)}


@app.get("/api/campaigns/templates")
async def list_campaign_templates(request: Request):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    templates = pg_db.list_templates(None, tenant_id)
    return {"success": True, "data": templates}


@app.get("/api/campaigns/{campaign_id}")
async def get_campaign_api(campaign_id: str):
    campaign = pg_db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    stats = pg_db.get_campaign_stats(campaign_id)
    return {"success": True, "data": {**dict(campaign), "stats": dict(stats)}}


class UpdateCampaignRequest(BaseModel):
    name: str | None = None


@app.put("/api/campaigns/{campaign_id}")
async def update_campaign_api(campaign_id: str, req: UpdateCampaignRequest):
    campaign = pg_db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if req.name:
        with pg_db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE campaigns SET name = %s WHERE campaign_id = %s", (req.name, campaign_id))
    return {"success": True, "data": pg_db.get_campaign(campaign_id)}


class CloneCampaignRequest(BaseModel):
    name: str


@app.post("/api/campaigns/{campaign_id}/clone")
async def clone_campaign_api(campaign_id: str, req: CloneCampaignRequest, request: Request):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    new_id = str(uuid.uuid4())
    try:
        new_campaign = pg_db.clone_campaign(None, campaign_id, new_id, req.name, tenant_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True, "data": new_campaign}


class SaveTemplateRequest(BaseModel):
    name: str


@app.post("/api/campaigns/{campaign_id}/template")
async def save_campaign_template(campaign_id: str, req: SaveTemplateRequest, request: Request):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    campaign = pg_db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    template_id = str(uuid.uuid4())
    pg_db.save_template(
        None, template_id, tenant_id, req.name,
        concurrency_limit=campaign.get("concurrency_limit"),
        inter_call_delay_ms=campaign.get("inter_call_delay_ms"),
    )
    return {"success": True, "data": {"template_id": template_id}}


# ── Lead browse/management routes ─────────────────────────────────────────────

@app.get("/api/leads")
async def list_leads_api(
    request: Request,
    campaign_id: str = "",
    category: str = "",
    page: int = 1,
    limit: int = 50,
    sort: str = "",
    min_score: int = 0,
    max_score: int = 100,
):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    if campaign_id:
        leads = pg_db.list_contacts(campaign_id, status=None)
    else:
        with pg_db.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT c.* FROM contacts c
                    JOIN campaigns camp ON c.campaign_id = camp.campaign_id
                    WHERE camp.client_id = %s
                    ORDER BY c.updated_at DESC LIMIT %s OFFSET %s
                """, (tenant_id, limit, (page - 1) * limit))
                leads = cur.fetchall()
    leads = [dict(l) for l in leads]
    if category:
        leads = [l for l in leads if l.get("classification") == category]
    # Score filtering (lead_score stored in call_insights, approximate via classification)
    if min_score > 0 or max_score < 100:
        def _score(l: dict) -> int:
            # Use lead_score from extra if present, otherwise estimate from classification
            s = l.get("lead_score") or l.get("extra", {}).get("lead_score")
            if s is not None:
                return int(s)
            cls = (l.get("classification") or "").lower()
            return {"hot": 85, "warm": 65, "cold": 40, "not_interested": 15}.get(cls, 0)
        leads = [l for l in leads if min_score <= _score(l) <= max_score]
    # Sorting
    if sort == "score":
        leads.sort(key=lambda l: l.get("lead_score") or 0, reverse=True)
    return {"success": True, "data": leads}


@app.get("/api/leads/{lead_id}/history")
async def get_lead_history(lead_id: str, request: Request):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    with pg_db.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM lead_interactions
                WHERE lead_id = %s AND tenant_id = %s
                ORDER BY occurred_at DESC
            """, (lead_id, tenant_id))
            interactions = cur.fetchall()
    return {"success": True, "data": [dict(i) for i in interactions]}


@app.get("/api/leads/{lead_id}/events")
async def get_lead_events(lead_id: str, request: Request):
    """Return call events / interaction history for a lead (alias for /history)."""
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    with pg_db.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM lead_interactions
                WHERE lead_id = %s AND tenant_id = %s
                ORDER BY occurred_at DESC
            """, (lead_id, tenant_id))
            interactions = cur.fetchall()
    return {"success": True, "data": [dict(i) for i in interactions]}


@app.get("/api/leads/{lead_id}")
async def get_lead_api(lead_id: str):
    lead = pg_db.get_contact(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    insight = get_insight(lead_id)
    return {"success": True, "data": {**dict(lead), "insight": insight}}


class UpdateLeadCategoryRequest(BaseModel):
    category: str


@app.put("/api/leads/{lead_id}/category")
async def update_lead_category(lead_id: str, req: UpdateLeadCategoryRequest):
    lead = pg_db.get_contact(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    pg_db.update_contact_call_result(lead_id, lead["status"], classification=req.category)
    return {"success": True}


class FollowUpRequest(BaseModel):
    follow_up_at: str
    notes: str = ""


@app.post("/api/leads/{lead_id}/follow-up")
async def schedule_follow_up(lead_id: str, req: FollowUpRequest, request: Request):
    """Schedule a follow-up task for a lead."""
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    lead = pg_db.get_contact(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    try:
        scheduled_at = datetime.fromisoformat(req.follow_up_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid follow_up_at datetime format")
    result = pg_db.upsert_follow_up(
        None,
        lead_id=lead_id,
        tenant_id=tenant_id,
        scheduled_at=scheduled_at,
        campaign_id=lead.get("campaign_id"),
        notes=req.notes or None,
    )
    # Also record as an interaction
    pg_db.insert_interaction(
        None,
        lead_id=lead_id,
        tenant_id=tenant_id,
        type="follow_up_scheduled",
        summary=f"Follow-up scheduled for {req.follow_up_at}",
        metadata={"notes": req.notes},
    )
    return {"success": True, "data": result}


# ── Analytics routes ──────────────────────────────────────────────────────────

def _build_analytics_payload(tenant_id: str) -> dict:
    """Build the combined analytics payload used by /api/analytics and /api/analytics/summary."""
    summary = get_dashboard_summary("")
    # Aggregate counts across all campaigns for this tenant
    with pg_db.get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    COUNT(*) as total_leads,
                    COUNT(*) FILTER (WHERE c.classification = 'Hot') as hot,
                    COUNT(*) FILTER (WHERE c.classification = 'Warm') as warm,
                    COUNT(*) FILTER (WHERE c.classification = 'Cold') as cold,
                    COUNT(*) FILTER (WHERE c.status IN ('Dialing','In_Progress')) as in_progress,
                    COUNT(*) FILTER (WHERE c.status = 'Completed') as completed
                FROM contacts c
                JOIN campaigns camp ON c.campaign_id = camp.campaign_id
                WHERE camp.client_id = %s
            """, (tenant_id,))
            counts = cur.fetchone() or {}

            # Sentiment distribution from contacts extra field
            cur.execute("""
                SELECT
                    COALESCE(extra->>'sentiment', 'unknown') as sentiment,
                    COUNT(*) as count
                FROM contacts c
                JOIN campaigns camp ON c.campaign_id = camp.campaign_id
                WHERE camp.client_id = %s AND extra->>'sentiment' IS NOT NULL
                GROUP BY extra->>'sentiment'
            """, (tenant_id,))
            sentiment_rows = cur.fetchall()

            # Intent breakdown
            cur.execute("""
                SELECT
                    COALESCE(extra->>'buying_intent', 'unknown') as intent,
                    COUNT(*) as count
                FROM contacts c
                JOIN campaigns camp ON c.campaign_id = camp.campaign_id
                WHERE camp.client_id = %s AND extra->>'buying_intent' IS NOT NULL
                GROUP BY extra->>'buying_intent'
            """, (tenant_id,))
            intent_rows = cur.fetchall()

    # Funnel data
    funnel = [
        {"stage": "Total", "count": counts.get("total_leads", 0)},
        {"stage": "Completed", "count": counts.get("completed", 0)},
        {"stage": "Hot", "count": counts.get("hot", 0)},
        {"stage": "Warm", "count": counts.get("warm", 0)},
    ]

    return {
        "total_leads": counts.get("total_leads", 0),
        "hot": counts.get("hot", 0),
        "warm": counts.get("warm", 0),
        "cold": counts.get("cold", 0),
        "in_progress": counts.get("in_progress", 0),
        "completed": counts.get("completed", 0),
        "funnel": funnel,
        "sentiment_distribution": [dict(r) for r in sentiment_rows],
        "intent_breakdown": [dict(r) for r in intent_rows],
        "top_topics": summary.get("top_topics", []) if isinstance(summary, dict) else [],
    }


@app.get("/api/analytics")
@app.get("/api/analytics/summary")
async def analytics_combined(request: Request):
    """Combined analytics — accessible at /api/analytics and /api/analytics/summary."""
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    try:
        data = _build_analytics_payload(tenant_id)
    except Exception as exc:
        logger.error("analytics_combined failed", error=str(exc))
        data = {"total_leads": 0, "hot": 0, "warm": 0, "cold": 0, "in_progress": 0,
                "completed": 0, "funnel": [], "sentiment_distribution": [],
                "intent_breakdown": [], "top_topics": []}
    return {"success": True, "data": data}


@app.get("/api/analytics/overview")
async def analytics_overview(request: Request):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    try:
        data = _build_analytics_payload(tenant_id)
    except Exception as exc:
        logger.error("analytics_overview failed", error=str(exc))
        data = {}
    return {"success": True, "data": data}


@app.get("/api/analytics/funnel")
async def analytics_funnel(request: Request, campaign_id: str = ""):
    if campaign_id:
        stats = pg_db.get_campaign_stats(campaign_id)
    else:
        tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
        with pg_db.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE c.status = 'Completed') as completed,
                        COUNT(*) FILTER (WHERE c.classification = 'Hot') as hot,
                        COUNT(*) FILTER (WHERE c.classification = 'Warm') as warm,
                        COUNT(*) FILTER (WHERE c.classification = 'Cold') as cold
                    FROM contacts c
                    JOIN campaigns camp ON c.campaign_id = camp.campaign_id
                    WHERE camp.client_id = %s
                """, (tenant_id,))
                stats = cur.fetchone()
    funnel = [
        {"stage": "Total", "count": stats.get("total", 0)},
        {"stage": "Completed", "count": stats.get("completed", 0)},
        {"stage": "Hot", "count": stats.get("hot", 0)},
        {"stage": "Warm", "count": stats.get("warm", 0)},
    ]
    return {"success": True, "data": funnel}


@app.get("/api/analytics/sentiment")
async def analytics_sentiment(campaign_id: str = ""):
    insights = get_insights_by_campaign(campaign_id) if campaign_id else get_dashboard_summary("")
    return {"success": True, "data": insights}


@app.get("/api/analytics/topics")
async def analytics_topics(campaign_id: str = ""):
    insights = get_insights_by_campaign(campaign_id) if campaign_id else {}
    return {"success": True, "data": insights}


@app.get("/api/analytics/timeline")
async def analytics_timeline(request: Request, month: str = ""):
    """Return daily call counts for the current month from contacts table."""
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    target_month = month or datetime.now(timezone.utc).strftime("%Y-%m")
    try:
        with pg_db.get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        DATE(updated_at) AS date,
                        COUNT(*) AS calls
                    FROM contacts
                    WHERE client_id = %s
                      AND status IN ('Completed', 'Failed', 'Not_Picked')
                      AND TO_CHAR(updated_at, 'YYYY-MM') = %s
                    GROUP BY DATE(updated_at)
                    ORDER BY date
                """, (tenant_id, target_month))
                rows = cur.fetchall()
        data = [{"date": str(r["date"]), "calls": int(r["calls"])} for r in rows]
    except Exception as exc:
        logger.warning(f"analytics_timeline query failed: {exc}")
        data = []
    return {"success": True, "data": data}


# ── Auth management routes ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    api_key: str


@app.post("/api/auth/login")
async def auth_login(req: LoginRequest):
    key_hash = hashlib.sha256(req.api_key.encode()).hexdigest()
    record = pg_db.get_api_key_by_hash(None, key_hash)
    if not record:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return {"success": True, "data": {"tenant_id": record["tenant_id"], "role": record["role"]}}


class CreateApiKeyRequest(BaseModel):
    name: str = ""
    role: str = "manager"


@app.post("/api/auth/api-keys")
async def create_api_key_endpoint(req: CreateApiKeyRequest, request: Request):
    import secrets
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = str(uuid.uuid4())
    pg_db.create_api_key(None, key_id, tenant_id, key_hash, name=req.name, role=req.role)
    return {"success": True, "data": {"key_id": key_id, "api_key": raw_key, "name": req.name}}


@app.delete("/api/auth/api-keys/{key_id}")
async def revoke_api_key_endpoint(key_id: str, request: Request):
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    pg_db.revoke_api_key(None, key_id, tenant_id)
    return {"success": True}


# ── Settings routes ───────────────────────────────────────────────────────────

@app.get("/api/settings")
async def get_settings(request: Request):
    from config import AGENT_NAME, COMPANY_NAME, PRODUCT_NAME, AGENT_LANGUAGE, GEMINI_VOICE, GEMINI_SPEAKING_RATE
    import gemini_bridge as _gb
    return {"success": True, "data": {
        "agent_name":           AGENT_NAME,
        "company_name":         COMPANY_NAME,
        "product_name":         PRODUCT_NAME,
        "agent_language":       AGENT_LANGUAGE,
        "gemini_voice":         GEMINI_VOICE,
        "gemini_speaking_rate": GEMINI_SPEAKING_RATE,
        "affective_dialog":     getattr(_gb, "_AFFECTIVE_DIALOG", True),
    }}


class UpdateSettingsRequest(BaseModel):
    agent_name: str | None = None
    company_name: str | None = None
    product_name: str | None = None
    agent_language: str | None = None
    gemini_voice: str | None = None
    gemini_speaking_rate: float | None = None
    affective_dialog: bool | None = None


@app.put("/api/settings")
async def update_settings(req: UpdateSettingsRequest):
    """
    Persist settings to the .env file and hot-reload config module values.
    Changes take effect immediately for new calls without a server restart.
    """
    import config as _cfg

    updates: dict[str, str] = {}
    if req.agent_name is not None:
        updates["AGENT_NAME"] = req.agent_name
    if req.company_name is not None:
        updates["COMPANY_NAME"] = req.company_name
    if req.product_name is not None:
        updates["PRODUCT_NAME"] = req.product_name
    if req.agent_language is not None:
        updates["AGENT_LANGUAGE"] = req.agent_language
    if req.gemini_voice is not None:
        updates["GEMINI_VOICE"] = req.gemini_voice
    if req.gemini_speaking_rate is not None:
        updates["GEMINI_SPEAKING_RATE"] = str(req.gemini_speaking_rate)

    if updates:
        # Write to .env file
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        try:
            if os.path.exists(env_path):
                with open(env_path, "r") as f:
                    lines = f.readlines()
            else:
                lines = []

            existing_keys = {}
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    existing_keys[key] = i

            for key, value in updates.items():
                escaped = value.replace('"', '\\"')
                new_line = f'{key}="{escaped}"\n'
                if key in existing_keys:
                    lines[existing_keys[key]] = new_line
                else:
                    lines.append(new_line)

            with open(env_path, "w") as f:
                f.writelines(lines)
        except Exception as exc:
            logger.warning("Could not write .env file", error=str(exc))

        # Hot-patch config module so changes apply immediately
        for key, value in updates.items():
            os.environ[key] = value
            if hasattr(_cfg, key):
                attr_val = float(value) if key == "GEMINI_SPEAKING_RATE" else value
                setattr(_cfg, key, attr_val)

    # Hot-patch affective dialog flag on gemini_bridge module
    if req.affective_dialog is not None:
        try:
            import gemini_bridge as _gb
            _gb._AFFECTIVE_DIALOG = req.affective_dialog
        except Exception:
            pass

    # Reload gemini_bridge so voice/rate/language take effect for new calls
    reload_fields = {"gemini_voice", "gemini_speaking_rate", "agent_language", "affective_dialog"}
    if reload_fields & (req.model_fields_set or set()):
        try:
            import gemini_bridge
            importlib.reload(gemini_bridge)
        except Exception:
            pass

    return {"success": True, "message": "Settings saved"}


# ── Org Config API ────────────────────────────────────────────────────────────
# Temporary in-memory multi-tenant org store.
# Each org is identified by a unique org_id (string).
# All fields are optional — missing fields fall back to global config defaults.

import org_config as _org_config_mod
from org_config import ORG_CONFIG_FIELDS


class OrgConfigRequest(BaseModel):
    org_id: str
    agent_name: str = ""
    company_name: str = ""
    product_name: str = ""
    agent_language: str = ""
    gemini_voice: str = ""
    gemini_speaking_rate: float = 0.0
    business_type: str = ""
    operating_city: str = ""
    company_email: str = ""
    company_legal_name: str = ""
    industry_experience: str = ""
    sales_manager_name: str = ""
    product_restrictions: str = ""
    business_context: str = ""
    opening_question: str = ""
    qualify_questions: str = ""
    pitch_lines: str = ""
    calling_window_start: str = ""
    calling_window_end: str = ""
    calling_window_tz: str = ""
    min_connection_rate: float = 0.0


@app.post("/api/orgs")
async def create_org(req: OrgConfigRequest, request: Request):
    """Register a new organisation with its agent/business config."""
    data = {k: v for k, v in req.dict().items() if k != "org_id" and v not in ("", 0.0)}
    result = _org_config_mod.upsert_org_config(req.org_id, data)
    return {"success": True, "org_id": req.org_id, "config": result}


@app.get("/api/orgs")
async def list_orgs(request: Request):
    """List all registered organisations."""
    return {"success": True, "orgs": _org_config_mod.list_orgs()}


@app.get("/api/orgs/{org_id}")
async def get_org(org_id: str, request: Request):
    """Get the merged config for an org (org values + global defaults)."""
    raw = _org_config_mod.get_raw_org(org_id)
    if raw is None:
        raise HTTPException(status_code=404, detail=f"Org '{org_id}' not found")
    merged = _org_config_mod.get_org_config(org_id)
    return {"success": True, "org_id": org_id, "stored": raw, "effective": merged}


@app.put("/api/orgs/{org_id}")
async def update_org(org_id: str, req: OrgConfigRequest, request: Request):
    """Update an existing org's config (partial update — only provided fields are changed)."""
    data = {k: v for k, v in req.dict().items() if k != "org_id" and v not in ("", 0.0)}
    result = _org_config_mod.upsert_org_config(org_id, data)
    return {"success": True, "org_id": org_id, "config": result}


@app.delete("/api/orgs/{org_id}")
async def delete_org(org_id: str, request: Request):
    """Remove an org's config from the store."""
    existed = _org_config_mod.delete_org(org_id)
    if not existed:
        raise HTTPException(status_code=404, detail=f"Org '{org_id}' not found")
    return {"success": True, "org_id": org_id, "message": "Org deleted"}


@app.get("/api/orgs/{org_id}/fields")
async def get_org_fields(request: Request):
    """Return the list of configurable org fields."""
    return {"success": True, "fields": ORG_CONFIG_FIELDS}


# ── Credits API ───────────────────────────────────────────────────────────────

@app.get("/api/credits/balance")
async def credits_balance(request: Request):
    """Return the current credit balance for the authenticated tenant.

    Requirements: 5.1, 5.2
    """
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    balance = credit_service.get_balance(tenant_id)
    return {"balance": balance, "tenant_id": tenant_id}


@app.get("/api/credits/ledger")
async def credits_ledger(request: Request, page: int = 1, page_size: int = 50):
    """Return a paginated ledger of credit transactions for the authenticated tenant.

    Requirements: 5.3, 5.4
    """
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    return credit_service.get_ledger(tenant_id, page=page, page_size=page_size)


@app.post("/api/credits/purchase")
async def credits_purchase(req: PurchaseRequest, request: Request):
    """Purchase credits for the authenticated tenant.

    Returns HTTP 400 on invalid amount, HTTP 200 with original result on
    duplicate idempotency key.

    Requirements: 2.4, 2.5, 9.1
    """
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    try:
        result = credit_service.purchase_credits(
            tenant_id=tenant_id,
            amount=req.amount,
            description=req.description,
            idempotency_key=req.idempotency_key,
        )
        return result
    except DuplicateIdempotencyKeyError as exc:
        return exc.original_result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/credits/admin/adjust")
async def credits_admin_adjust(req: AdminAdjustRequest, request: Request):
    """Apply a signed credit adjustment for any tenant (admin only).

    Requires the caller's API key to have role == "admin".
    Returns HTTP 403 if not admin, HTTP 400 if adjustment would go negative.

    Requirements: 8.1, 8.2, 8.3
    """
    role = getattr(request.state, "role", None)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")

    admin_tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    try:
        result = credit_service.admin_adjust(
            tenant_id=req.tenant_id,
            amount=req.amount,
            description=req.description,
            admin_tenant_id=admin_tenant_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class SetPricingRequest(BaseModel):
    price_per_credit: float


@app.get("/api/credits/admin/pricing/{tenant_id}")
async def get_credit_pricing(tenant_id: str, request: Request):
    """Get the price per credit (INR) for a specific tenant (admin only)."""
    role = getattr(request.state, "role", None)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")
    try:
        price = pg_db.get_credit_pricing(tenant_id)
        return {"tenant_id": tenant_id, "price_per_credit": price}
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@app.put("/api/credits/admin/pricing/{tenant_id}")
async def set_credit_pricing(tenant_id: str, req: SetPricingRequest, request: Request):
    """Set a custom price per credit (INR) for a specific tenant (admin only).

    Example: price_per_credit=6 means 1 credit costs ₹6 for that tenant.
    Tenants cannot make calls if their balance is 0.
    """
    role = getattr(request.state, "role", None)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required.")
    try:
        new_price = pg_db.set_credit_pricing(tenant_id, req.price_per_credit)
        return {"tenant_id": tenant_id, "price_per_credit": new_price}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/credits/pricing")
async def get_my_credit_pricing(request: Request):
    """Get the price per credit (INR) for the authenticated tenant."""
    tenant_id = getattr(request.state, "tenant_id", CLIENT_ID)
    price = pg_db.get_credit_pricing(tenant_id)
    return {"tenant_id": tenant_id, "price_per_credit": price}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    workers = int(os.getenv("SERVER_WORKERS", "1"))
    uvicorn.run(
        "main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        workers=workers,
        reload=False,
        log_level="info",
    )
