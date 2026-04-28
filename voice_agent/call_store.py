"""
Shared in-memory store for call params AND pre-started Gemini bridges.
Populated at /exoml time (when we have CallSid + all params).
Consumed at _on_start time.
"""
from typing import Dict, Any

# Keyed by Exotel CallSid
_call_params: Dict[str, dict] = {}
_call_bridges: Dict[str, Any] = {}  # GeminiBridge instances, keyed by CallSid


def store(call_sid: str, params: dict) -> None:
    _call_params[call_sid] = params


def pop(call_sid: str) -> dict:
    return _call_params.pop(call_sid, {})


def store_bridge(call_sid: str, bridge) -> None:
    _call_bridges[call_sid] = bridge


def pop_bridge(call_sid: str):
    return _call_bridges.pop(call_sid, None)
