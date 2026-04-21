"""
GeminiBridge -- manages a single Gemini Live API session for one phone call.
"""
import asyncio
import base64
import logging
from typing import Optional

# Guard allows unittest.mock.patch("gemini_bridge.genai") to survive importlib.reload()
if "genai" not in globals():
    from google import genai  # noqa: F401  (re-exported for patching)

if "upsample_8k_to_16k" not in globals():
    from audio_utils import upsample_8k_to_16k, downsample_24k_to_8k
# Guard config imports so patches survive importlib.reload()
if "GEMINI_API_KEY" not in globals():
    from config import (
        GEMINI_API_KEY,
        GEMINI_MODEL,
        USE_VERTEX_AI,
        VERTEX_PROJECT_ID,
        VERTEX_LOCATION,
        GOOGLE_APPLICATION_CREDENTIALS,
        AGENT_NAME,
        COMPANY_NAME,
    )
if "build_system_prompt" not in globals():
    from sales_prompt import build_system_prompt
if "extract_from_chunk" not in globals():
    from extractor import extract_from_chunk
if "LeadInfo" not in globals():
    from lead_info import LeadInfo, upsert as upsert_info

logger = logging.getLogger(__name__)

_OUTPUT_QUEUE_MAXSIZE = 100


class GeminiBridge:
    def __init__(
        self,
        call_sid: str,
        lead_id: str = "",
        lead_name: str = "there",
        lead_company: str = "",
        call_context: str = "",
        outbound_intro: Optional[str] = None,
        initial_info: Optional[LeadInfo] = None,
    ):
        self.call_sid       = call_sid
        self.lead_id        = lead_id
        self.lead_name      = lead_name
        self.lead_company   = lead_company
        self.call_context   = call_context
        self.outbound_intro = outbound_intro

        # Live collected info — updated as transcript chunks arrive
        self.collected_info: LeadInfo = initial_info or LeadInfo(lead_id=lead_id)

        # Initialize Gemini client based on configuration
        if USE_VERTEX_AI:
            # Set credentials if provided
            if GOOGLE_APPLICATION_CREDENTIALS:
                import os
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS
            
            self._client = genai.Client(
                vertexai=True,
                project=VERTEX_PROJECT_ID,
                location=VERTEX_LOCATION
            )
            logger.info(f"[{call_sid}] Using Vertex AI (Project: {VERTEX_PROJECT_ID}, Location: {VERTEX_LOCATION})")
        else:
            self._client = genai.Client(
                api_key=GEMINI_API_KEY,
                http_options={"api_version": "v1beta"},
            )
            logger.info(f"[{call_sid}] Using Gemini API Key")
        
        self._session = None
        self._task    = None

        self.output_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue(maxsize=_OUTPUT_QUEUE_MAXSIZE)
        self._active = False
        self.transcript_parts: list[str] = []

    async def start(self):
        system_prompt = build_system_prompt(
            lead_name=self.lead_name,
            lead_company=self.lead_company,
            call_context=self.call_context,
            collected_info=self.collected_info,
        )
        _types = genai.types
        config = _types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=_types.Content(
                role="user",
                parts=[_types.Part(text=system_prompt)],
            ),
            speech_config=_types.SpeechConfig(
                voice_config=_types.VoiceConfig(
                    prebuilt_voice_config=_types.PrebuiltVoiceConfig(voice_name="Aoede")
                )
            ),
            media_resolution="MEDIA_RESOLUTION_MEDIUM",
            context_window_compression=_types.ContextWindowCompressionConfig(
                trigger_tokens=104857,
                sliding_window=_types.SlidingWindow(target_tokens=52428),
            ),
        )
        self._ctx = self._client.aio.live.connect(model=GEMINI_MODEL, config=config)
        self._session = await self._ctx.__aenter__()
        self._active = True
        logger.info(f"[{self.call_sid}] Gemini session opened.")

        # Start the receive loop first
        self._task = asyncio.create_task(self._receive_loop())

        # Send initial greeting to trigger Gemini to speak
        if self.outbound_intro:
            initial_message = f"(Start the call. Say exactly: {self.outbound_intro})"
        else:
            # Default greeting for all calls
            initial_message = f"(Greet the caller warmly and introduce yourself as {AGENT_NAME} from {COMPANY_NAME}. Ask how you can help them today.)"
        
        logger.info(f"[{self.call_sid}] Sending initial prompt to Gemini...")
        await self._session.send_realtime_input(text=initial_message)

    async def stop(self):
        self._active = False
        try:
            self.output_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        # Drain any remaining audio after task is done
        while not self.output_queue.empty():
            self.output_queue.get_nowait()
        if self._session:
            try:
                await self._ctx.__aexit__(None, None, None)
            except Exception:
                pass
        logger.info(f"[{self.call_sid}] Gemini session closed.")

    async def send_audio(self, pcm_8k: bytes):
        if not self._active or not self._session:
            return
        pcm_16k = await upsample_8k_to_16k(pcm_8k)
        await self._session.send_realtime_input(
            audio=genai.types.Blob(data=pcm_16k, mime_type="audio/pcm;rate=16000")
        )

    async def send_interrupt(self):
        if not self._active or not self._session:
            return
        # Drain buffered output audio immediately
        while not self.output_queue.empty():
            self.output_queue.get_nowait()
        try:
            silent = genai.types.Blob(data=bytes(320), mime_type="audio/pcm;rate=16000")
            await self._session.send_realtime_input(audio=silent)
        except Exception as e:
            logger.warning(f"[{self.call_sid}] Interrupt send failed: {e}")

    async def _receive_loop(self):
        try:
            while self._active:
                turn = self._session.receive()
                async for response in turn:
                    if not self._active:
                        break

                    # Audio: response.data is raw PCM bytes at 24kHz
                    if response.data:
                        raw_pcm = response.data
                        if isinstance(raw_pcm, str):
                            raw_pcm = base64.b64decode(raw_pcm)
                        pcm_8k = await downsample_24k_to_8k(bytes(raw_pcm))
                        try:
                            self.output_queue.put_nowait(pcm_8k)
                        except asyncio.QueueFull:
                            logger.warning(f"[{self.call_sid}] Audio queue full, dropping chunk")

                    # Text transcript
                    if response.text:
                        text = response.text
                        logger.info(f"[{self.call_sid}] Transcript: {text}")
                        self.transcript_parts.append(text)
                        if self.lead_id:
                            chunk_info = extract_from_chunk(self.lead_id, text)
                            self._merge_info(chunk_info)
                            upsert_info(self.collected_info)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{self.call_sid}] Gemini receive error: {e}", exc_info=True)
        finally:
            try:
                self.output_queue.put_nowait(None)
            except asyncio.QueueFull:
                pass

    def full_transcript(self) -> str:
        return " ".join(self.transcript_parts)

    def _merge_info(self, chunk: LeadInfo) -> None:
        """Merge newly extracted fields into the live collected_info snapshot."""
        info = self.collected_info
        if chunk.budget_min is not None:
            info.budget_min = chunk.budget_min
        if chunk.budget_max is not None:
            info.budget_max = chunk.budget_max
        if chunk.location is not None:
            info.location = chunk.location
        if chunk.timeline is not None:
            info.timeline = chunk.timeline
        if chunk.property_type is not None:
            info.property_type = chunk.property_type
        if chunk.bhk is not None:
            info.bhk = chunk.bhk
        if chunk.team_size is not None:
            info.team_size = chunk.team_size
        if chunk.current_crm is not None:
            info.current_crm = chunk.current_crm
        if chunk.pain_points:
            for p in chunk.pain_points:
                if p not in info.pain_points:
                    info.pain_points.append(p)
        if chunk.callback_time is not None:
            info.callback_time = chunk.callback_time
        if chunk.demo_requested:
            info.demo_requested = True
