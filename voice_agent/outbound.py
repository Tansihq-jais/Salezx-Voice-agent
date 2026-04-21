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
    from_: str = EXOTEL_CALLER_ID,  # defaults to configured virtual number
    lead_name: str = "there",
    lead_company: str = "",
    call_context: str = "",
    record: bool = True,
) -> dict:
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
        f"&outbound=true"
    )

    payload = {
        "From":        from_,    # your Exotel virtual number
        "To":          to,       # destination number
        "CallerId":    from_,
        "Url":         exoml_url,
        "Record":      "true" if record else "false",
        "StatusCallback": f"{PUBLIC_URL}/call-status",
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
