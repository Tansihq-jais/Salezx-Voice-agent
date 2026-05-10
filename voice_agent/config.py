"""Central configuration — loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini / Vertex AI ────────────────────────────────────────────────────────
USE_VERTEX_AI                   = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
GEMINI_API_KEY                  = os.getenv("GEMINI_API_KEY", "")
VERTEX_PROJECT_ID               = os.getenv("VERTEX_PROJECT_ID", "")
VERTEX_LOCATION                 = os.getenv("VERTEX_LOCATION", "us-central1")
GOOGLE_APPLICATION_CREDENTIALS  = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GEMINI_MODEL                    = os.getenv("GEMINI_MODEL", "models/gemini-3.1-flash-live-preview")

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
EXOTEL_APP_ID    = os.getenv("EXOTEL_APP_ID", "")

# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGODB_URI", "")
CLIENT_ID   = os.getenv("CLIENT_ID", "default")

# ── PostgreSQL (Neon) ─────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ── Server ────────────────────────────────────────────────────────────────────
SERVER_HOST    = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT    = int(os.getenv("SERVER_PORT", "8000"))
SERVER_WORKERS = int(os.getenv("SERVER_WORKERS", "1"))
PUBLIC_URL     = os.getenv("PUBLIC_URL", "http://localhost:8000")

# ── Agent persona ─────────────────────────────────────────────────────────────
AGENT_NAME           = os.getenv("AGENT_NAME",    "Riya")
COMPANY_NAME         = os.getenv("COMPANY_NAME",  "GrabYourCar")
PRODUCT_NAME         = os.getenv("PRODUCT_NAME",  "GrabYourCar")
AGENT_LANGUAGE       = os.getenv("AGENT_LANGUAGE", "hi-IN")
GEMINI_VOICE         = os.getenv("GEMINI_VOICE",  "Sadachbia")
GEMINI_SPEAKING_RATE = float(os.getenv("GEMINI_SPEAKING_RATE", "1.0"))

# ── Business details (per-client configurable) ────────────────────────────────
COMPANY_LEGAL_NAME   = os.getenv("COMPANY_LEGAL_NAME",  "")
BUSINESS_TYPE        = os.getenv("BUSINESS_TYPE",       "new cars ki sales aur car insurance")
OPERATING_CITY       = os.getenv("OPERATING_CITY",      "Gurgaon")
COMPANY_EMAIL        = os.getenv("COMPANY_EMAIL",       "")
INDUSTRY_EXPERIENCE  = os.getenv("INDUSTRY_EXPERIENCE",  "7 saal")
SALES_MANAGER_NAME   = os.getenv("SALES_MANAGER_NAME",  "Manager")
PRODUCT_RESTRICTIONS = os.getenv("PRODUCT_RESTRICTIONS", "")
# Full override for business context — if set, replaces the auto-generated paragraph
BUSINESS_CONTEXT     = os.getenv("BUSINESS_CONTEXT",    "")

# Qualify questions — what to ask the lead about (one per line, shown as bullet points)
# Default is car-sales focused; change for your business domain
QUALIFY_QUESTIONS    = os.getenv(
    "QUALIFY_QUESTIONS",
    "Kaunsi car ya segment mein interest hai? (e.g. SUV, sedan, hatchback, specific model)\n"
    "Budget range kya hai?\n"
    "Delivery kahan chahiye?\n"
    "Kitne time mein lena chahte hain?\n"
    "Insurance bhi chahiye?"
)

# Pitch lines — 1-2 lines to pitch your product/service (shown as bullet points)
PITCH_LINES          = os.getenv(
    "PITCH_LINES",
    "Hum {OPERATING_CITY} mein hain, pan-India deliver karte hain — {INDUSTRY_EXPERIENCE} se trusted naam hai.\n"
    "New purchase ke saath best deals bhi milti hain — sab ek jagah."
)

# Opening question after intro — what to ask to start the sales conversation
OPENING_QUESTION     = os.getenv(
    "OPENING_QUESTION",
    "Kya aap {BUSINESS_TYPE} ke baare mein soch rahe hain?"
)

# ── CORS ──────────────────────────────────────────────────────────────────────
_origins_raw    = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _origins_raw.split(",") if o.strip()]
    if _origins_raw != "*"
    else ["*"]
)

# ── Calling window ────────────────────────────────────────────────────────────
CALLING_WINDOW_START = os.getenv("CALLING_WINDOW_START", "09:00")
CALLING_WINDOW_END   = os.getenv("CALLING_WINDOW_END",   "18:00")
CALLING_WINDOW_TZ    = os.getenv("CALLING_WINDOW_TZ",    "Asia/Kolkata")

# ── Campaign quality thresholds ───────────────────────────────────────────────
MIN_CONNECTION_RATE = float(os.getenv("MIN_CONNECTION_RATE", "0.3"))
