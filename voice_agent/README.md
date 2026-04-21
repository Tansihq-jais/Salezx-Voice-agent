# 🤖 Sales Voice Agent — LiveKit + Gemini Live 2.5 Flash

A production-grade AI sales caller that bridges **LiveKit** (real-time communication)
with **Google Gemini Live 2.5 Flash Native Audio** (real-time voice AI).

Now includes a **Bulk Lead Dialer** — upload a CSV of leads, configure concurrency,
and let the system dial everyone automatically while you monitor progress on a live dashboard.

> **🆕 NEW: LiveKit Integration!** 
> We now support LiveKit for better scalability, lower latency, and 96% cost savings!
> See [LIVEKIT_QUICKSTART.md](./LIVEKIT_QUICKSTART.md) to get started in 5 minutes.

---

## 🚀 Quick Start with LiveKit (Recommended)

### 1. Get LiveKit credentials
Sign up at https://cloud.livekit.io/ (free tier available)

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Install and run
```bash
pip install -r requirements.txt
./start_livekit.sh  # or start_livekit.bat on Windows
```

### 4. Test it!
Open http://localhost:8000/livekit-client and start talking! 🎤

📚 **Full guides:**
- [Quick Start (5 min)](./LIVEKIT_QUICKSTART.md)
- [Detailed Setup](./LIVEKIT_SETUP.md)
- [Migration from Exotel](./LIVEKIT_MIGRATION.md)

---

## Architecture

### LiveKit Architecture (New)
```
Web/Mobile Client
   │
   ▼
LiveKit Server (WebRTC)
   │  (bidirectional audio — 16-48 kHz)
   ▼
FastAPI Server  (/livekit/create-room)
   │
   ├─ LiveKitCallHandler
   │     │
   │     ▼
   │  GeminiBridge  ──── Gemini Live API (WebSocket) ────► Gemini 2.5 Flash
   │     │                                                  Native Audio
   │     ▼
   └─ Audio chunks → back to LiveKit → played to caller
```

### Exotel Architecture (Legacy)
```
Phone Call
   │
   ▼
Exotel PSTN/SIP
   │  (bidirectional WebSocket — 8 kHz PCM)
   ▼
FastAPI Server  (/ws/exotel)
   │
   ├─ ExotelCallHandler
   │     │  upsample 8→16 kHz
   │     ▼
   │  GeminiBridge  ──── Gemini Live API (WebSocket) ────► Gemini 2.5 Flash
   │     │                                                  Native Audio
   │     │  downsample 24→8 kHz
   │     ▼
   └─ Audio chunks → back to Exotel → played to caller
```

### Bulk Dialer
```
Browser Dashboard (/dashboard)
      │  REST polls every 3s
      ▼
Campaign REST API (/campaign/*)
      │
CampaignOrchestrator  ──── asyncio semaphore ────► create_livekit_room()
      │                                                  │
LeadStore (in-memory)                           LiveKitCallHandler + GeminiBridge
      │
Classifier  ──── keyword match on transcript ────► Hot / Warm / Cold / Not_Picked
```

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your API keys
```

### 3. Expose your server (local dev)
```bash
ngrok http 8000
# Copy the https URL into PUBLIC_URL in .env
```

### 4. Run the server
```bash
python main.py
```

### 5. Configure Exotel
- Go to **App Bazaar → Create Flow**
- Add **Voicebot Applet** → URL: `https://your-server.com/exoml`
- Add **Hangup Applet** at the end
- Assign the flow to your Exotel number
- Set the **Call Status Callback URL** to `https://your-server.com/call-status`

### 6. Place a single outbound call (REST API)
```bash
curl -X POST http://localhost:8000/outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "+918012345678",
    "lead_name": "Rahul",
    "lead_company": "Acme Corp",
    "call_context": "Downloaded free trial 3 days ago"
  }'
```

### 7. Run a bulk campaign (Modern UI)

#### Option A: Modern React Dashboard (Recommended)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` in your browser:
1. Upload a CSV file (see `leads_sample.csv` for the expected format)
2. Fill in campaign name, virtual number, concurrency limit, and inter-call delay
3. Click **Start Campaign** — the system dials all leads concurrently up to your limit
4. Watch real-time statistics and per-lead status updates
5. Click **Download Results** when done to get a CSV with classifications

Features:
- 🎨 Modern dark theme with gradients
- 📊 Real-time statistics dashboard
- 📞 Live call monitoring
- 🎯 Lead classification visualization (Hot/Warm/Cold)
- 📱 Fully responsive design

#### Option B: Simple HTML Dashboard

Open `http://localhost:8000/dashboard` in your browser for a basic HTML interface.

Or use the REST API directly:

```bash
# 1. Upload leads
curl -X POST http://localhost:8000/campaign/upload \
  -F "file=@leads_sample.csv"

# 2. Start campaign
curl -X POST http://localhost:8000/campaign/start \
  -H "Content-Type: application/json" \
  -d '{"name":"My Campaign","concurrency_limit":5,"virtual_number":"+918012345678","inter_call_delay_ms":500}'

# 3. Check status
curl http://localhost:8000/campaign/status

# 4. Pause / Resume / Stop
curl -X POST http://localhost:8000/campaign/pause
curl -X POST http://localhost:8000/campaign/resume
curl -X POST http://localhost:8000/campaign/stop

# 5. Download results CSV
curl http://localhost:8000/campaign/results -o results.csv
```

