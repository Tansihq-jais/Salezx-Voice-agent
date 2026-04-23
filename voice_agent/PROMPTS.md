# Voice Agent Prompt System

The voice agent now supports multiple prompt types for different call scenarios. Each prompt type has its own personality, call flow, and hard rules tailored to the specific situation.

## Available Prompt Types

### 1. **sales** (Default)
Initial outbound or inbound sales calls for cars and insurance.

**Key characteristics:**
- Confirms caller identity first
- Explores car/insurance needs
- Qualifies budget, timeline, location
- Handles objections
- Books showroom visits or callbacks

**Use when:**
- Making cold outbound calls
- Receiving inbound inquiries
- First-time contact with a lead

**Example API call:**
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Rahul",
    "lead_company": "Acme Ltd",
    "prompt_type": "sales"
  }'
```

---

### 2. **feedback**
Post-purchase or post-call feedback collection.

**Key characteristics:**
- Warm and appreciative tone
- Focuses on customer experience
- Collects satisfaction feedback
- Identifies improvement areas
- Explores referral opportunities

**Use when:**
- Following up after a purchase
- Collecting feedback on service quality
- Asking for testimonials or referrals
- Post-call satisfaction surveys

**Example API call:**
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Rahul",
    "prompt_type": "feedback"
  }'
```

---

### 3. **insurance_only**
Insurance-focused calls (not tied to car sales).

**Key characteristics:**
- Explains comprehensive vs third-party coverage
- Focuses on insurance benefits and protection
- Handles renewal opportunities
- Provides quotes
- Reassuring tone about coverage

**Use when:**
- Calling specifically about insurance
- Handling insurance renewals
- Selling standalone insurance policies
- Explaining coverage options

**Example API call:**
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Priya",
    "prompt_type": "insurance_only"
  }'
```

---

### 4. **followup**
Follow-up calls to previous leads.

**Key characteristics:**
- Familiar, casual tone
- Recalls previous conversation
- Checks on decision progress
- Provides new information or offers
- Moves toward next step

**Use when:**
- Calling back a lead who said "let me think"
- Checking on decision status
- Providing promised information
- Moving stalled deals forward

**Example API call:**
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Rahul",
    "call_context": "Following up on Maruti Swift interest",
    "prompt_type": "followup"
  }'
```

---

### 5. **objection**
Handling specific objections or concerns.

**Key characteristics:**
- Empathetic and understanding
- Validates concerns
- Provides solutions
- Builds confidence with social proof
- Escalates if needed

**Use when:**
- Lead has specific concerns (price, delivery, etc.)
- Handling competitor comparisons
- Addressing trust or quality concerns
- Resolving payment or timeline issues

**Example API call:**
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Rahul",
    "call_context": "Lead concerned about delivery timeline",
    "prompt_type": "objection"
  }'
```

---

### 6. **callback**
Rescheduled callback calls.

**Key characteristics:**
- Acknowledges scheduled callback
- Recalls previous conversation context
- Continues from where you left off
- Delivers promised information
- Moves to next step

**Use when:**
- Calling back at a scheduled time
- Lead specifically requested a callback
- Continuing a previous conversation
- Delivering promised quotes or information

**Example API call:**
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Rahul",
    "call_context": "Callback for Hyundai Creta quote",
    "prompt_type": "callback"
  }'
```

---

## Implementation Details

### Code Structure

The prompt system is implemented in `prompts.py`:

```python
from prompts import build_system_prompt, PromptType, build_outbound_intro

# Build a system prompt for a specific scenario
prompt = build_system_prompt(
    prompt_type="feedback",
    lead_name="Rahul",
    lead_company="Acme Ltd",
    call_context="Post-purchase feedback",
    collected_info=lead_info_object
)

# Build an outbound intro for a specific scenario
intro = build_outbound_intro(
    lead_name="Rahul",
    prompt_type="feedback"
)
```

### Integration Points

1. **API Layer** (`main.py`):
   - `OutboundCallRequest` now includes `prompt_type` field
   - `trigger_outbound()` passes `prompt_type` to `make_outbound_call()`

2. **Outbound Handler** (`outbound.py`):
   - `make_outbound_call()` accepts `prompt_type` parameter
   - Passes it through to the WebSocket URL

3. **WebSocket Handler** (`exotel_handler.py`):
   - `ExotelCallHandler` receives `prompt_type`
   - Passes it to `GeminiBridge`

4. **Gemini Bridge** (`gemini_bridge.py`):
   - `GeminiBridge` accepts `prompt_type` parameter
   - Uses it when building the system prompt

