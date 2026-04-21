"""billing.py — INR tiered billing with PostgreSQL persistence (multi-tenant)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from config import CLIENT_ID
import pg_db

logger = logging.getLogger(__name__)

# ── Tiered pricing (INR per minute) ──────────────────────────────────────────
# Rate applies to the ENTIRE month's usage once a threshold is crossed.
# < 5,000  calls/month → ₹10.0/min  (Starter)
# < 10,000 calls/month → ₹8.0/min   (Standard)
# ≥ 10,000 calls/month → ₹6.5/min   (Pro)

TIERS = [
    {"name": "Starter",  "min_calls": 0,     "max_calls": 4999,  "rate": 10.0},
    {"name": "Standard", "min_calls": 5000,  "max_calls": 9999,  "rate": 8.0},
    {"name": "Pro",      "min_calls": 10000, "max_calls": None,  "rate": 6.5},
]


def get_tier(total_calls: int) -> dict:
    """Return the tier dict that applies for the given monthly call count."""
    if total_calls >= 10000:
        return TIERS[2]
    if total_calls >= 5000:
        return TIERS[1]
    return TIERS[0]


def current_month() -> str:
    """Return current month as 'YYYY-MM'."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


# ── PostgreSQL helpers ────────────────────────────────────────────────────────

def record_call(
    lead_id: str,
    campaign_id: str,
    duration_seconds: float,
    lead_name: str = "",
    lead_phone: str = "",
) -> None:
    """Upsert a billing record for a completed call. Called after every call."""
    if duration_seconds <= 0:
        return
    try:
        pg_db.record_billing(
            lead_id=lead_id,
            campaign_id=campaign_id,
            client_id=CLIENT_ID,
            duration_seconds=round(duration_seconds, 2),
            month=current_month(),
            lead_name=lead_name,
            lead_phone=lead_phone,
        )
    except Exception as exc:
        logger.error("billing.record_call failed: %s", exc)


# ── Summary queries ───────────────────────────────────────────────────────────

def get_monthly_summary(month: Optional[str] = None, client_id: Optional[str] = None) -> dict:
    """Return full billing summary for a given month and client."""
    month = month or current_month()
    cid   = client_id or CLIENT_ID
    try:
        # Get monthly totals
        totals = pg_db.get_monthly_billing_totals(cid, month)
        total_calls   = totals["total_calls"]
        total_seconds = float(totals["total_seconds"])
        total_minutes = total_seconds / 60.0

        tier      = get_tier(total_calls)
        rate      = tier["rate"]
        total_cost = round(total_minutes * rate, 2)

        # Next-tier info
        next_tier_info = None
        if total_calls < 5000:
            next_tier_info = f"{5000 - total_calls:,} more calls this month to drop to ₹8/min"
        elif total_calls < 10000:
            next_tier_info = f"{10000 - total_calls:,} more calls this month to drop to ₹6.5/min"

        # Per-campaign breakdown
        by_campaign = []
        for c in pg_db.get_billing_by_campaign(cid, month):
            mins = float(c["total_seconds"]) / 60.0
            by_campaign.append({
                "campaign_id":    c["campaign_id"],
                "calls":          c["calls"],
                "total_minutes":  round(mins, 2),
                "total_cost":     round(mins * rate, 2),
            })

        # Daily breakdown
        daily = []
        for d in pg_db.get_daily_billing(cid, month):
            mins = float(d["total_seconds"]) / 60.0
            daily.append({
                "date":  str(d["date"]),
                "calls": d["calls"],
                "cost":  round(mins * rate, 2),
            })

        # Available months
        available_months = pg_db.get_available_billing_months(cid)
        if month not in available_months:
            available_months.insert(0, month)

        return {
            "month": month,
            "summary": {
                "total_calls":   total_calls,
                "total_minutes": round(total_minutes, 2),
                "total_cost":    total_cost,
                "rate_per_min":  rate,
            },
            "tier": {
                "name":           tier["name"],
                "rate_per_min":   rate,
                "next_tier_info": next_tier_info,
            },
            "by_campaign":      by_campaign,
            "daily":            daily,
            "available_months": available_months,
        }
    except Exception as exc:
        logger.error("billing.get_monthly_summary failed: %s", exc)
        return _empty_summary(month)


def get_campaign_billing(campaign_id: str, month: Optional[str] = None, client_id: Optional[str] = None) -> dict:
    """Return billing summary for a single campaign in a given month."""
    month = month or current_month()
    cid   = client_id or CLIENT_ID
    try:
        # Month total to determine rate
        month_totals = pg_db.get_monthly_billing_totals(cid, month)
        total_calls = month_totals["total_calls"]
        rate = get_tier(total_calls)["rate"]

        # Campaign totals
        camp_totals = pg_db.get_campaign_billing_totals(campaign_id, month)
        calls   = camp_totals["calls"]
        seconds = float(camp_totals["total_seconds"])
        minutes = seconds / 60.0

        return {
            "campaign_id":   campaign_id,
            "month":         month,
            "calls":         calls,
            "total_minutes": round(minutes, 2),
            "total_cost":    round(minutes * rate, 2),
            "rate_per_min":  rate,
        }
    except Exception as exc:
        logger.error("billing.get_campaign_billing failed: %s", exc)
        return {"campaign_id": campaign_id, "month": month, "calls": 0,
                "total_minutes": 0, "total_cost": 0, "rate_per_min": 10.0}


def estimate_cost(num_contacts: int, avg_duration_min: float = 2.0, client_id: Optional[str] = None) -> dict:
    """Estimate cost for a new batch of calls, factoring in current month's usage."""
    cid = client_id or CLIENT_ID
    month = current_month()
    try:
        month_totals = pg_db.get_monthly_billing_totals(cid, month)
        current_calls = month_totals["total_calls"]
    except Exception:
        current_calls = 0

    projected_total = current_calls + num_contacts
    tier = get_tier(projected_total)
    rate = tier["rate"]
    total_minutes = num_contacts * avg_duration_min
    total_cost    = round(total_minutes * rate, 2)

    return {
        "num_contacts":      num_contacts,
        "avg_duration_min":  avg_duration_min,
        "projected_calls":   projected_total,
        "total_cost":        total_cost,
        "per_call":          round(total_cost / num_contacts, 2) if num_contacts else 0,
        "rate_per_min":      rate,
        "tier":              tier["name"],
    }


def _empty_summary(month: str) -> dict:
    return {
        "month": month,
        "summary": {"total_calls": 0, "total_minutes": 0.0, "total_cost": 0.0, "rate_per_min": 10.0},
        "tier": {"name": "Starter", "rate_per_min": 10.0, "next_tier_info": "5,000 more calls this month to drop to ₹8/min"},
        "by_campaign": [],
        "daily": [],
        "available_months": [month],
    }
