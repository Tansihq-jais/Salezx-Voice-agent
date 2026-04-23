"""
Examples of how to use the prompt system in your code.
"""

# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 1: Direct prompt building (for testing/debugging)
# ─────────────────────────────────────────────────────────────────────────────

from prompts import build_system_prompt, build_outbound_intro, PromptType
from lead_info import LeadInfo

# Build a sales prompt
sales_prompt = build_system_prompt(
    prompt_type="sales",
    lead_name="Rahul Kumar",
    lead_company="Tech Solutions",
    call_context="Interested in new car",
)
print("Sales Prompt:")
print(sales_prompt)
print("\n" + "="*80 + "\n")

# Build a feedback prompt
feedback_prompt = build_system_prompt(
    prompt_type="feedback",
    lead_name="Priya Sharma",
)
print("Feedback Prompt:")
print(feedback_prompt)
print("\n" + "="*80 + "\n")

# Build an insurance prompt with lead info
lead_info = LeadInfo(
    lead_id="lead_123",
    budget_min=500000,
    budget_max=800000,
    location="Gurgaon",
    timeline="This month",
    property_type="SUV",
)

insurance_prompt = build_system_prompt(
    prompt_type="insurance_only",
    lead_name="Amit Patel",
    collected_info=lead_info,
)
print("Insurance Prompt with Lead Info:")
print(insurance_prompt)
print("\n" + "="*80 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 2: Building outbound intros
# ─────────────────────────────────────────────────────────────────────────────

# Sales intro
sales_intro = build_outbound_intro("Rahul", prompt_type="sales")
print(f"Sales intro: {sales_intro}")

# Feedback intro
feedback_intro = build_outbound_intro("Priya", prompt_type="feedback")
print(f"Feedback intro: {feedback_intro}")

# Insurance intro
insurance_intro = build_outbound_intro("Amit", prompt_type="insurance_only")
print(f"Insurance intro: {insurance_intro}")

# Follow-up intro
followup_intro = build_outbound_intro("Rahul", prompt_type="followup")
print(f"Follow-up intro: {followup_intro}")

# Callback intro
callback_intro = build_outbound_intro("Rahul", prompt_type="callback")
print(f"Callback intro: {callback_intro}")

print("\n" + "="*80 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 3: Using with GeminiBridge (in your call handler)
# ─────────────────────────────────────────────────────────────────────────────

from gemini_bridge import GeminiBridge

async def start_sales_call():
    """Start a sales call with Gemini."""
    bridge = GeminiBridge(
        call_sid="call_12345",
        lead_id="lead_123",
        lead_name="Rahul Kumar",
        lead_company="Tech Solutions",
        call_context="Interested in new car",
        prompt_type="sales",  # ← Specify the prompt type
    )
    await bridge.start()
    return bridge


async def start_feedback_call():
    """Start a feedback collection call."""
    bridge = GeminiBridge(
        call_sid="call_12346",
        lead_id="lead_124",
        lead_name="Priya Sharma",
        prompt_type="feedback",  # ← Specify the prompt type
    )
    await bridge.start()
    return bridge


async def start_insurance_call():
    """Start an insurance-focused call."""
    bridge = GeminiBridge(
        call_sid="call_12347",
        lead_id="lead_125",
        lead_name="Amit Patel",
        prompt_type="insurance_only",  # ← Specify the prompt type
    )
    await bridge.start()
    return bridge


async def start_followup_call():
    """Start a follow-up call."""
    bridge = GeminiBridge(
        call_sid="call_12348",
        lead_id="lead_123",
        lead_name="Rahul Kumar",
        call_context="Following up on Maruti Swift interest",
        prompt_type="followup",  # ← Specify the prompt type
    )
    await bridge.start()
    return bridge


async def start_objection_call():
    """Start an objection handling call."""
    bridge = GeminiBridge(
        call_sid="call_12349",
        lead_id="lead_123",
        lead_name="Rahul Kumar",
        call_context="Lead concerned about delivery timeline",
        prompt_type="objection",  # ← Specify the prompt type
    )
    await bridge.start()
    return bridge


async def start_callback_call():
    """Start a callback call."""
    bridge = GeminiBridge(
        call_sid="call_12350",
        lead_id="lead_123",
        lead_name="Rahul Kumar",
        call_context="Callback for Hyundai Creta quote",
        prompt_type="callback",  # ← Specify the prompt type
    )
    await bridge.start()
    return bridge


print("\n" + "="*80 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 4: Using with ExotelCallHandler (in your WebSocket handler)
# ─────────────────────────────────────────────────────────────────────────────

from exotel_handler import ExotelCallHandler

async def handle_sales_websocket(websocket):
    """Handle a sales call WebSocket."""
    handler = ExotelCallHandler(
        websocket,
        lead_id="lead_123",
        prompt_type="sales",  # ← Specify the prompt type
    )
    await handler.run()


async def handle_feedback_websocket(websocket):
    """Handle a feedback collection WebSocket."""
    handler = ExotelCallHandler(
        websocket,
        lead_id="lead_124",
        prompt_type="feedback",  # ← Specify the prompt type
    )
    await handler.run()


async def handle_insurance_websocket(websocket):
    """Handle an insurance call WebSocket."""
    handler = ExotelCallHandler(
        websocket,
        lead_id="lead_125",
        prompt_type="insurance_only",  # ← Specify the prompt type
    )
    await handler.run()


print("\n" + "="*80 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 5: Making outbound calls with different prompt types
# ─────────────────────────────────────────────────────────────────────────────

from outbound import make_outbound_call

async def make_sales_call():
    """Make an outbound sales call."""
    result = await make_outbound_call(
        to="+919876543210",
        lead_name="Rahul Kumar",
        lead_company="Tech Solutions",
        call_context="Interested in new car",
        prompt_type="sales",  # ← Specify the prompt type
    )
    return result


async def make_feedback_call():
    """Make an outbound feedback collection call."""
    result = await make_outbound_call(
        to="+919876543210",
        lead_name="Priya Sharma",
        prompt_type="feedback",  # ← Specify the prompt type
    )
    return result


async def make_insurance_call():
    """Make an outbound insurance call."""
    result = await make_outbound_call(
        to="+919876543210",
        lead_name="Amit Patel",
        prompt_type="insurance_only",  # ← Specify the prompt type
    )
    return result


async def make_followup_call():
    """Make an outbound follow-up call."""
    result = await make_outbound_call(
        to="+919876543210",
        lead_name="Rahul Kumar",
        call_context="Following up on Maruti Swift interest",
        prompt_type="followup",  # ← Specify the prompt type
    )
    return result


async def make_objection_call():
    """Make an outbound objection handling call."""
    result = await make_outbound_call(
        to="+919876543210",
        lead_name="Rahul Kumar",
        call_context="Lead concerned about delivery timeline",
        prompt_type="objection",  # ← Specify the prompt type
    )
    return result


async def make_callback_call():
    """Make an outbound callback call."""
    result = await make_outbound_call(
        to="+919876543210",
        lead_name="Rahul Kumar",
        call_context="Callback for Hyundai Creta quote",
        prompt_type="callback",  # ← Specify the prompt type
    )
    return result


print("\n" + "="*80 + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 6: Using with FastAPI endpoints
# ─────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class OutboundCallRequest(BaseModel):
    to: str
    from_number: str
    lead_name: str = "there"
    lead_company: str = ""
    call_context: str = ""
    record: bool = True
    prompt_type: str = "sales"  # ← New field


@app.post("/trigger-outbound")
async def trigger_outbound(req: OutboundCallRequest):
    """Trigger an outbound call with specified prompt type."""
    result = await make_outbound_call(
        to=req.to,
        from_=req.from_number,
        lead_name=req.lead_name,
        lead_company=req.lead_company,
        call_context=req.call_context,
        record=req.record,
        prompt_type=req.prompt_type,  # ← Pass the prompt type
    )
    return {"status": "call_placed", "exotel_response": result}


# Example API calls:
"""
# Sales call
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Rahul",
  "prompt_type": "sales"
}

# Feedback call
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Priya",
  "prompt_type": "feedback"
}

# Insurance call
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Amit",
  "prompt_type": "insurance_only"
}

# Follow-up call
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Rahul",
  "call_context": "Following up on Maruti Swift interest",
  "prompt_type": "followup"
}

# Objection handling call
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Rahul",
  "call_context": "Lead concerned about delivery timeline",
  "prompt_type": "objection"
}

# Callback call
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Rahul",
  "call_context": "Callback for Hyundai Creta quote",
  "prompt_type": "callback"
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 7: Choosing prompt type based on lead status
# ─────────────────────────────────────────────────────────────────────────────

def get_prompt_type_for_lead(lead_status: str, lead_history: dict) -> str:
    """
    Determine the best prompt type based on lead status and history.
    
    Args:
        lead_status: Current status of the lead
        lead_history: Dictionary with lead history info
    
    Returns:
        The appropriate prompt type
    """
    if lead_status == "new":
        return "sales"
    
    elif lead_status == "purchased":
        return "feedback"
    
    elif lead_status == "insurance_renewal":
        return "insurance_only"
    
    elif lead_status == "callback_scheduled":
        return "callback"
    
    elif lead_status == "objection_raised":
        return "objection"
    
    elif lead_status == "interested_but_undecided":
        # Check how long since last contact
        days_since_contact = lead_history.get("days_since_contact", 0)
        if days_since_contact > 7:
            return "followup"
        else:
            return "sales"
    
    else:
        return "sales"  # Default


# Usage
lead_status = "interested_but_undecided"
lead_history = {"days_since_contact": 10}
prompt_type = get_prompt_type_for_lead(lead_status, lead_history)
print(f"Determined prompt type: {prompt_type}")


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 8: Logging and monitoring prompt types
# ─────────────────────────────────────────────────────────────────────────────

import logging

logger = logging.getLogger(__name__)


async def make_call_with_logging(
    to: str,
    lead_name: str,
    prompt_type: str = "sales",
):
    """Make a call and log the prompt type."""
    logger.info(f"Starting {prompt_type} call to {lead_name} ({to})")
    
    try:
        result = await make_outbound_call(
            to=to,
            lead_name=lead_name,
            prompt_type=prompt_type,
        )
        logger.info(f"Call placed successfully. Call SID: {result.get('call_sid')}")
        return result
    
    except Exception as e:
        logger.error(f"Failed to place {prompt_type} call: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# EXAMPLE 9: A/B testing different prompt types
# ─────────────────────────────────────────────────────────────────────────────

import random


async def make_call_with_ab_test(
    to: str,
    lead_name: str,
    test_group: str = "control",
):
    """
    Make a call with A/B testing of prompt types.
    
    Args:
        to: Phone number
        lead_name: Lead name
        test_group: "control" or "test"
    """
    if test_group == "control":
        prompt_type = "sales"
    else:
        # Test group: randomly choose between different prompt types
        prompt_type = random.choice(["sales", "followup"])
    
    logger.info(f"A/B test: {test_group} group using {prompt_type} prompt")
    
    result = await make_outbound_call(
        to=to,
        lead_name=lead_name,
        prompt_type=prompt_type,
    )
    
    # Log for analytics
    logger.info(f"Call result: {result}")
    
    return result


print("\n" + "="*80 + "\n")
print("All examples completed!")
