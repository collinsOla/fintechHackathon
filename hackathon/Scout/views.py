from datetime import date
from django.shortcuts import render
from google import genai
from django.utils.text import slugify
from pathlib import Path
import json
from datetime import date, datetime
from django.conf import settings
from django.utils.text import slugify
from django.core.paginator import Paginator
from .ai_scoring import score_abstract_with_gemini
# views.py (top)
from .signals import find_signals, find_top_signal



# ---- JSON loader + normalizers ----

_PAPERS_CACHE = None
_PAPERS_MTIME = None

def _parse_date(s):
    try:
        # accepts "YYYY-MM-DD"
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

def _categories_to_industries(cats_str):
    """
    Naive mapping from arXiv categories to display-friendly industry tags.
    Tweak this mapping as you like; unknown tags fall back to the raw code.
    """
    mapdict = {
        "cs.SE": "Software",
        "quant-ph": "Quantum",
        "physics.gen-ph": "Physics (General)",
    }
    inds = []
    for t in (cats_str or "").split():
        inds.append(mapdict.get(t, t))
    return inds or ["General"]

def _load_papers_from_json():
    """
    Read archivpapers.json and return a list of normalized paper dicts
    that match the structure your templates already use.
    """
    path = Path(settings.BASE_DIR) / "archivpapers.json"
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    papers, seen = [], set()
    for i, r in enumerate(raw):
        title = (r.get("title") or "").strip() or f"Untitled {i+1}"
        slug = slugify(title, allow_unicode=True) or f"paper-{i}"
        if slug in seen:
            slug = f"{slug}-{i}"
        seen.add(slug)

        papers.append({
            "id": r.get("id"),
            "title": title,
            "slug": slug,
            "published": _parse_date(r.get("created")) or date.today(),
            "industries": _categories_to_industries(r.get("categories")),
            "score": 0,                         # placeholder; keep your existing logic if any
            "url": "",                          # optional external link (empty for now)
            "summary_background": r.get("abstract", ""),
            "summary_problems": "",             # fill later
            "summary_market": "",               # fill later
            "summary_ideas": "",                # fill later
        })
    return papers

def get_papers():
    """
    Cached accessor that reloads the JSON file if it changed on disk
    (useful during development with auto-reload).
    """
    global _PAPERS_CACHE, _PAPERS_MTIME
    path = Path(settings.BASE_DIR) / "archivpapers.json"
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError:
        return []

    if _PAPERS_CACHE is None or _PAPERS_MTIME != mtime:
        _PAPERS_CACHE = _load_papers_from_json()
        _PAPERS_MTIME = mtime
    return _PAPERS_CACHE



SAMPLE_PAPERS = [
    {"title": "Amplitude amplification and estimation require inverses",
     "published": date(2025, 7, 31),
     "industries": ["Software", "Semiconductors", "Professional Services"],
     "score": 1, "url": "#"},
    {"title": "Gaussian Variation Field Diffusion for High-fidelity Video-to-4D Synthesis",
     "published": date(2025, 7, 31),
     "industries": ["Media & Entertainment", "Software", "Interactive Media & Services"],
     "score": 4, "url": "#"},
    {"title": "SUB: Benchmarking CBM Generalization via Synthetic Attribute Substitutions",
     "published": date(2025, 7, 31),
     "industries": ["Biotechnology", "Pharmaceuticals", "Software"],
     "score": 4, "url": "#"},
    {"title": "MonoFusion: Sparse-View 4D Reconstruction via Monocular Fusion",
     "published": date(2025, 7, 31),
     "industries": ["Media & Entertainment", "Interactive Media & Services", "Health Care"],
     "score": 4, "url": "#"},
    {"title": "Phi-Ground Tech Report: Advancing Perception in GUI Grounding",
     "published": date(2025, 7, 31),
     "industries": ["Software", "IT Services", "Media & Entertainment"],
     "score": 5, "url": "#"},
    {"title": "Half-Physics: Enabling Kinematic 3D Human Model with Physical Interactions",
     "published": date(2025, 7, 31),
     "industries": ["Media & Entertainment", "Interactive Media & Services", "Software"],
     "score": 6, "url": "#"},
    {"title": "XSpecMesh: Quality-Preserving Auto-Regressive Mesh Generation Acceleration",
     "published": date(2025, 7, 31),
     "industries": ["Software", "Media & Entertainment", "Interactive Media & Services"],
     "score": 4, "url": "#"},
    {"title": "Cascaded Information Disclosure: Generalized Evaluation of Problem Solving",
     "published": date(2025, 7, 31),
     "industries": ["Software", "IT Services", "Professional Services"],
     "score": 4, "url": "#"},
]

# ---- add near the top of views.py ----
DEFAULT_CRITERIA = {
    "weight_problems": 1.0,
    "weight_ideas": 1.0,
    "weight_industry": 1.0,
    "weight_market": 1.0,
    "weight_feasibility": 1.0,
}

def _to_float(val, default):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default

