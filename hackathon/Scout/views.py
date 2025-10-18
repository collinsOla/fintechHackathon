from datetime import date
from django.shortcuts import render
from django.utils.text import slugify



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

    filtered = [p for p in SAMPLE_PAPERS if _matches_query(p, q)]
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

    context = {
        "papers": page_items,
        "q": q,
        "per_page": per_page,
        "per_page_options": per_page_options,
        "page": page,
        "total_pages": total_pages,
        "page_numbers": list(range(1, total_pages + 1)),
        "total": total,
        "start_index": start + 1 if total else 0,
        "end_index": min(end, total),
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

def paper_detail(request, slug: str):
    paper = next((p for p in SAMPLE_PAPERS if p["slug"] == slug), None)
    if not paper:
        from django.http import Http404
        raise Http404("Paper not found")
    return render(request, "Scout/detail.html", {"paper": paper, "brand": "Imperial", "product_title": "SciScout", "is_demo": True})

print(slugify("Gaussian Variation Field Diffusion for High-fidelity Video-to-4D Synthesis"))