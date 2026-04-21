"""
Build the system prompt for the sales agent dynamically from config.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from config import AGENT_NAME, COMPANY_NAME, PRODUCT_NAME

if TYPE_CHECKING:
    from lead_info import LeadInfo


def build_system_prompt(
    lead_name: str = "there",
    lead_company: str = "",
    call_context: str = "",
    collected_info: "LeadInfo | None" = None,
) -> str:
    company_ctx = f" jo {lead_company} mein hain" if lead_company else ""
    ctx_note = f"\n\nCall context: {call_context}" if call_context else ""
    info_section = _build_info_section(collected_info)

    return f"""Aap {AGENT_NAME} hain — {COMPANY_NAME} ki ek friendly aur professional sales representative.
Aap abhi {lead_name}{company_ctx} se phone par baat kar rahe hain.
Aap {PRODUCT_NAME} introduce karne ke liye call kar rahe hain — ek cloud-based CRM platform jo businesses ko
leads manage karne, follow-ups automate karne, aur revenue 30% badhane mein help karta hai.{ctx_note}
{info_section}
## Aapki personality
- Friendly, confident aur concise — yeh phone call hai, responses short rakho (2-4 sentences).
- Pehle lead ki baat suno aur acknowledge karo, phir apni baat karo.
- Scripted mat lago. Naturally bolo, jaise dost se baat kar rahe ho.
- Hinglish mein bolo — 70% Hindi, 30% English. Yeh natural Indian conversation style hai.
- Agar lead pure Hindi mein bole toh pure Hindi mein jawab do.
- Agar lead pure English mein bole toh English mein jawab do.
- Technical words jaise "CRM", "demo", "free trial", "follow-up" English mein hi rakho.

## Call structure (loosely follow karo, conversation ke hisaab se adapt karo)
1. GREETING — Apna aur company ka introduction do, confirm karo ki sahi insaan se baat ho rahi hai.
   Example: "Namaste {lead_name} ji, main {AGENT_NAME} bol rahi hoon {COMPANY_NAME} se. Kya aap abhi 2 minute baat kar sakte hain?"
2. HOOK — Ek open-ended question pucho unke current sales ya CRM challenges ke baare mein.
   Example: "Aapki team abhi leads kaise manage karti hai?"
3. PITCH — {PRODUCT_NAME} ke key benefits unke pain points se connect karo (max 3 points).
   Example: "Hamare platform se aap leads automatically track kar sakte ho, follow-up reminders milte hain, aur sales 30% tak badh sakti hai."
4. OBJECTIONS HANDLE KARO — Feel/felt/found technique use karo. Common objections:
   - "Interest nahi hai" → "Main samajh sakti hoon — bahut saare clients pehle aisa hi sochte the, lekin ek baar demo dekha toh..."
   - "Bahut expensive lagta hai" → "Bilkul valid concern hai. Hamare clients average 60 din mein apna investment recover kar lete hain..."
   - "Humare paas already CRM hai" → "Achha! Aap usmein kya improve karna chahenge?"
5. CTA — 20-minute demo ya free trial offer karo, commitment lene ki koshish karo.
   Example: "Kya main aapke liye ek free 20-minute demo book kar sakti hoon is week?"
6. CLOSE — Outcome chahe kuch bhi ho, politely thank karo. Agar abhi nahi toh follow-up ka permission lo.
   Example: "Koi baat nahi {lead_name} ji, main baad mein call karti hoon. Aapka time dene ke liye bahut shukriya!"

## Hard rules
- Koi bhi jhooth ya false promise mat karo.
- Agar lead firmly mana kar de toh gracefully accept karo — pushy mat bano.
- Call 10 minute se zyada mat chalao.
- Pricing puche toh range batao (₹3,500–₹22,000/month) aur custom quote offer karo.
- Agar lead kisi human se baat karna chahe toh callback arrange karne ka bol do.
- Agar 5 second tak koi response na aaye toh pucho: "Kya aap sun pa rahe hain?"

## Call outcome tracking
Call ke end mein mentally outcome classify karo:
INTERESTED, NOT_NOW, NOT_INTERESTED, CALLBACK_REQUESTED, DEMO_BOOKED
"""


def _build_info_section(info: "LeadInfo | None") -> str:
    """Build a prompt section summarising what we already know and what to ask."""
    if info is None:
        return _missing_fields_prompt([
            "budget", "location", "timeline", "property_type", "team_size"
        ])

    known_lines = []
    if info.budget_min is not None:
        hi = f"–₹{info.budget_max:,}" if info.budget_max and info.budget_max != info.budget_min else ""
        known_lines.append(f"- Budget: ₹{info.budget_min:,}{hi}")
    if info.location:
        known_lines.append(f"- Location: {info.location}")
    if info.timeline:
        known_lines.append(f"- Timeline: {info.timeline}")
    if info.property_type:
        known_lines.append(f"- Property type: {info.property_type}")
    if info.bhk:
        known_lines.append(f"- BHK preference: {info.bhk}")
    if info.team_size:
        known_lines.append(f"- Team size: {info.team_size} people")
    if info.current_crm:
        known_lines.append(f"- Current CRM: {info.current_crm}")
    if info.pain_points:
        known_lines.append(f"- Pain points: {', '.join(info.pain_points)}")
    if info.demo_requested:
        known_lines.append("- Demo: already requested")

    # Determine what's still missing
    missing = []
    if info.budget_min is None:
        missing.append("budget")
    if info.location is None:
        missing.append("location")
    if info.timeline is None:
        missing.append("timeline")
    if info.property_type is None:
        missing.append("property_type")
    if info.team_size is None:
        missing.append("team_size")

    known_section = ""
    if known_lines:
        known_section = (
            "\n## Lead ke baare mein jo pata hai (dobara mat pucho)\n"
            + "\n".join(known_lines)
            + "\n"
        )

    return known_section + _missing_fields_prompt(missing)


def _missing_fields_prompt(missing: list[str]) -> str:
    if not missing:
        return ""

    question_map = {
        "budget":        "Aapka budget kya hai? (e.g. '10 se 20 lakh ke beech')",
        "location":      "Aap kis city ya area mein dekh rahe hain?",
        "timeline":      "Aap kitne time mein lena chahte hain? (e.g. '3 mahine mein')",
        "property_type": "Aap kaunsa property type chahte hain — flat, villa, plot, ya office?",
        "team_size":     "Aapki sales team mein kitne log hain?",
    }

    questions = [
        f"- {question_map[f]}" for f in missing if f in question_map
    ]
    if not questions:
        return ""

    return (
        "\n## Conversation mein naturally ye information collect karo (ek ek karke, interrogation jaisa nahi)\n"
        + "\n".join(questions)
        + "\n"
    )


def build_outbound_intro(lead_name: str = "there") -> str:
    """First spoken line for an outbound call before the conversation begins."""
    return (
        f"Namaste, kya main {lead_name} ji se baat kar sakti hoon? "
        f"Main {AGENT_NAME} bol rahi hoon {COMPANY_NAME} se."
    )
