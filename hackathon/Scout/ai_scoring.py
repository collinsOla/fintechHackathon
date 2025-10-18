# Scout/ai_scoring.py
import os, hashlib, json, time
from typing import Dict, Any
import google.generativeai as genai

# ---------- Configure ----------
MODEL_NAME = "gemini-2.5-flash"  # fast/cheap. swap to 1.5-pro for higher quality
API_KEY = "AIzaSyAQXQ1ulMBsoAIOBv-7U1c7xUbFNx0_suY"
if API_KEY:
    genai.configure(api_key=API_KEY)

# ---------- Simple file cache (avoids re-billing for same abstract) ----------
CACHE_PATH = os.path.join(os.path.dirname(__file__), "gemini_cache.json")
try:
    _CACHE = json.load(open(CACHE_PATH, "r", encoding="utf-8"))
except Exception:
    _CACHE = {}

def _cache_get(key: str):
    return _CACHE.get(key)

def _cache_set(key: str, value: Dict[str, Any]):
    _CACHE[key] = value
    try:
        json.dump(_CACHE, open(CACHE_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass

def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]

# ---------- Prompt (JSON-only) ----------
SYSTEM_INSTRUCTIONS = """You are an analyst scoring research for commercialization.
Return ONLY valid JSON that matches the provided JSON schema. No extra text."""
# at top
from string import Template
from string import Template  # if not already

PROMPT_TEMPLATE = Template(r"""
You score research abstracts for commercialization. Output JSON ONLY (no prose, no markdown).

Infer practicality beyond what’s explicitly written:
- If the abstract is theoretical, imagine realistic applications in adjacent domains.
- Do NOT penalize absence of an “applications” section; reason about plausible pathways.

Scoring rubric:
- problem_fit (0–5): Real-world pain points this could address (inferred allowed).
- practicality_maturity (0–5): Plausible path to prototype/deployment given today’s tools/data.
- novelty (0–5): Originality vs. typical work in the field.
- market_fit (0–5): Likely buyer segments, demand urgency, willingness to pay (inferred allowed).
- partner_interest (0–5): Likely interest from partners/licensees/investors given current market.
- trl (1–9): TRL estimate today (1 theory → 9 proven in real-world).
- overall_commercialization (1–9): Weighted combination of the above (TRL ~30% weight; do NOT just copy TRL).

Return ONLY valid JSON EXACTLY in this schema (no extra fields, no text outside JSON):
{
  "scores": {
    "problem_fit": 0,
    "practicality_maturity": 0,
    "novelty": 0,
    "market_fit": 0,
    "partner_interest": 0
  },
  "trl": 1,
  "overall_commercialization": 1
}

Abstract:
\"\"\"${abstract}\"\"\"
""")

def _coerce_int(x, lo, hi, default):
    try:
        v = int(round(float(x)))
        return max(lo, min(hi, v))
    except Exception:
        return default

def _safe_parse(json_text: str) -> Dict[str, Any]:
    # Trim non-JSON if any, then parse
    s = json_text.strip()
    start, end = s.find("{"), s.rfind("}")
    if start != -1 and end != -1:
        s = s[start:end+1]
    data = json.loads(s)

    # Coerce and clamp
    sc = data.get("scores", {}) or {}
    out = {
        "scores": {
            "problem_fit":           _coerce_int(sc.get("problem_fit", 0), 0, 5, 0),
            "practicality_maturity": _coerce_int(sc.get("practicality_maturity", 0), 0, 5, 0),
            "novelty":               _coerce_int(sc.get("novelty", 0), 0, 5, 0),
            "market_fit":            _coerce_int(sc.get("market_fit", 0), 0, 5, 0),
            "partner_interest":      _coerce_int(sc.get("partner_interest", 0), 0, 5, 0),
        },
        "trl": _coerce_int(data.get("trl", 1), 1, 9, 1),
        "overall_commercialization": _coerce_int(data.get("overall_commercialization", 1), 1, 9, 1),
        "rationale": str(data.get("rationale", ""))[:2000],
    }
    return out

def score_abstract_with_gemini(abstract: str, retry: int = 2) -> Dict[str, Any]:
    """
    Returns dict:
    {
      "scores": {... five 0-5 ints ...},
      "trl": 1-9,
      "overall_commercialization": 1-9,
      "rationale": "..."
    }
    Caches by abstract hash to avoid repeat calls.
    """
    if not API_KEY:
        # Fallback if no key: neutral baseline
        return {
            "scores": {k: 2 for k in ["problem_fit","practicality_maturity","novelty","market_fit","partner_interest"]},
            "trl": 2, "overall_commercialization": 2,
            "rationale": "Fallback score: no GOOGLE_API_KEY configured."
        }

    key = _hash(abstract)
    cached = _cache_get(key)
    if cached:
        return cached

    model = genai.GenerativeModel(MODEL_NAME)
    prompt = PROMPT_TEMPLATE.substitute(abstract=abstract)

    last_err = None
    for attempt in range(retry + 1):
        try:
            resp = model.generate_content(
                prompt,
                safety_settings=None,  # keep defaults if you prefer
                generation_config={"response_mime_type": "application/json"}
            )
            print(">>> resp.text (first 400):", repr((resp.text or "")[:400]), flush=True)

# Helpful metadata:
            try:
                print(">>> finish_reason:", getattr(resp.candidates[0], "finish_reason", None), flush=True)
                print(">>> safety_ratings:", getattr(resp.candidates[0], "safety_ratings", None), flush=True)
            except Exception:
                pass
            print(">>> prompt_feedback:", getattr(resp, "prompt_feedback", None), flush=True)
            raw = resp.text or ""
            parsed = _safe_parse(raw)  # your hardened parser
            _cache_set(key, parsed)
            return parsed
        except Exception as e:
            last_err = e
            time.sleep(0.8 * (attempt + 1))
    # Final fallback if parsing failed
    return {
        "scores": {k: 1 for k in ["problem_fit","practicality_maturity","novelty","market_fit","partner_interest"]},
        "trl": 1, "overall_commercialization": 1,
        "rationale": f"Error calling Gemini: {last_err}"
    }