---

## Key Files

| File | Purpose |
|---|---|
| `main.py` | FastAPI server, HTTP + WebSocket endpoints |
| **`livekit_handler.py`** | **LiveKit room management and audio streaming (NEW)** |
| `exotel_handler.py` | Manages Exotel WebSocket session per call (legacy) |
| `gemini_bridge.py` | Gemini Live API session, audio I/O, transcript accumulation |
| `audio_utils.py` | PCM resampling (8↔16↔24 kHz) |
| `sales_prompt.py` | System prompt + sales script builder |
| `outbound.py` | Exotel Make-a-Call API wrapper (legacy) |
| `config.py` | All config from environment variables |
| `campaign_models.py` | `Lead`, `Campaign`, `LeadStatus`, `CampaignStatus` data models |
| `csv_parser.py` | CSV upload parser → `ParseResult` |
| `lead_store.py` | In-memory lead store with status tracking |
| `classifier.py` | Keyword-based transcript classifier (Hot/Warm/Cold/Not_Picked) |
| `campaign_orchestrator.py` | Async dispatch loop, pause/resume/stop, results export |
| `leads_sample.csv` | Sample CSV for testing the bulk dialer |
| `frontend/` | Modern React UI for campaign management |
| **`livekit_client.html`** | **Web client for testing LiveKit integration (NEW)** |
| **`LIVEKIT_QUICKSTART.md`** | **5-minute setup guide (NEW)** |
| **`LIVEKIT_SETUP.md`** | **Detailed LiveKit setup guide (NEW)** |
| **`LIVEKIT_MIGRATION.md`** | **Migration guide from Exotel (NEW)** |

## Campaign API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/campaign/upload` | Upload CSV → `{campaign_id, lead_count, skipped}` |
| `POST` | `/campaign/start` | Start campaign with config |
| `POST` | `/campaign/pause` | Pause (in-progress calls finish) |
| `POST` | `/campaign/resume` | Resume after pause |
| `POST` | `/campaign/stop` | Stop and cancel remaining leads |
| `GET` | `/campaign/status` | Full status + per-lead data + stats |
| `GET` | `/campaign/results` | Download results as CSV |
| `GET` | `/dashboard` | Live monitoring dashboard |

## Lead Classification

After each call, the transcript is analysed for outcome keywords:

| Keyword in transcript | Classification |
|-----------------------|----------------|
| `INTERESTED` or `DEMO_BOOKED` | Hot |
| `CALLBACK_REQUESTED` or `NOT_NOW` | Warm |
| `NOT_INTERESTED` | Cold |
| Call not answered | Not_Picked |
| No keyword found | Cold (default) |

## CSV Format

Minimum required columns: `phone`, `name`. All other columns are preserved as metadata.

```csv
phone,name,company,notes
+919876543210,Rahul Sharma,Acme Corp,Downloaded free trial
+919876543211,Priya Patel,Beta Solutions,Attended webinar
```

---

## Audio Format Chain

| Stage | Format |
|---|---|
| Exotel → Bot | 8 kHz, 16-bit, mono PCM, base64 |
| Bot → Gemini | 16 kHz, 16-bit, mono PCM |
| Gemini → Bot | 24 kHz, 16-bit, mono PCM |
| Bot → Exotel | 8 kHz, 16-bit, mono PCM, base64 |

---

## Cost Estimate (per 5-min call)

### LiveKit (Recommended)
| Component | Cost |
|---|---|
| Gemini 2.5 Flash audio input | ~$0.075 |
| Gemini 2.5 Flash text output | ~$0.013 |
| LiveKit Cloud (10MB @ $0.10/GB) | ~$0.001 |
| **Total per call** | **~$0.09** |

### Exotel (Legacy)
| Component | Cost |
|---|---|
| Gemini 2.5 Flash audio input | ~$0.075 |
| Gemini 2.5 Flash text output | ~$0.013 |
| Exotel call charges (India) | ~₹0.50–2.00 |
| **Total per call** | **~$0.09 + ₹1** |

**💰 Cost Savings: ~96% with LiveKit!**

---

## Platform Comparison

| Feature | LiveKit | Exotel |
|---------|---------|--------|
| **Platforms** | Web, iOS, Android, Desktop | Phone only |
| **Audio Quality** | HD (48kHz) | Phone (8kHz) |
| **Latency** | 50-150ms | 200-500ms |
| **Cost (5 min)** | ~$0.09 | ~$0.09 + ₹1 |
| **Recording** | Built-in, free | Extra cost |
| **Scalability** | Unlimited | Limited |
| **Setup Time** | 5 minutes | 1-2 days |

---

## Exotel Setup Notes (Legacy)
- Enable **AgentStream / Voicebot Applet** on your account (email hello@exotel.com)
- Complete KYC before streaming is activated
- Use **Mumbai (Veeno) instance** for India
- Sessions max at **60 minutes** on Exotel side, **10 minutes** on Gemini side
  → Implement session handoff for longer calls
