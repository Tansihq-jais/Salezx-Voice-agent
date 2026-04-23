"""
Trigger an outbound call via Exotel Make-a-Call API.

Usage:
    from outbound import make_outbound_call
    await make_outbound_call(to="+919876543210", lead_name="Rahul", lead_company="Acme Ltd")
"""
import httpx
import logging
from config import (
    EXOTEL_API_KEY, EXOTEL_API_TOKEN, EXOTEL_SID,
    EXOTEL_SUBDOMAIN, EXOTEL_CALLER_ID, PUBLIC_URL
)

logger = logging.getLogger(__name__)

EXOTEL_CALL_URL = (
    f"https://{EXOTEL_API_KEY}:{EXOTEL_API_TOKEN}"
    f"@{EXOTEL_SUBDOMAIN}/v1/Accounts/{EXOTEL_SID}/Calls/connect"
)


async def make_outbound_call(
    to: str,
    from_: str = EXOTEL_CALLER_ID,
    lead_name: str = "there",
    lead_company: str = "",
    call_context: str = "",
    record: bool = True,
    prompt_type: str = "sales",
) -> dict:
    # Exotel requires 0XXXXXXXXXX format for Indian mobiles, not +91
    if to.startswith("+91"):
        to = "0" + to[3:]
    elif not to.startswith("0") and len(to) == 10:
        to = "0" + to
    """
    Place an outbound call. Exotel will connect to the caller and then
    open a WebSocket to our /ws/exotel endpoint with the custom parameters
    embedded, so GeminiBridge can personalize the pitch.
    """
    # The ExoML URL tells Exotel how to handle the call once connected.
    # It points to our /exoml endpoint which returns the Voicebot Applet XML.
    exoml_url = (
        f"{PUBLIC_URL}/exoml"
        f"?lead_name={lead_name}"
        f"&lead_company={lead_company}"
        f"&call_context={call_context}"
        f"&prompt_type={prompt_type}"
        f"&outbound=true"
    )

    # The Url must point to your Exotel app (flow) that has the Voicebot applet configured.
    # Format: http://my.exotel.in/exoml/start/<APP_ID>
    # The APP_ID is found in your Exotel Dashboard → AppBazaar → your voicebot app.
    # Your external /exoml endpoint is called BY Exotel once the voicebot applet runs —
    # it is NOT the Url you pass here.
    from config import EXOTEL_APP_ID
    exotel_app_url = f"http://my.exotel.in/exoml/start/{EXOTEL_APP_ID}"

    payload = {
        "From":           to,             # customer number — Exotel calls this first
        "CallerId":       from_,          # your Exotel virtual number
        "Url":            exotel_app_url, # your Exotel app/flow that has the Voicebot applet
        "CallType":       "trans",
        "Record":         "true" if record else "false",
        "StatusCallback": f"{PUBLIC_URL}/call-status",
        # Pass lead info as CustomField (max 3 params per Exotel docs)
        "CustomField":    f"lead_name={lead_name}&lead_company={lead_company}&outbound=true",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(EXOTEL_CALL_URL, data=payload)
        resp.raise_for_status()
        # Exotel returns XML, not JSON
        import re
        sid_match = re.search(r"<Sid>([^<]+)</Sid>", resp.text)
        call_sid = sid_match.group(1) if sid_match else "unknown"
        logger.info(f"Outbound call placed: {call_sid}")
        return {"call_sid": call_sid, "raw": resp.text}
