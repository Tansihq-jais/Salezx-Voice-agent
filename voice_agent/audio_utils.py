"""
Audio resampling utilities.

Exotel  →  8 kHz  16-bit mono  PCM  (base64 encoded)
Gemini  ←  16 kHz 16-bit mono  PCM  (bytes)
Gemini  →  24 kHz 16-bit mono  PCM  (bytes)
Exotel  ←  8 kHz  16-bit mono  PCM  (base64 encoded)
"""
import asyncio
import audioop
import base64
from functools import partial


def b64_to_pcm(b64_str: str) -> bytes:
    """Decode base64 string coming from Exotel into raw PCM bytes."""
    return base64.b64decode(b64_str)


def pcm_to_b64(pcm_bytes: bytes) -> str:
    """Encode raw PCM bytes to base64 for sending back to Exotel."""
    return base64.b64encode(pcm_bytes).decode("utf-8")


def resample_pcm(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """
    Resample 16-bit mono PCM from from_rate to to_rate using audioop.
    This is CPU-bound; use the async wrappers below from async contexts.
    """
    if from_rate == to_rate:
        return pcm
    converted, _ = audioop.ratecv(
        pcm,
        2,      # sample width bytes (16-bit)
        1,      # mono
        from_rate,
        to_rate,
        None,   # state (None = new conversion)
    )
    return converted


# fix #3: async wrappers offload CPU-bound resampling to thread pool
async def resample_pcm_async(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """Offload resampling to a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(resample_pcm, pcm, from_rate, to_rate))


async def upsample_8k_to_16k(pcm_8k: bytes) -> bytes:
    """8 kHz → 16 kHz for Gemini input (async, non-blocking)."""
    return await resample_pcm_async(pcm_8k, 8000, 16000)


async def downsample_24k_to_8k(pcm_24k: bytes) -> bytes:
    """24 kHz → 8 kHz for Exotel output (async, non-blocking)."""
    return await resample_pcm_async(pcm_24k, 24000, 8000)
