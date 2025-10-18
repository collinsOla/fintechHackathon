#!/usr/bin/env python3
"""
Find commercial signals for a startup idea using Gemini + Google Search grounding,
and save the results as JSON.

Usage:
    setx GEMINI_API_KEY "your_key_here"         # Windows PowerShell, then open a new terminal
    # or: export GEMINI_API_KEY="your_key_here" # macOS/Linux
    python signals.py "self-hosted RAG for regulated data"
"""

import os
import sys
import json
from datetime import datetime, timedelta
from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"
TIME_WINDOW_MONTHS = 24
OUT_DIR = "out"
OUT_JSON = os.path.join(OUT_DIR, "signals_report.json")

def make_prompt(idea: str) -> str:
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
"""

def find_signals(idea: str):
    client = genai.Client(api_key="AIzaSyAQXQ1ulMBsoAIOBv-7U1c7xUbFNx0_suY")
    if not client:
        raise RuntimeError("Set GEMINI_API_KEY in your environment first.")


    # Enable Google Search grounding (tools), but DO NOT request application/json mime.
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(
        tools=[grounding_tool],
        response_mime_type="text/plain",  # text mode; we'll parse JSON ourselves
    )

    contents = [types.Content(parts=[types.Part(text=make_prompt(idea))])]

    resp = client.models.generate_content(
        model=MODEL_NAME,
        config=config,
        contents=contents,
    )

    # Parse JSON from text (robust to minor wrappers)
    text = resp.text or ""
    try:
        return json.loads(text)
    except Exception:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start:end+1])
        raise ValueError("Gemini did not return valid JSON:\n" + text)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python signals.py "<your idea>"')
        sys.exit(1)

    idea = sys.argv[1]
    data = find_signals(idea)

    # Ensure keys exist
    data.setdefault("idea", idea)
    data.setdefault("summary", "No summary provided.")
    data.setdefault("signals", [])

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Signals saved to {OUT_JSON}")
    print(f"Idea: {data['idea']}")
    print(f"Summary: {data['summary']}")
    print(f"Items: {len(data['signals'])}")