def _parse_criteria_from_request(request):
    """
    Reads user criteria from POST (form name 'criteria'), saves to session,
    prints them to the server log, and returns (criteria_dict, did_post_bool).
    """
    if request.method == "POST" and request.POST.get("form") == "criteria":
        c = {
            "weight_problems": _to_float(request.POST.get("weight_problems"), DEFAULT_CRITERIA["weight_problems"]),
            "weight_ideas": _to_float(request.POST.get("weight_ideas"), DEFAULT_CRITERIA["weight_ideas"]),
            "weight_industry": _to_float(request.POST.get("weight_industry"), DEFAULT_CRITERIA["weight_industry"]),
            "weight_market": _to_float(request.POST.get("weight_market"), DEFAULT_CRITERIA["weight_market"]),
            "weight_feasibility": _to_float(request.POST.get("weight_feasibility"), DEFAULT_CRITERIA["weight_feasibility"]),
        }
        request.session["criteria"] = c
        print(">>> User criteria saved:", c, flush=True)
        return c, True
    # GET or no form: load from session or defaults
    return request.session.get("criteria", DEFAULT_CRITERIA.copy()), False

# (optional) use later for custom scoring with the user’s weights
def compute_demo_score(paper, c):
    """
    Example placeholder that combines an existing paper 'score' with user weights.
    Swap with your real logic later.
    """
    base = paper.get("score", 0)
    total_weight = (
        c["weight_problems"]
        + c["weight_ideas"]
        + c["weight_industry"]
        + c["weight_market"]
        + c["weight_feasibility"]
    )
    return base * total_weight


def _matches_query(paper, q: str) -> bool:
    if not q:
        return True
    q = q.lower()
    return (
        q in paper["title"].lower()
        or any(q in ind.lower() for ind in paper["industries"])
        or q in paper["published"].isoformat()
    )


def home(request):
    criteria, did_post = _parse_criteria_from_request(request)
    if did_post:
        from django.shortcuts import redirect
        return redirect("home")

    q = (request.GET.get("q") or "").strip()

    try:
        per_page = int(request.GET.get("per_page", 10))
    except ValueError:
        per_page = 10
    per_page = max(1, min(50, per_page))
    per_page_options = [10, 25, 50]

    source = get_papers()
    filtered = [p for p in source if _matches_query(p, q)]
    filtered.sort(key=lambda p: (p["published"], p["score"]), reverse=True)
    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)

    try:
        page = int(request.GET.get("page", 1))
    except ValueError:
        page = 1
    page = max(1, min(total_pages, page))

    start = (page - 1) * per_page
    end = start + per_page
    page_items = filtered[start:end]
    paginator = Paginator(filtered, per_page)

    try:
        page_number = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_number = 1

    page_obj = paginator.get_page(page_number)  # safe clamp
    papers = list(page_obj.object_list)

    # “Showing X–Y of Z”
    start_index = page_obj.start_index() if paginator.count else 0
    end_index = page_obj.end_index() if paginator.count else 0

    # Elided page range (compact page buttons)
    page_range = paginator.get_elided_page_range(
        number=page_obj.number,
        on_each_side=1,
        on_ends=1,
    )


    context = {
        "papers": papers,
        "q": q,
        "per_page": per_page,
        "per_page_options": per_page_options,
        "page": page_obj.number,
        "total_pages": paginator.num_pages,
        "page_numbers": list(range(1, total_pages + 1)),
        "page_range": list(page_range),
        "total": paginator.count,
        "start_index": start_index,
        "end_index": end_index,
        # Updated branding ↓
        "brand": "Imperial",
        "product_title": "SciScout",
        "is_demo": True,
        "criteria":criteria

    }
    return render(request, "Scout/home.html", context)

seen = set()
for i, p in enumerate(SAMPLE_PAPERS):
    base = p.get("slug") or p.get("title") or f"paper-{i}"
    s = slugify(base)
    if not s or s in seen:           # avoid empty or duplicate slugs
        s = f"paper-{i}"
    p["slug"] = s
    seen.add(s)

def paper_detail(request, paper_id):
    paper = next((p for p in get_papers() if str(p["id"]) == str(paper_id)), None)
    if not paper:
        from django.http import Http404
        raise Http404("Paper not found")
    abstract = paper.get("summary_background") or paper.get("abstract") or ""
    ai = score_abstract_with_gemini(abstract)
    idea_text = abstract or paper.get("title", "")
    try:
        signals_data = find_signals(idea_text)  # full JSON: { idea, summary, signals[] }
        best_signal = find_top_signal(idea_text)  # optional: single best item (or None)
    except Exception as e:
        # Don’t 500 the page if the API hiccups
        signals_data = {"idea": idea_text, "summary": "Signals unavailable.", "signals": []}
        best_signal = None
    return render(request, "Scout/detail.html", {
        "paper": paper,
        "ai_score":ai,
        "brand": "Imperial",
        "product_title": "SciScout",
        "is_demo": True,
        "signals_data": signals_data,
        "best_signal": best_signal
    })
