# Exotel WebSocket Connection Fix

## Problem Identified

The system stopped working after implementing tasks from `tasks.md`. The root cause was:

**The `/exoml` endpoint was changed to return JSON instead of XML**, which broke Exotel's ability to connect to the WebSocket.

## What Was Fixed

### 1. Fixed `/exoml` Endpoint (main.py)
Changed from returning JSON to returning proper ExoML XML format:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Voicebot url="wss://marci-unharked-sally.ngrok-free.dev/ws/exotel?lead_name=...&..." />
</Response>
```

### 2. Added Query Parameters
The WebSocket URL now includes lead information as query parameters so the agent can personalize the greeting.

### 3. Added Logging
Enhanced WebSocket handler logging to track connections and debug issues.

## Required Configuration Changes

### ⚠️ CRITICAL: Update Exotel App Configuration

You need to update your Exotel app "flow" configuration:

**WRONG (Current):**
```
Voicebot URL: wss://marci-unharked-sally.ngrok-free.dev/ws/exotel
```

**CORRECT (Should be):**
```
Voicebot URL: https://marci-unharked-sally.ngrok-free.dev/exoml
```

### How to Update:

1. Go to Exotel Dashboard → AppBazaar
2. Find your "flow" app
3. Edit the Voicebot applet
4. Change the URL from `wss://...` to `https://...exoml`
5. Save the configuration

## Why This Matters

The correct flow is:

1. **Call initiated** → Exotel receives call
2. **Exotel calls your HTTP endpoint** → `GET https://your-domain/exoml`
3. **Your server returns XML** → Contains WebSocket URL with parameters
4. **Exotel reads XML** → Extracts WebSocket URL
5. **Exotel connects to WebSocket** → `wss://your-domain/ws/exotel?lead_name=...`
6. **Agent conversation starts** → Gemini handles the call

If you point directly to the WebSocket URL, Exotel doesn't know how to connect because:
- It expects an HTTP endpoint first
- It needs the XML response to understand the configuration
- The dynamic parameters (lead name, etc.) can't be passed

## Testing the Fix

### Test 1: Verify /exoml Endpoint
```bash
curl http://localhost:8000/exoml?lead_name=Tanishq
```

Should return XML (not JSON):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Voicebot url="wss://..." />
</Response>
```

### Test 2: Make a Test Call
```bash
cd voice_agent
python test_call.py 9098471077 Tanishq
```

This will:
1. Place an outbound call via Exotel API
2. Exotel will call your `/exoml` endpoint
3. Your server returns XML with WebSocket URL
4. Exotel connects to WebSocket
5. Call proceeds with Riya (the agent)

### Test 3: Check Logs

**Server logs** (should show):
```
INFO: WebSocket connection accepted from ...
INFO: WebSocket handler initialized for lead: Tanishq
INFO: [call_sid] Call started. Lead: Tanishq
```

**ngrok logs** (should show):
```
GET /exoml?lead_name=Tanishq&...
WebSocket upgrade /ws/exotel?lead_name=Tanishq&...
```

## What to Watch For

### ✅ Success Indicators:
- Phone rings
- Server logs show "WebSocket connection accepted"
- Server logs show "Call started. Lead: [name]"
- ngrok shows both `/exoml` GET request AND WebSocket upgrade
- Agent (Riya) speaks: "Hello, kya main [name] se baat kar rahi hoon?"

### ❌ Failure Indicators:
- Phone rings but immediately hangs up → Exotel can't connect to WebSocket
- No WebSocket logs → Exotel isn't calling your server
- Only `/call-status` in ngrok logs → Exotel is calling status callback but not WebSocket

## Additional Notes

### Why It Was Working Yesterday

Before the tasks.md changes, the `/exoml` endpoint was returning XML. During the implementation of the new features (auth middleware, rate limiter, etc.), the endpoint was accidentally changed to return JSON for testing purposes and never reverted.

### Auth & Rate Limiting

Both middleware components correctly skip:
- `/exoml` endpoint (no auth required)
- `/ws/*` paths (WebSocket connections)
- `/call-status` (Exotel callback)

So they won't interfere with Exotel connections.

### Ngrok vs Cloudflare

You switched to ngrok for better WebSocket support, which was the right decision. ngrok handles WebSocket upgrades properly.

## Next Steps

1. **Update Exotel app configuration** (change URL from `wss://` to `https://...exoml`)
2. **Restart server** (already done)
3. **Make a test call** using `test_call.py`
4. **Watch the logs** to confirm WebSocket connection
5. **Verify agent speaks** the correct greeting in Hindi

If the call still doesn't work after updating the Exotel configuration, check:
- Is ngrok still running? (`ngrok http 8000`)
- Is the ngrok URL in `.env` correct?
- Does the Exotel app have the correct ExoPhone assigned?
- Is the Voicebot feature enabled on your Exotel account?
