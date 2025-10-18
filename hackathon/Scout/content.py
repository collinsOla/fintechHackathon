# arp/arp_report_list.py
import os, hashlib, json, time
from typing import List, Dict, Any, Optional
import google.generativeai as genai
from string import Template

# ---------- Configure (mirrors your ai_scoring.py) ----------
MODEL_NAME = "gemini-2.5-flash"  # fast/cheap. swap if needed to 1.5-pro or 2.0-pro
API_KEY = "AIzaSyAQXQ1ulMBsoAIOBv-7U1c7xUbFNx0_suY" or ""  # or set directly like your file
if not API_KEY:
    # Optional: fall back to the same literal you had (not recommended to hardcode!)
    # API_KEY = "YOUR_API_KEY"
    pass
if API_KEY:
    genai.configure(api_key=API_KEY)

# ---------- Simple file cache (avoid re-billing for same (title+abstract)) ----------
CACHE_PATH = os.path.join(os.path.dirname(__file__), "gemini_cache.json")
try:
    _CACHE = json.load(open(CACHE_PATH, "r", encoding="utf-8"))
except Exception:
    _CACHE = {}

def _cache_get(key: str):
    return _CACHE.get(key)

def _cache_set(key: str, value: Any):
    _CACHE[key] = value
    try:
        json.dump(_CACHE, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]

# ---------- Prompt (JSON-array ONLY) ----------
SYSTEM_INSTRUCTIONS = (
    "You are ARP, an AI that analyzes arXiv papers for commercial and practical potential. "
    "Return ONLY valid JSON (no prose, no markdown)."
)

PROMPT_TEMPLATE = Template(r"""
Only output valid JSON and nothing else.
Produce a JSON array with EXACTLY 4 strings in this order:
[
  "background_context",
  "real_world_problems_solved",
  "market_analysis",
  "immediate_startup_patent_ideas"
]

Guidance:
- Be concise, clear, and professional.
- Avoid hype; ground claims in what’s plausible from the abstract.
- If the abstract is theoretical, infer reasonable applied pathways.
- No extra keys or objects—just a 4-item JSON array of strings.

Paper:
Title: ${title}

Abstract:
${abstract}
""")


def _safe_parse_list(json_text: str) -> List[str]:
    """
    Extract the first top-level JSON array and return it as a 4-item list of strings.
    Raises ValueError if parsing/shape is wrong.
    """
    s = (json_text or "").strip()
    start, end = s.find("["), s.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON array found in model output.")
    s = s[start:end+1]
    data = json.loads(s)

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got: {type(data)}")

    # Enforce exactly 4 items
    if len(data) != 4:
        raise ValueError(f"Expected 4 items, got {len(data)}")

    # Coerce all items to strings (truncate to keep things tidy if you want)
    out = [str(x) if x is not None else "" for x in data]
    return out

def arp_report_list_with_gemini(title: str, abstract: str, retry: int = 2) -> List[str]:
    """
    Returns a list of 4 strings:
    [
      background_context,
      real_world_problems_solved,
      market_analysis,
      immediate_startup_patent_ideas
    ]
    Caches by (title+abstract) hash to avoid repeat calls.
    """
    # Fallback if no API key configured
    if not API_KEY:
        return [
            "Fallback: no GOOGLE_API_KEY configured.",
            "Fallback: cannot assess real-world problems.",
            "Fallback: cannot assess market without API access.",
            "Fallback: integrate once API is configured; consider provisional patent search."
        ]

    key = "arpv1_" + _hash(f"{title}\n{abstract}")
    cached = _cache_get(key)
    if cached:
        return cached

    model = genai.GenerativeModel(MODEL_NAME)

    prompt = PROMPT_TEMPLATE.substitute(title=title.strip(), abstract=abstract.strip())

    last_err: Optional[Exception] = None
    for attempt in range(retry + 1):
        try:
            resp = model.generate_content(
                prompt,
                safety_settings=None,  # keep defaults if preferred
                generation_config={"response_mime_type": "application/json"}
            )

            # Debug prints (optional):
            try:
                print(">>> resp.text (first 400):", repr((resp.text or "")[:400]), flush=True)
                print(">>> finish_reason:", getattr(resp.candidates[0], "finish_reason", None), flush=True)
                print(">>> prompt_feedback:", getattr(resp, "prompt_feedback", None), flush=True)
            except Exception:
                pass

            raw = resp.text or ""
            parsed_list = _safe_parse_list(raw)  # hardened parser for JSON arrays
            _cache_set(key, parsed_list)
            return parsed_list

        except Exception as e:
            last_err = e
            time.sleep(0.8 * (attempt + 1))

    # Final fallback if parsing failed
    return [
        f"Error calling Gemini: {last_err}",
        "N/A",
        "N/A",
        "N/A"
    ]

