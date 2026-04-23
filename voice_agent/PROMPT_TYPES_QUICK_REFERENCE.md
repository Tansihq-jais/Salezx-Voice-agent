# Prompt Types Quick Reference

## At a Glance

| Type | Purpose | Tone | Best For |
|------|---------|------|----------|
| **sales** | New lead acquisition | Friendly, exploratory | Cold calls, inbound inquiries |
| **feedback** | Post-purchase satisfaction | Warm, appreciative | After purchase, surveys |
| **insurance_only** | Insurance-focused | Reassuring, protective | Insurance renewals, standalone policies |
| **followup** | Continue previous conversation | Familiar, casual | "Let me think" leads, stalled deals |
| **objection** | Handle concerns | Empathetic, solution-focused | Price/delivery/trust concerns |
| **callback** | Scheduled callback | Punctual, respectful | Rescheduled calls, promised info |

---

## Quick API Examples

### Sales Call
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Rahul",
    "prompt_type": "sales"
  }'
```

### Feedback Call
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Priya",
    "prompt_type": "feedback"
  }'
```

### Insurance Call
```bash
curl -X POST http://localhost:8000/trigger-outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "from_number": "1234567890",
    "lead_name": "Amit",
    "prompt_type": "insurance_only"
  }'
```

### Follow-up Call
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

### Objection Handling
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

### Callback
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

## Call Flow Summaries

### Sales
1. Confirm identity
2. Introduce yourself
3. Ask open-ended question
4. Qualify (car, budget, location, timeline)
5. Pitch personalized offer
6. Handle objections
7. Get next step (visit/callback/quote)
8. Close warmly

### Feedback
1. Warm greeting
2. Thank for business
3. Ask about experience
4. Listen and acknowledge
5. Explore referral opportunity
6. Offer escalation if needed
7. Close with appreciation

### Insurance Only
1. Confirm identity
2. Ask about current car/insurance
3. Understand needs
4. Explain comprehensive vs third-party
5. Provide personalized quote
6. Handle objections
7. Get next step
8. Close with confidence

### Follow-up
1. Familiar greeting
2. Recap previous conversation
3. Check progress
4. Provide new value/info
5. Handle objections
6. Move to next step
7. Close professionally

### Objection
1. Acknowledge concern
2. Empathize
3. Clarify the issue
4. Address with solution
5. Build confidence
6. Move forward
7. Close supportively

### Callback
1. Acknowledge scheduled callback
2. Recall context
3. Continue conversation
4. Deliver promised info
5. Move to next step
6. Close professionally

---

## When to Use Each Type

**Use SALES when:**
- First contact with a lead
- Cold outbound call
- Inbound inquiry from website/ad
- Lead hasn't been contacted before

**Use FEEDBACK when:**
- Customer just purchased
- Want satisfaction survey
- Asking for testimonial/referral
- Post-call satisfaction check

**Use INSURANCE_ONLY when:**
- Calling specifically about insurance
- Insurance renewal time
- Lead only interested in insurance
- Selling standalone policy

**Use FOLLOWUP when:**
- Lead said "let me think"
- Previous call ended without decision
- Checking on decision progress
- Providing promised information

**Use OBJECTION when:**
- Lead has specific concern
- Handling price objection
- Addressing delivery concerns
- Comparing with competitor

**Use CALLBACK when:**
- Lead requested specific callback time
- Rescheduled call
- Continuing previous conversation
- Delivering promised quote/info

---

## Key Differences

### Sales vs Follow-up
- **Sales**: Exploratory, building interest from scratch
- **Follow-up**: Continuing momentum, moving stalled deal forward

### Sales vs Objection
- **Sales**: General pitch, handle objections as they come
- **Objection**: Focused on specific concern, solution-oriented

### Insurance_Only vs Sales
- **Insurance_Only**: Insurance is the focus, not car sales
- **Sales**: Car sales primary, insurance as add-on

### Feedback vs Sales
- **Feedback**: Customer already bought, gathering satisfaction
- **Sales**: Trying to make the sale

---

## Prompt Type Outcomes

Each prompt type tracks different outcomes:

**Sales outcomes:**
- INTERESTED
- NOT_NOW
- NOT_INTERESTED
- CALLBACK_REQUESTED
- VISIT_BOOKED
- QUOTE_SENT

**Feedback outcomes:**
- POSITIVE_FEEDBACK
- MIXED_FEEDBACK
- NEGATIVE_FEEDBACK
- REFERRAL_INTERESTED
- ESCALATION_NEEDED

**Insurance outcomes:**
- INTERESTED_COMPREHENSIVE
- INTERESTED_THIRD_PARTY
- RENEWAL_INTERESTED
- NOT_INTERESTED
- QUOTE_SENT

**Follow-up outcomes:**
- STILL_INTERESTED
- MOVED_TO_COMPETITOR
- TIMELINE_EXTENDED
- READY_TO_VISIT
- LOST_LEAD

**Objection outcomes:**
- OBJECTION_RESOLVED
- OBJECTION_PENDING
- ESCALATION_NEEDED
- LEAD_LOST

**Callback outcomes:**
- CALLBACK_SUCCESSFUL
- CALLBACK_RESCHEDULED
- LEAD_LOST
- NEXT_STEP_BOOKED

---

## Pro Tips

1. **Combine with context** - Use `call_context` to give agent background
2. **Test and measure** - Track which prompt types convert best
3. **Match the situation** - Wrong prompt type = wrong tone
4. **Provide lead info** - Pass previous data for better personalization
5. **Monitor logs** - Check "Prompt Type:" in logs to verify correct type is used

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Wrong intro message | Check `prompt_type` is passed to API |
| Agent not following flow | Verify `prompt_type` value is valid |
| Lead info not collected | Pass `collected_info` to `build_system_prompt()` |
| Unexpected tone | Ensure correct `prompt_type` for situation |

---

## File Locations

- **Prompt definitions**: `voice_agent/prompts.py`
- **Full documentation**: `voice_agent/PROMPTS.md`
- **API integration**: `voice_agent/main.py`
- **Outbound handler**: `voice_agent/outbound.py`
- **WebSocket handler**: `voice_agent/exotel_handler.py`
- **Gemini integration**: `voice_agent/gemini_bridge.py`
