#!/usr/bin/env python3
"""
Find commercial signals for a startup idea using Gemini + Google Search grounding,
and save results as JSON split into:
  - top_signal (exactly one, or {} if none)
  - commercial_signals (all other items)

Usage:
  # Windows PowerShell (open a new terminal after setx):
  setx GEMINI_API_KEY "your_key_here"
  # macOS/Linux:
  export GEMINI_API_KEY="your_key_here"

  # Run with a CLI argument:
  python signals.py "Self-hosted RAG for regulated data"

  # Or run with no argument for an interactive prompt.
"""

import os
import sys
import re
import json
from datetime import datetime, timedelta
from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"
TIME_WINDOW_MONTHS = 24
OUT_DIR = "out"
OUT_JSON = os.path.join(OUT_DIR, "signals_report.json")

# ---------------- Helpers: cleaning & parsing ----------------

def _clean_json_text(s: str) -> str:
    """
    Make model output more JSON-friendly:
    - Strip code fences (``` / ```json)
    - Normalize smart quotes to ASCII quotes
    - Remove control chars (except \t and \n)
    - Extract outermost {...}
    - Remove trailing commas before } or ]
    """
    if not s:
        return ""

    # Remove code fences
    s = re.sub(r"```(?:json)?", "", s, flags=re.IGNORECASE).strip()

    # Normalize quotes
    s = (s
         .replace("“", '"').replace("”", '"')
         .replace("‘", "'").replace("’", "'"))

    # Remove raw control chars (keep tab/newline)
    s = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", s)

    # Extract outermost JSON object if there is extra prose around it
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1 and start < end:
        s = s[start:end+1]

    # Remove trailing commas before } or ]
    s = re.sub(r",\s*([}\]])", r"\1", s)

    return s.strip()


def _parse_json_lenient(text: str, idea_fallback: str):
    """
    Try multiple strategies to parse JSON from model text.
    If all fail, return a minimal payload with raw_output for debugging.
    """
    if not text:
        return {
            "idea": idea_fallback,
            "summary": "No content returned from model.",
            "signals": [],
            "raw_output": ""
        }

    # 1) Direct parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) Clean once and parse
    s1 = _clean_json_text(text)
    try:
        return json.loads(s1)
    except Exception:
        pass

    # 3) Try largest {...} block again
    start, end = s1.find("{"), s1.rfind("}")
    if start != -1 and end != -1 and start < end:
        core = _clean_json_text(s1[start:end+1])
        try:
            return json.loads(core)
        except Exception:
            pass

    # 4) Give a safe payload for inspection
    return {
        "idea": idea_fallback,
        "summary": "Parsing error: model did not return valid JSON. See 'raw_output'.",
        "signals": [],
        "raw_output": text[:4000]
    }

# ---------------- Prompt building (safe for LaTeX ideas) ----------------

def make_prompt(idea: str) -> str:
    """
    Embed idea using json.dumps so backslashes/braces/newlines are escaped safely.
    This helps when the idea contains LaTeX or other special characters.
    """
    cutoff_date = (datetime.utcnow() - timedelta(days=TIME_WINDOW_MONTHS * 30)).date().isoformat()
    idea_safe = json.dumps(idea)  # ensures quotes/backslashes/newlines are escaped

    return f"""
You are a venture analyst. Use web search to find **recent, verifiable signals** related to:

Idea: {idea_safe}

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
  "idea": {idea_safe},
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

# ---------------- Gemini call ----------------

def find_signals(idea: str):
    client = genai.Client(api_key="AIzaSyAQXQ1ulMBsoAIOBv-7U1c7xUbFNx0_suY")
    if not client:
        raise RuntimeError("Set GEMINI_API_KEY in your environment first.")

    # Use Google Search grounding; with tools, keep text/plain and parse JSON ourselves
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(
        tools=[grounding_tool],
        response_mime_type="text/plain",
    )

    contents = [types.Content(parts=[types.Part(text=make_prompt(idea))])]
    resp = client.models.generate_content(model=MODEL_NAME, config=config, contents=contents)

    text = (resp.text or "").strip()
    data = _parse_json_lenient(text, idea_fallback=idea)

    # Ensure core keys exist
    data.setdefault("idea", idea)
    data.setdefault("summary", "No summary provided.")
    data.setdefault("signals", [])

    return data

# ---------------- Top vs Commercial split (one top_signal) ----------------

def pick_top_and_split(signals):
    """
    Choose exactly one top signal by (1) type priority, then (2) recency.
    Everything else goes to commercial_signals.
    """
    if not signals:
        return None, []

    priority = ["funding", "mna", "partnership", "customer"]  # highest → lowest

    def score(sig):
        t = (sig.get("type") or "").lower()
        try:
            pri = priority.index(t)
        except ValueError:
            pri = len(priority)  # non-priority types come after all priority types
        try:
            dt = datetime.fromisoformat(sig.get("date", "1900-01-01"))
        except Exception:
            dt = datetime(1900, 1, 1)
        return (pri, -dt.timestamp())  # lower is better

    top_signal = sorted(signals, key=score)[0]
    commercial = [s for s in signals if s is not top_signal]
    return top_signal, commercial

# ---------------- Pretty-printing ----------------

def _format_signal(sig: dict) -> str:
    t = (sig.get("type") or "?").upper()
    org = sig.get("org") or "Unknown org"
    date = sig.get("date") or "Unknown date"
    note = (sig.get("note") or "").strip()
    src  = sig.get("source") or ""
    parts = [f"[{t}] {org} — {date}"]
    if note:
        parts.append(f"    {note}")
    if src:
        parts.append(f"    Source: {src}")
    return "\n".join(parts)

# ---------------- Input handling ----------------

def read_idea_from_args_or_prompt():
    if len(sys.argv) >= 2:
        return sys.argv[1]
    idea = input("Enter your startup/research idea: ").strip()
    if not idea:
        print("❌ No idea provided, exiting.")
        sys.exit(1)
    return idea

# ---------------- Main ----------------

if __name__ == "__main__":
    idea = read_idea_from_args_or_prompt()
    data = find_signals(idea)

    top_signal, commercial_signals = pick_top_and_split(data.get("signals", []))
    output = {
        "idea": data.get("idea", idea),
        "summary": data.get("summary", "No summary provided."),
        "top_signal": top_signal or {},
        "commercial_signals": commercial_signals
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Descriptive console output
    print(f"✅ Signals saved to {OUT_JSON}\n")
    print(f"Idea: {output['idea']}")
    print(f"Summary: {output['summary']}\n")

    print("=== Top Signal ===")
    if output["top_signal"]:
        print(_format_signal(output["top_signal"]))
    else:
        print("None")
    print("\n=== Other Commercial Signals ===")
    if output["commercial_signals"]:
        for i, sig in enumerate(output["commercial_signals"], 1):
            print(f"{i}. {_format_signal(sig)}")
    else:
        print("None")