### Prompt Components

Each prompt type consists of:

1. **Personality** - How the agent should behave and communicate
2. **Call Structure** - Step-by-step flow for the conversation
3. **Hard Rules** - Non-negotiable guidelines and constraints

All prompts share:
- **Business Context** - GrabYourCar company information
- **Lead Information** - Dynamically collected data about the lead

---

## Usage Examples

### Example 1: Initial Sales Call
```python
# Trigger an outbound sales call
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Rahul Kumar",
  "lead_company": "Tech Solutions",
  "call_context": "Interested in new car",
  "prompt_type": "sales"
}
```

### Example 2: Feedback Collection
```python
# Collect feedback after purchase
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Priya Sharma",
  "prompt_type": "feedback"
}
```

### Example 3: Insurance Follow-up
```python
# Follow up on insurance renewal
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Amit Patel",
  "call_context": "Insurance renewal - Maruti Swift",
  "prompt_type": "insurance_only"
}
```

### Example 4: Objection Handling
```python
# Handle price objection
POST /trigger-outbound
{
  "to": "+919876543210",
  "from_number": "1234567890",
  "lead_name": "Rahul",
  "call_context": "Lead concerned about premium pricing",
  "prompt_type": "objection"
}
```

---

## Prompt Type Decision Tree

Use this flowchart to choose the right prompt type:

```
Is this a new lead or first contact?
├─ YES → "sales"
└─ NO → Is this about feedback/satisfaction?
    ├─ YES → "feedback"
    └─ NO → Is this specifically about insurance?
        ├─ YES → "insurance_only"
        └─ NO → Is this a scheduled callback?
            ├─ YES → "callback"
            └─ NO → Is the lead raising objections?
                ├─ YES → "objection"
                └─ NO → "followup"
```

---

## Customization

To add a new prompt type:

1. Define personality, call structure, and hard rules in `prompts.py`
2. Add to `_get_prompt_components()` function
3. Add intro text to `build_outbound_intro()` function
4. Update `PromptType` literal type
5. Test with API calls

Example:
```python
# In prompts.py

_CUSTOM_PERSONALITY = """..."""
_CUSTOM_CALL_STRUCTURE = """..."""
_CUSTOM_HARD_RULES = """..."""

# Add to _get_prompt_components()
"custom": (_CUSTOM_PERSONALITY, _CUSTOM_CALL_STRUCTURE, _CUSTOM_HARD_RULES),

# Add to build_outbound_intro()
"custom": f"Hello {lead_name}! Custom intro here...",
```

---

## Monitoring & Analytics

Each call tracks its prompt type for analytics:

- **Call outcome tracking** varies by prompt type
- **Sales**: INTERESTED, NOT_NOW, NOT_INTERESTED, CALLBACK_REQUESTED, VISIT_BOOKED, QUOTE_SENT
- **Feedback**: POSITIVE_FEEDBACK, MIXED_FEEDBACK, NEGATIVE_FEEDBACK, REFERRAL_INTERESTED
- **Insurance**: INTERESTED_COMPREHENSIVE, INTERESTED_THIRD_PARTY, RENEWAL_INTERESTED
- **Follow-up**: STILL_INTERESTED, MOVED_TO_COMPETITOR, TIMELINE_EXTENDED, READY_TO_VISIT, LOST_LEAD

---

## Best Practices

1. **Choose the right prompt type** - Accuracy matters for agent performance
2. **Provide context** - Use `call_context` to give the agent background
3. **Lead information** - Pass `collected_info` if you have previous data
4. **Test variations** - Try different prompt types to see what works best
5. **Monitor outcomes** - Track which prompt types convert best

---

## Troubleshooting

**Agent not following the right flow?**
- Check that `prompt_type` is being passed correctly through the API
- Verify the prompt type value matches one of the valid types
- Check logs for the "Prompt Type:" message

**Wrong intro message?**
- Ensure `prompt_type` is set before the call starts
- Check `build_outbound_intro()` for the correct intro text

**Lead information not being collected?**
- Verify `collected_info` is being passed to `build_system_prompt()`
- Check that lead fields are being extracted correctly

---

## Related Files

- `prompts.py` - Main prompt definitions and builders
- `gemini_bridge.py` - Integrates prompts with Gemini API
- `exotel_handler.py` - Passes prompt type through WebSocket
- `outbound.py` - Includes prompt type in outbound calls
- `main.py` - API endpoints for triggering calls
