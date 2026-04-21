"""
ExotelCallHandler — manages one bidirectional Exotel WebSocket session.

Protocol summary (Exotel → Bot):
  connected  →  websocket handshake confirmed
  start      →  call metadata + custom_parameters
  media      →  base64-encoded 8 kHz PCM audio chunk
  dtmf       →  keypress from caller
  stop       →  call ended

Protocol summary (Bot → Exotel):
  media      →  base64-encoded 8 kHz PCM audio chunk to play to caller
  mark       →  optional milestone marker
"""
import asyncio
import json
import logging
from typing import Optional

from starlette.websockets import WebSocketDisconnect

from audio_utils import b64_to_pcm, pcm_to_b64
from gemini_bridge import GeminiBridge

logger = logging.getLogger(__name__)


class ExotelCallHandler:
    def __init__(self, websocket, on_call_end=None, lead_id: str = "", initial_info=None):
        self.ws         = websocket
        self.call_sid   = "unknown"
        self.stream_sid = "unknown"
        self.bridge: Optional[GeminiBridge] = None
        self._sender_task = None
        self._on_call_end = on_call_end
        self._lead_id     = lead_id
        self._initial_info = initial_info

    async def run(self):
        """Main loop: receive messages from Exotel, dispatch to bridge."""
        try:
            while True:
                raw = await self.ws.receive_text()
                msg = json.loads(raw)
                event = msg.get("event", "")

                if event == "connected":
                    await self._on_connected(msg)
                elif event == "start":
                    await self._on_start(msg)
                elif event == "media":
                    await self._on_media(msg)
                elif event == "dtmf":
                    await self._on_dtmf(msg)
                elif event == "stop":
                    await self._on_stop(msg)
                    break
        except WebSocketDisconnect:
            logger.info(f"[{self.call_sid}] Connection closed normally.")
        except Exception as e:
            logger.exception(f"[{self.call_sid}] Unexpected error: {e}")
        finally:
            await self._cleanup()

    # ── Event handlers ────────────────────────────────────────────────────────
    async def _on_connected(self, msg: dict):
        logger.info(f"Exotel WebSocket connected. Protocol: {msg.get('protocol')}")

    async def _on_start(self, msg: dict):
        start = msg.get("start", {})
        self.call_sid   = start.get("callSid",   "unknown")
        self.stream_sid = start.get("streamSid", "unknown")
        custom          = start.get("customParameters", {})

        lead_name    = custom.get("lead_name",    "there")
        lead_company = custom.get("lead_company", "")
        call_context = custom.get("call_context", "")
        is_outbound  = custom.get("outbound",     "false").lower() == "true"

        logger.info(
            f"[{self.call_sid}] Call started. Lead: {lead_name} @ {lead_company}. "
            f"Outbound: {is_outbound}"
        )

        # Build outbound intro text if needed
        outbound_intro = None
        if is_outbound:
            from sales_prompt import build_outbound_intro
            outbound_intro = build_outbound_intro(lead_name)

        # Start Gemini session
        self.bridge = GeminiBridge(
            call_sid=self.call_sid,
            lead_id=self._lead_id,
            lead_name=lead_name,
            lead_company=lead_company,
            call_context=call_context,
            outbound_intro=outbound_intro,
            initial_info=self._initial_info,
        )
        await self.bridge.start()

        # Start the audio sender (Gemini → Exotel) as background task
        self._sender_task = asyncio.create_task(self._audio_sender())

    async def _on_media(self, msg: dict):
        """Forward caller audio to Gemini."""
        if not self.bridge:
            return
        payload = msg.get("media", {}).get("payload", "")
        if payload:
            pcm = b64_to_pcm(payload)
            await self.bridge.send_audio(pcm)

    async def _on_dtmf(self, msg: dict):
        """Handle DTMF keypresses (e.g. press 0 to escalate to human agent)."""
        digit = msg.get("dtmf", {}).get("digit", "")
        logger.info(f"[{self.call_sid}] DTMF received: {digit}")
        if digit == "0":
            # Interrupt Gemini and inject escalation message
            if self.bridge:
                await self.bridge.send_interrupt()

    async def _on_stop(self, msg: dict):
        logger.info(f"[{self.call_sid}] Call stopped by Exotel.")

    # ── Audio sender (Gemini → Exotel) ────────────────────────────────────────
    async def _audio_sender(self):
        """Drain bridge.output_queue and send audio back to Exotel."""
        if not self.bridge:
            return
        try:
            while True:
                chunk = await self.bridge.output_queue.get()
                if chunk is None:   # sentinel → session ended
                    break
                payload = pcm_to_b64(chunk)
                media_msg = {
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload},
                }
                await self.ws.send_text(json.dumps(media_msg))
        except Exception as e:
            logger.error(f"[{self.call_sid}] Audio sender error: {e}")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    async def _cleanup(self):
        if self._sender_task:
            self._sender_task.cancel()
        transcript = self.bridge.full_transcript() if self.bridge else ""
        collected_info = self.bridge.collected_info if self.bridge else None
        if self.bridge:
            await self.bridge.stop()
        if self._on_call_end:
            if asyncio.iscoroutinefunction(self._on_call_end):
                await self._on_call_end(self.call_sid, transcript, collected_info)
            else:
                self._on_call_end(self.call_sid, transcript, collected_info)
