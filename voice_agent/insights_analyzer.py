"""
insights_analyzer.py

Analyzes call transcripts using Gemini (primary) with keyword fallback.
Returns structured insights: sentiment, buying intent, lead score, objections,
summary, topics, follow-up flag, etc.

Transcripts are NEVER stored — only structured insights are persisted.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

_ANALYSIS_PROMPT = """You are an expert sales call analyst. Analyze the following call transcript and return a JSON object with insights.

The transcript may be in Hindi, English, Hinglish (mixed Hindi-English), Tamil, Telugu, Marathi, Bengali, or other Indian languages. Understand it fully regardless of language.

Call duration: {duration} seconds

Transcript:
\"\"\"
{transcript}
\"\"\"

Return ONLY a valid JSON object with this exact structure (no markdown, no explanation):
{{
  "sentiment": {{
    "overall": "positive" | "neutral" | "negative",
    "score": <number between -1 and 1>,
    "reasoning": "<one sentence why>"
  }},
  "buyingIntent": {{
    "level": "high" | "medium" | "low" | "none",
    "indicators": ["<phrase that showed intent>"],
    "timeline": "<immediate | within 30 days | 3-6 months | future | unknown>"
  }},
  "interestLevel": <0-10>,
  "engagementScore": <0-10>,
  "keyTopics": ["<topic1>", "<topic2>"],
  "objections": [
    {{ "type": "<price | timing | authority | need | other>", "detail": "<what they said>", "resolved": true | false }}
  ],
  "extractedData": {{
    "companyName": "<if mentioned, else null>",
    "industry": "<if mentioned, else null>",
    "budget": "<if mentioned, else null>",
    "decisionMaker": true | false | null,
    "painPoints": ["<pain point>"],
    "requirements": ["<requirement>"],
    "currentSolution": "<if mentioned, else null>"
  }},
  "followUpRequired": true | false,
  "conversationSummary": "<2-3 sentence summary in English regardless of transcript language>",
  "nextAction": "<specific recommended action>",
  "detectedLanguage": "<primary language e.g. Hindi, Hinglish, Tamil, English>"
}}"""


# ── Gemini analysis ───────────────────────────────────────────────────────────

async def _analyze_with_gemini(transcript: str, duration: float) -> dict:
    """Use Gemini to analyze the transcript."""
    from config import GEMINI_API_KEY, USE_VERTEX_AI, VERTEX_PROJECT_ID, VERTEX_LOCATION, GOOGLE_APPLICATION_CREDENTIALS
    from google import genai
    from google.genai import types

    prompt = _ANALYSIS_PROMPT.format(transcript=transcript[:8000], duration=int(duration))

    if USE_VERTEX_AI:
        import os
        if GOOGLE_APPLICATION_CREDENTIALS:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GOOGLE_APPLICATION_CREDENTIALS
        client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
    else:
        client = genai.Client(api_key=GEMINI_API_KEY)

    response = await client.aio.models.generate_content(
        model='gemini-2.0-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=1500,
        ),
    )

    text = response.text or ''
    # Strip markdown code fences if present
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    return json.loads(text)


# ── Keyword fallback ──────────────────────────────────────────────────────────

def _analyze_with_keywords(transcript: str, duration: float) -> dict:
    """Basic keyword-based fallback — no API needed."""
    t = transcript.lower()

    pos_words = ['interested', 'great', 'yes', 'definitely', 'sounds good', 'perfect', 'sure', 'absolutely', 'haan', 'theek hai']
    neg_words = ['not interested', 'no', 'busy', 'remove', 'stop calling', "don't call", 'waste', 'nahi', 'mat karo']
    pos_count = sum(1 for w in pos_words if w in t)
    neg_count = sum(1 for w in neg_words if w in t)

    sentiment = 'positive' if pos_count > neg_count else 'negative' if neg_count > pos_count else 'neutral'
    score = 0.5 if sentiment == 'positive' else -0.5 if sentiment == 'negative' else 0.0

    high_intent = any(w in t for w in ['how much', 'price', 'cost', "let's start", 'send quote', 'next step', 'kitna', 'rate'])
    med_intent = any(w in t for w in ['interested', 'tell me more', 'sounds good', 'considering', 'batao'])
    intent = 'high' if high_intent else 'medium' if med_intent else 'low'

    follow_up = any(w in t for w in ['call back', 'follow up', 'send me', 'email me', 'contact me', 'baad mein'])

    sentences = [s.strip() for s in re.split(r'[.!?]+', transcript) if len(s.strip()) > 20]
    summary = f"{sentences[0]}." if sentences else 'Call completed.'

    return {
        'sentiment': {'overall': sentiment, 'score': score, 'reasoning': 'Keyword-based analysis'},
        'buyingIntent': {'level': intent, 'indicators': [], 'timeline': 'unknown'},
        'interestLevel': 6 if duration > 180 else 4 if duration > 60 else 2,
        'engagementScore': 5 if duration > 180 else 3,
        'keyTopics': [],
        'objections': [],
        'extractedData': {
            'companyName': None, 'industry': None, 'budget': None,
            'decisionMaker': None, 'painPoints': [], 'requirements': [], 'currentSolution': None,
        },
        'followUpRequired': follow_up,
        'conversationSummary': summary,
        'nextAction': 'Follow up as requested' if follow_up else 'Add to nurture campaign',
        'detectedLanguage': 'Unknown (keyword fallback)',
    }


# ── Lead scoring ──────────────────────────────────────────────────────────────

def calculate_lead_score(result: dict, duration: float, status: str) -> tuple[int, str]:
    """
    Score 0-100 and return (score, category).
    Category: hot (80-100), warm (60-79), cold (30-59), not_interested (0-29)
    """
    score = 0

    # Call completion
    if status in ('Completed', 'completed'):
        score += 20

    # Duration (up to 15 pts)
    score += min(15, int(duration / 60) * 3)

    # Sentiment
    sentiment = result.get('sentiment', {}).get('overall', 'neutral')
    score += 20 if sentiment == 'positive' else 10 if sentiment == 'neutral' else 0

    # Buying intent
    intent = result.get('buyingIntent', {}).get('level', 'none')
    score += 25 if intent == 'high' else 15 if intent == 'medium' else 5 if intent == 'low' else 0

    # Interest level (0-10 → up to 10 pts)
    score += min(10, result.get('interestLevel', 0))

    # Decision maker
    if result.get('extractedData', {}).get('decisionMaker'):
        score += 5

    # Budget mentioned
    if result.get('extractedData', {}).get('budget'):
        score += 5

    # Follow-up requested
    if result.get('followUpRequired'):
        score += 10

    score = min(100, max(0, score))

    if score >= 80:
        category = 'Hot'
    elif score >= 60:
        category = 'Warm'
    elif score >= 30:
        category = 'Cold'
    else:
        category = 'Not_Interested'

    return score, category


# ── Main entry point ──────────────────────────────────────────────────────────

async def analyze_call(
    transcript: str,
    duration: float,
    status: str,
    lead_id: str,
) -> dict:
    """
    Analyze a call transcript and return a structured insights dict.
    Uses Gemini with keyword fallback.
    """
    if not transcript or len(transcript.strip()) < 20:
        result = _analyze_with_keywords('', duration)
        provider = 'keyword (empty transcript)'
    else:
        try:
            result = await _analyze_with_gemini(transcript, duration)
            provider = 'gemini'
            logger.info(f'[{lead_id}] Gemini analysis OK (lang: {result.get("detectedLanguage", "?")})')
        except Exception as e:
            logger.warning(f'[{lead_id}] Gemini analysis failed: {e} — using keyword fallback')
            result = _analyze_with_keywords(transcript, duration)
            provider = 'keyword'

    score, category = calculate_lead_score(result, duration, status)

    return {
        'lead_id': lead_id,
        'provider': provider,
        'lead_score': score,
        'lead_category': category,
        'sentiment': result.get('sentiment', {}),
        'buying_intent': result.get('buyingIntent', {}),
        'interest_level': result.get('interestLevel', 0),
        'engagement_score': result.get('engagementScore', 0),
        'key_topics': result.get('keyTopics', []),
        'objections': result.get('objections', []),
        'extracted_data': result.get('extractedData', {}),
        'follow_up_required': result.get('followUpRequired', False),
        'conversation_summary': result.get('conversationSummary', ''),
        'next_action': result.get('nextAction', ''),
        'detected_language': result.get('detectedLanguage', ''),
    }
