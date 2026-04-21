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
  GET  /api/billing/*       — billing API
  GET  /dashboard           — simple HTML monitoring dashboard
"""
import logging
import os

import uvicorn
from fastapi import FastAPI, WebSocket, Request, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse, Response, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    SERVER_HOST, SERVER_PORT, PUBLIC_URL,
    AGENT_NAME, COMPANY_NAME, USE_LIVEKIT,
)
from exotel_handler import ExotelCallHandler
from outbound import make_outbound_call
from campaign_orchestrator_pg import orchestrator
from campaign_models import CampaignStatus, Lead, LeadStatus
from csv_parser import CSVParseError
from lead_info import get as get_lead_info
from ocr_parser import parse_file_to_contacts, SUPPORTED_EXTENSIONS
from call_insights import (
    get_insight, get_insights_by_campaign,
    get_insights_by_category, get_dashboard_summary,
)
from billing import record_call, get_monthly_summary, get_campaign_billing, estimate_cost
import pg_db

if USE_LIVEKIT:
    from livekit_handler import create_livekit_room

import uuid

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=f"{COMPANY_NAME} Sales Voice Agent",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Startup: Initialize PostgreSQL ───────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize PostgreSQL schema on startup."""
    try:
        pg_db.init_db()
        logger.info("PostgreSQL initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize PostgreSQL: {e}")
        raise


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "agent": AGENT_NAME, "company": COMPANY_NAME}


# ── ExoML endpoint ────────────────────────────────────────────────────────────

@app.get("/exoml")
async def exoml(
    lead_name: str = "there",
    lead_company: str = "",
    call_context: str = "",
    outbound: str = "false",
):
    ws_url = PUBLIC_URL.replace("https://", "wss://").replace("http://", "ws://")
    ws_url += "/ws/exotel"
    return JSONResponse({
        "url": (
            f"{ws_url}?lead_name={lead_name}"
            f"&lead_company={lead_company}"
            f"&call_context={call_context}"
            f"&outbound={outbound}"
        )
    })


# ── Call status callback ──────────────────────────────────────────────────────

@app.post("/call-status")
async def call_status(request: Request):
    form = await request.form()
    data = dict(form)
    logger.info(f"Call status: {data}")
    if orchestrator._current_campaign_id is not None:
        await orchestrator.on_call_status_callback(
            call_sid=data.get("CallSid", ""),
            status=data.get("Status", ""),
            duration=float(data.get("Duration") or 0),
        )
    return JSONResponse({"received": True})


# ── Outbound call ─────────────────────────────────────────────────────────────

class OutboundCallRequest(BaseModel):
    to: str
    from_number: str
    lead_name: str = "there"
    lead_company: str = ""
    call_context: str = ""
    record: bool = True


@app.post("/outbound")
async def trigger_outbound(req: OutboundCallRequest):
    try:
        result = await make_outbound_call(
            to=req.to,
            from_=req.from_number,
            lead_name=req.lead_name,
            lead_company=req.lead_company,
            call_context=req.call_context,
            record=req.record,
        )
        return {"status": "call_placed", "exotel_response": result}
    except Exception as e:
        logger.error(f"Outbound call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Exotel WebSocket ──────────────────────────────────────────────────────────

@app.websocket("/ws/exotel")
async def exotel_ws(websocket: WebSocket):
    await websocket.accept()
    on_call_end = None
    lead_id = ""
    initial_info = None

    if orchestrator._current_campaign_id is not None:
        campaign = pg_db.get_campaign(orchestrator._current_campaign_id)
        if campaign and campaign["status"] in ("Running", "Paused"):
            on_call_end = orchestrator.on_call_end_callback

    call_sid_param = websocket.query_params.get("callSid", "")
    if call_sid_param and orchestrator._current_campaign_id is not None:
        lead = pg_db.get_contact_by_call_sid(call_sid_param)
        if lead:
            lead_id = lead["lead_id"]
            initial_info = get_lead_info(lead_id)

    handler = ExotelCallHandler(
        websocket,
        on_call_end=on_call_end,
        lead_id=lead_id,
        initial_info=initial_info,
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


# ── Billing API ───────────────────────────────────────────────────────────────

@app.get("/api/billing/summary")
async def billing_summary(month: str = ""):
    data = get_monthly_summary(month or None)
    return {"success": True, "data": data}


@app.get("/api/billing/campaign/{campaign_id}")
async def billing_campaign(campaign_id: str, month: str = ""):
    data = get_campaign_billing(campaign_id, month or None)
    return {"success": True, "data": data}


class BillingEstimateRequest(BaseModel):
    num_contacts: int
    avg_duration_min: float = 2.0


@app.post("/api/billing/estimate")
async def billing_estimate(req: BillingEstimateRequest):
    data = estimate_cost(req.num_contacts, req.avg_duration_min)
    return {"success": True, "data": data}


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
