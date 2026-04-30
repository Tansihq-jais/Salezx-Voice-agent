"""Audio resampling utilities for Exotel ↔ Gemini PCM conversion.

Exotel: 8 kHz 16-bit mono PCM (base64)
Gemini input: 16 kHz 16-bit mono PCM
Gemini output: 24 kHz 16-bit mono PCM
"""
import asyncio
import audioop
import base64
from functools import partial


def b64_to_pcm(b64_str: str) -> bytes:
    return base64.b64decode(b64_str)


def pcm_to_b64(pcm_bytes: bytes) -> str:
    return base64.b64encode(pcm_bytes).decode("utf-8")


def resample_pcm(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """Resample 16-bit mono PCM synchronously using audioop."""
    if from_rate == to_rate:
        return pcm
    converted, _ = audioop.ratecv(pcm, 2, 1, from_rate, to_rate, None)
    return converted


async def resample_pcm_async(pcm: bytes, from_rate: int, to_rate: int) -> bytes:
    """Offload resampling to a thread pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(resample_pcm, pcm, from_rate, to_rate))


async def upsample_8k_to_16k(pcm_8k: bytes) -> bytes:
    return await resample_pcm_async(pcm_8k, 8000, 16000)


async def downsample_24k_to_8k(pcm_24k: bytes) -> bytes:
    return await resample_pcm_async(pcm_24k, 24000, 8000)
