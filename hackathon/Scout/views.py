from datetime import date
from django.shortcuts import render
from google import genai

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
    }
    return render(request, "Scout/home.html", context)
