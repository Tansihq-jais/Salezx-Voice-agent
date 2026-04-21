"""Central configuration — loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini / Vertex AI ────────────────────────────────────────────────────────
USE_VERTEX_AI               = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
GEMINI_API_KEY              = os.getenv("GEMINI_API_KEY", "")
VERTEX_PROJECT_ID           = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION             = os.getenv("VERTEX_LOCATION", "us-central1")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GEMINI_MODEL                = "models/gemini-3.1-flash-live-preview"

# ── LiveKit ───────────────────────────────────────────────────────────────────
USE_LIVEKIT        = os.getenv("USE_LIVEKIT", "false").lower() == "true"
LIVEKIT_URL        = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY    = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# ── Exotel ────────────────────────────────────────────────────────────────────
EXOTEL_API_KEY   = os.getenv("EXOTEL_API_KEY", "")
EXOTEL_API_TOKEN = os.getenv("EXOTEL_API_TOKEN", "")
EXOTEL_SID       = os.getenv("EXOTEL_SID", "")
EXOTEL_CALLER_ID = os.getenv("EXOTEL_CALLER_ID", "")
EXOTEL_SUBDOMAIN = os.getenv("EXOTEL_SUBDOMAIN", "api.in.exotel.com")

# ── MongoDB (shared CRM + multi-agent) ───────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI", "")
# Identifies which client/tenant this agent instance belongs to.
# Set a unique value per client deployment (e.g. "client_acme", "client_xyz").
CLIENT_ID   = os.getenv("CLIENT_ID", "default")

# ── PostgreSQL (Neon) — campaigns, leads, billing ────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Billing ───────────────────────────────────────────────────────────────────
# Tiered INR pricing is defined in billing.py (₹10 / ₹8 / ₹6.5 per min).
# No env-var overrides needed — tiers are fixed by contract.

# ── Server ────────────────────────────────────────────────────────────────────
SERVER_HOST    = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT    = int(os.getenv("SERVER_PORT", "8000"))
SERVER_WORKERS = int(os.getenv("SERVER_WORKERS", "1"))
PUBLIC_URL     = os.getenv("PUBLIC_URL", "http://localhost:8000")

# ── Agent persona ─────────────────────────────────────────────────────────────
AGENT_NAME     = os.getenv("AGENT_NAME",    "Priya")
COMPANY_NAME   = os.getenv("COMPANY_NAME",  "TechVision Solutions")
PRODUCT_NAME   = os.getenv("PRODUCT_NAME",  "CloudPro CRM")
AGENT_LANGUAGE = os.getenv("AGENT_LANGUAGE", "en-IN")
