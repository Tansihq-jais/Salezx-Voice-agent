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
        GEMINI_VOICE,
        USE_VERTEX_AI,
        VERTEX_PROJECT_ID,
        VERTEX_LOCATION,
        GOOGLE_APPLICATION_CREDENTIALS,
        AGENT_NAME,
        COMPANY_NAME,
        AGENT_LANGUAGE,
        GEMINI_SPEAKING_RATE,
    )
if "build_system_prompt" not in globals():
    from prompts import build_system_prompt, PromptType
if "extract_from_chunk" not in globals():
    from extractor import extract_from_chunk
if "LeadInfo" not in globals():
    from lead_info import LeadInfo, upsert as upsert_info

logger = logging.getLogger(__name__)

_OUTPUT_QUEUE_MAXSIZE = 100

# Module-level flag — can be hot-patched by the settings API without a reload
_AFFECTIVE_DIALOG: bool = True


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
        prompt_type: "PromptType" = "sales",
    ):
        self.call_sid       = call_sid
        self.lead_id        = lead_id
        self.lead_name      = lead_name
        self.lead_company   = lead_company
        self.call_context   = call_context
        self.outbound_intro = outbound_intro
        self.prompt_type    = prompt_type

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
        self.on_hangup: Optional[asyncio.Event] = asyncio.Event()  # set when agent wants to hang up

    async def start(self, send_greeting: bool = True):
        # Pool-warm sessions use the prompt_type passed in (default "feedback").
        # This avoids the large runtime override that causes speaking delay.
        if self.call_sid == "pool-warm":
            system_prompt = build_system_prompt(
                prompt_type=self.prompt_type,
                lead_name="there",
            )
        else:
            system_prompt = build_system_prompt(
                prompt_type=self.prompt_type,
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
                    prebuilt_voice_config=_types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE)
                ),
                language_code=AGENT_LANGUAGE,
            ),
            # Transcribe both agent output and customer input so transcripts are captured
            output_audio_transcription=_types.AudioTranscriptionConfig(),
            input_audio_transcription=_types.AudioTranscriptionConfig(),
            # ── Barge-in / turn-taking ────────────────────────────────────────
            # START_SENSITIVITY_HIGH  — detect user speech quickly so agent
            #   stops talking the moment the caller starts.
            # END_SENSITIVITY_HIGH    — wait until the caller has clearly
            #   finished before Gemini responds (avoids cutting in mid-sentence).
            # silence_duration_ms=2000 — 2 s of silence required before Gemini
            #   considers the caller done; gives room for natural pauses.
            # prefix_padding_ms=300   — capture the first syllable reliably.
            realtime_input_config=_types.RealtimeInputConfig(
                automatic_activity_detection=_types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=_types.StartSensitivity.START_SENSITIVITY_HIGH,
                    end_of_speech_sensitivity=_types.EndSensitivity.END_SENSITIVITY_HIGH,
                    prefix_padding_ms=300,
                    silence_duration_ms=2000,  # wait 2 s of silence before replying
                ),
                turn_coverage=_types.TurnCoverage.TURN_INCLUDES_ALL_INPUT,
            ),
            media_resolution="MEDIA_RESOLUTION_MEDIUM",
            context_window_compression=_types.ContextWindowCompressionConfig(
                trigger_tokens=104857,
                sliding_window=_types.SlidingWindow(target_tokens=52428),
            ),
        )
        self._ctx     = self._client.aio.live.connect(model=GEMINI_MODEL, config=config)
        self._session = await self._ctx.__aenter__()
        self._active  = True
        logger.info(f"[{self.call_sid}] Gemini session opened.")

        self._task = asyncio.create_task(self._receive_loop())

        if send_greeting:
            if self.outbound_intro:
                msg = f"(Start the call. Say exactly: {self.outbound_intro})"
            else:
                import config as _cfg
                msg = (
                    f"(Greet the caller warmly and introduce yourself as {_cfg.AGENT_NAME} "
                    f"from {_cfg.COMPANY_NAME}. Ask how you can help them today.)"
                )
            logger.info(f"[{self.call_sid}] Sending greeting to Gemini...")
            await self._session.send_realtime_input(text=msg)

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
        # Drain buffered output audio immediately so no stale agent audio plays
        drained = 0
        while not self.output_queue.empty():
            self.output_queue.get_nowait()
            drained += 1
        if drained:
            logger.info(f"[{self.call_sid}] Manual interrupt — drained {drained} audio chunks")
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

                    # ── Barge-in: customer started speaking mid-agent-turn ──
                    # Gemini sets server_content.interrupted = True and stops
                    # generating. We drain the output queue so no stale agent
                    # audio plays over the customer's voice.
                    if getattr(response, "server_content", None):
                        if getattr(response.server_content, "interrupted", False):
                            drained = 0
                            while not self.output_queue.empty():
                                self.output_queue.get_nowait()
                                drained += 1
                            if drained:
                                logger.info(f"[{self.call_sid}] Barge-in detected — drained {drained} audio chunks")
                            continue  # skip to next response, don't process audio

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

                    # Text transcript (agent output)
                    if response.text:
                        text = response.text
                        logger.info(f"[{self.call_sid}] Agent: {text}")
                        self.transcript_parts.append(f"Riya: {text}")
                        if self.lead_id:
                            chunk_info = extract_from_chunk(self.lead_id, text)
                            self._merge_info(chunk_info)
                            upsert_info(self.collected_info)
                        if "[[HANGUP]]" in text:
                            logger.info(f"[{self.call_sid}] Hangup signal detected in text — ending call")
                            self.on_hangup.set()

                    # Input audio transcription (customer speech)
                    if getattr(response, "server_content", None):
                        sc = response.server_content
                        # Agent output transcription — buffer chunks, also check for hangup signal
                        if getattr(sc, "output_transcription", None):
                            t = sc.output_transcription.text or ""
                            if t.strip():
                                if self.transcript_parts and self.transcript_parts[-1].startswith("Riya:"):
                                    self.transcript_parts[-1] += t
                                else:
                                    self.transcript_parts.append(f"Riya:{t}")
                                # Detect hangup from transcription (primary path in AUDIO-only mode)
                                if "[[HANGUP]]" in t:
                                    logger.info(f"[{self.call_sid}] Hangup signal detected in transcription — ending call")
                                    self.on_hangup.set()
                                # Also detect natural closing phrases as hangup trigger
                                closing_phrases = [
                                    "dhanyawad", "shukriya", "aapka din achha rahe",
                                    "thank you", "goodbye", "bye", "alvida"
                                ]
                                tl = t.lower()
                                if any(p in tl for p in closing_phrases):
                                    # Set hangup after a short delay to let audio finish playing
                                    async def _delayed_hangup():
                                        await asyncio.sleep(3)
                                        if not self.on_hangup.is_set():
                                            logger.info(f"[{self.call_sid}] Closing phrase detected — hanging up")
                                            self.on_hangup.set()
                                    asyncio.create_task(_delayed_hangup())
                        # Customer input transcription
                        if getattr(sc, "input_transcription", None):
                            t = sc.input_transcription.text or ""
                            if t.strip():
                                if self.transcript_parts and self.transcript_parts[-1].startswith("Customer:"):
                                    self.transcript_parts[-1] += t
                                else:
                                    self.transcript_parts.append(f"Customer:{t}")

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
