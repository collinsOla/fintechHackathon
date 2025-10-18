#!/usr/bin/env python3
"""
signals.py — fetch commercial signals for an idea using Gemini + Google Search grounding.

Usage:
    from signals import find_signals, find_top_signal

    data = find_signals("self-hosted RAG for regulated data")
    best = find_top_signal("self-hosted RAG for regulated data")
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from google import genai
from google.genai import types

# --- Config ---
API_KEY = "AIzaSyAQXQ1ulMBsoAIOBv-7U1c7xUbFNx0_suY"  # ⚠️ rotate if this key ever leaks
MODEL_NAME = "gemini-2.5-flash"
TIME_WINDOW_MONTHS = 24

# --- Prompt builder ---
def _make_prompt(idea: str) -> str:
    cutoff_date = (datetime.utcnow() - timedelta(days=TIME_WINDOW_MONTHS * 30)).date().isoformat()
    return f"""
You are a venture analyst. Use web search to find **recent, verifiable signals** related to:

Idea: "{idea}"

Signals of interest:
- funding rounds
- M&A activity
- partnerships
- customer wins
- hiring spikes
- open-source traction
- patents
- regulatory approvals

Constraints:
- Only include items on or after {cutoff_date}.
- Prefer primary sources (press releases, official blogs, SEC/EDGAR, reputable news).
- For each item, include one clear URL.
- Be concise and factual.

Return **STRICT JSON only**, with this exact structure (no extra text):

{{
  "idea": "{idea}",
  "summary": "one-paragraph overview of momentum (or lack thereof)",
  "signals": [
    {{
      "type": "funding|mna|partnership|customer|hiring|oss|patent|regulatory|other",
      "org": "organization name",
      "date": "YYYY-MM-DD",
      "note": "1–2 sentence description",
      "source": "https://exact-url"
    }}
  ]
}}
""".strip()

# --- Helpers ---
def _parse_json_loose(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start:end+1])
    raise ValueError("Gemini did not return valid JSON:\n" + text)

# --- Main function ---
def find_signals(idea: str, *, model: str = MODEL_NAME) -> Dict[str, Any]:
    client = genai.Client(api_key=API_KEY)

    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(
        tools=[grounding_tool],
        response_mime_type="text/plain",
    )
    contents = [types.Content(parts=[types.Part(text=_make_prompt(idea))])]

    resp = client.models.generate_content(model=model, config=config, contents=contents)
    print("RESPONSE ",resp)

    data = _parse_json_loose(getattr(resp, "text", "") or "")
    data.setdefault("idea", idea)
    data.setdefault("summary", "No summary provided.")
    data.setdefault("signals", [])
    if not isinstance(data["signals"], list):
        data["signals"] = []
    return data

# --- Best-signal scoring ---
_SIGNAL_PRIORITY = {
    "funding": 8, "mna": 8,
    "partnership": 6, "customer": 6, "regulatory": 6,
    "patent": 5, "hiring": 4, "oss": 3,
    "other": 1,
}

def _parse_date(d: str) -> datetime:
    try:
        return datetime.strptime(d, "%Y-%m-%d")
    except Exception:
        return datetime.min

def _score_signal(s: Dict[str, Any]) -> int:
    t = (s.get("type") or "").lower().strip()
    base = _SIGNAL_PRIORITY.get(t, 0)
    date_score = int((_parse_date(s.get("date") or "0001-01-01")).timestamp() // 86400)
    return base * 10_000_000 + date_score

def find_top_signal(idea: str, *, model: str = MODEL_NAME) -> Optional[Dict[str, Any]]:
    data = find_signals(idea, model=model)
    signals = data.get("signals", [])
    if not signals:
        return None
    return sorted(signals, key=_score_signal, reverse=True)[0]
