"""
lead_info.py — MongoDB-backed real-time lead data extracted during calls.

Public API (unchanged):
  upsert(info: LeadInfo) -> None
  get(lead_id: str) -> LeadInfo | None

LeadInfo fields are extracted live during the call by extractor.py and
stored here so the agent can reference them across call sessions and
the CRM can read them directly from MongoDB.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

from db import get_db
from config import CLIENT_ID

logger = logging.getLogger(__name__)


@dataclass
class LeadInfo:
    lead_id: str
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    location: Optional[str] = None
    timeline: Optional[str] = None
    property_type: Optional[str] = None
    bhk: Optional[str] = None
    team_size: Optional[int] = None
    current_crm: Optional[str] = None
    pain_points: list[str] = field(default_factory=list)
    callback_time: Optional[str] = None
    demo_requested: bool = False
    notes: Optional[str] = None


def _col():
    return get_db().lead_info


def upsert(info: LeadInfo) -> None:
    """Insert or update a LeadInfo record. Only overwrites non-None fields."""
    d = asdict(info)
    # Build $set only for fields that have a real value (don't overwrite with None)
    updates: dict = {"updated_at": datetime.now(timezone.utc)}
    for key, val in d.items():
        if key == "lead_id":
            continue
        if key == "pain_points":
            if val:  # only overwrite if we actually extracted something
                updates[key] = val
        elif key == "demo_requested":
            if val:  # only set True, never overwrite True with False
                updates[key] = True
        elif val is not None:
            updates[key] = val

    _col().update_one(
        {"lead_id": info.lead_id},
        {
            "$set": updates,
            "$setOnInsert": {
                "lead_id":    info.lead_id,
                "client_id":  CLIENT_ID,
                "created_at": datetime.now(timezone.utc),
            },
        },
        upsert=True,
    )


def get(lead_id: str) -> Optional[LeadInfo]:
    """Fetch a LeadInfo by lead_id, returns None if not found."""
    doc = _col().find_one({"lead_id": lead_id}, {"_id": 0})
    if not doc:
        return None
    return LeadInfo(
        lead_id=doc["lead_id"],
        budget_min=doc.get("budget_min"),
        budget_max=doc.get("budget_max"),
        location=doc.get("location"),
        timeline=doc.get("timeline"),
        property_type=doc.get("property_type"),
        bhk=doc.get("bhk"),
        team_size=doc.get("team_size"),
        current_crm=doc.get("current_crm"),
        pain_points=doc.get("pain_points", []),
        callback_time=doc.get("callback_time"),
        demo_requested=doc.get("demo_requested", False),
        notes=doc.get("notes"),
    )
