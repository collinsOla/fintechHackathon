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
import re
from html import unescape
from .content import arp_report_list_with_gemini
import re
from datetime import datetime
from typing import Optional, Dict, Any
# Scout/templatetags/signals_extras.py
import re
from django import template
import random

register = template.Library()
import re
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

_SIGNAL_PRIORITY = {
    "funding": 8, "mna": 8,
    "partnership": 6, "customer": 6, "regulatory": 6,
    "patent": 5, "hiring": 4, "oss": 3,
    "other": 1,
}

def _as_dict(x: Any) -> Dict[str, Any]:
    """Accept dict or JSON string; return dict ({} if invalid)."""
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        x = x.strip()
        if not x or x.lower() == "none":
            return {}
        try:
            return json.loads(x)
        except Exception:
            # try loose extraction if something wrapped it
            start, end = x.find("{"), x.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(x[start:end+1])
                except Exception:
                    return {}
    return {}

def _parse_date_safe(s: Optional[str]) -> datetime:
    try:
        return datetime.strptime((s or "").strip(), "%Y-%m-%d")
    except Exception:
        return datetime.min

def _score_signal(sig: Dict[str, Any]) -> int:
    t = (sig.get("type") or "").lower().strip()
    base = _SIGNAL_PRIORITY.get(t, 0)
    d = _parse_date_safe(sig.get("date"))
    # tie-break on recency (days since epoch)
    return base * 10_000_000 + int(d.timestamp() // 86400)

def normalize_signals_payload(payload: Any) -> Dict[str, Any]:
    """
    Accepts:
      - dict from find_signals(...)
      - or JSON string of that dict
      - or {} / None
    Returns: {"summary": str, "signals": List[Dict]}
    """
    data = _as_dict(payload)
    summary = data.get("summary") or ""
    signals = data.get("signals") or []
    if not isinstance(signals, list):
        signals = []
    # Coerce each signal to the expected fields
    out: List[Dict[str, Any]] = []
    for s in signals:
        if not isinstance(s, dict):
            continue
        out.append({
            "type": (s.get("type") or "other").lower(),
            "org": s.get("org") or "",
            "date": s.get("date") or "",
            "note": s.get("note") or "",
            "source": s.get("source") or "",
        })
    return {"summary": summary, "signals": out}

def pick_best_signal(signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not signals:
        return None
    return sorted(signals, key=_score_signal, reverse=True)[0]


HEAD_RE = re.compile(
    r'\\textbf\{\s*(\d\.)\s*([^}]+?)\s*\}\s*\\\\',  # e.g., \textbf{1. BACKGROUND & CONTEXT}\\
    flags=re.DOTALL | re.IGNORECASE
)

def _clean_tex(s: str) -> str:
    s = s.strip()
    s = re.sub(r'\\vspace\{[^}]*\}', ' ', s)
    s = s.replace(r'\noindent', ' ')
    s = s.replace(r'\\', '\n')
    s = re.sub(r'\s+\n', '\n', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = re.sub(r'\s{2,}', ' ', s)
    return unescape(s).strip()

def parse_gemini_output(gemini_output: str) -> dict:
    # Find all header matches with their spans
    matches = list(HEAD_RE.finditer(gemini_output))
    sections = {}

    # Helper to slice content between headers
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i+1].start() if i+1 < len(matches) else len(gemini_output)
        num = m.group(1).strip().rstrip('.')
        title = m.group(2).strip().upper()

        content = _clean_tex(gemini_output[start:end])

        key_map = {
            '1': 'background_context',
            '2': 'real_world_problems_solved',
            '3': 'market_analysis',
            '4': 'immediate_startup_patent_ideas'
        }
        key = key_map.get(num, f'section_{num}')
        sections[key] = content

    # Ensure all four keys exist, even if missing
    for k in ['background_context',
              'real_world_problems_solved',
              'market_analysis',
              'immediate_startup_patent_ideas']:
        sections.setdefault(k, "")

    return sections

# Example:
# parsed = parse_gemini_output(gemini_output_string)
# print(parsed['market_analysis'])




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
    
    for paper in papers:#
        paper["score"] = random.randint(1, 7)
    if paper["id"]=="2509.10432":
        paper["score"]=7

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
    
    idea_text = abstract or paper.get("title", "")

    # Open the file for reading
    with open("Scout/ideareports/top15_demo_ideas.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    content=[]
    gen = False
    for rec in data:
        
        if rec.get("id") == paper["id"]:
            ai = {
            "scores": {
                "problem_fit": rec.get("scores", {}).get("problem_fit"),
                "practicality_maturity": rec.get("scores", {}).get("practicality_maturity"),
                "novelty": rec.get("scores", {}).get("novelty"),
                "market_fit": rec.get("scores", {}).get("market_fit"),
                "partner_interest": rec.get("scores", {}).get("partner_interest"),
            },
            "trl": rec.get("trl"),
            "overall_commercialization": rec.get("overall_commercialization"),
                }       
        
            print("sif")
            gen=True
            gemout = rec.get("gemini_output")
            gemout = parse_gemini_output(gemout)
            background_context = gemout["background_context"]
            real_world_problems_solved = gemout["real_world_problems_solved"]
            market_analysis = gemout["market_analysis"]
            immediate_startup_patent_ideas = gemout["immediate_startup_patent_ideas"]
            content = [background_context,real_world_problems_solved,market_analysis,immediate_startup_patent_ideas]
    if gen == False:
        content = arp_report_list_with_gemini(paper["title"],abstract)
        ai = score_abstract_with_gemini(abstract)
    if paper["id"]=="2509.10432":
        signals_data={'idea': "AI-readiness describes the degree to which data may be optimally and ethically used for subsequent AI and Machine Learning (AI/ML) methods, where those methods may involve some combination of model training, data classification, and ethical, explainable prediction. The Bridge2AI consortium has defined the particular criteria a biomedical dataset may possess to render it AI-ready: in brief, a dataset's readiness is related to its FAIRness, provenance, degree of characterization, explainability, sustainability, and computability, in addition to its accompaniment with documentation about ethical data practices.\n  To ensure AI-readiness and to clarify data structure and relationships within Bridge2AI's Grand Challenges (GCs), particular types of metadata are necessary. The GCs within the Bridge2AI initiative include four data-generating projects focusing on generating AI/ML-ready datasets to tackle complex biomedical and behavioral research problems. These projects develop standardized, multimodal data, tools, and training resources to support AI integration, while addressing ethical data practices. Examples include using voice as a biomarker, building interpretable genomic tools, modeling disease trajectories with diverse multimodal data, and mapping cellular and molecular health indicators across the human body.\n  This report assesses the state of metadata creation and standardization in the Bridge2AI GCs, provides guidelines where required, and identifies gaps and areas for improvement across the program. New projects, including those outside the Bridge2AI consortium, would benefit from what we have learned about creating metadata as part of efforts to promote AI readiness.", 'summary': 'Momentum around AI-readiness for biomedical and healthcare data is strong, evidenced by significant funding rounds for companies developing AI infrastructure, healthcare-focused AI models, and data management solutions. Key partnerships are emerging between tech giants and healthcare providers to implement AI, while the Bridge2AI consortium actively releases AI-ready datasets and guidance for ethical data practices. Regulatory bodies like the USPTO and FDA are issuing guidance on AI-assisted inventions and AI-enabled devices, respectively. The open-source community is also contributing with projects focused on explainable AI and medical applications. Furthermore, there is a clear trend in hiring towards individuals with AI skills in the healthcare sector, indicating a broader shift towards an AI-ready workforce.', 'signals': [{'type': 'other', 'org': 'NIH Bridge2AI', 'date': '2024-10-25', 'note': "A paper titled 'AI-readiness for Biomedical Data: Bridge2AI Recommendations' was published, outlining criteria for biomedical data's AI-readiness and an evaluation method to assess dataset compliance.", 'source': 'https://pubmed.ncbi.nlm.nih.gov/39484409/'}, {'type': 'regulatory', 'org': 'FDA', 'date': '2024-12-05', 'note': 'The FDA issued final guidance on postmarket updates to AI-enabled devices, allowing for certain modifications after market entry through pre-determined change control plans (PCCPs).', 'source': 'https://www.medtechdive.com/news/fda-final-guidance-postmarket-updates-ai-ml-devices-PCCP/701625/'}, {'type': 'funding', 'org': 'DDN', 'date': '2025-01-10', 'note': 'Data storage company DDN received a $300 million strategic investment from Blackstone Group, intending to expand in industries like healthcare and accelerate product innovation for its AI data intelligence platform.', 'source': 'https://news.crunchbase.com/ai/biggest-funding-rounds-data-storage-biotech/'}, {'type': 'funding', 'org': 'Hippocratic AI', 'date': '2025-01-10', 'note': 'Hippocratic AI, a developer of a safety-focused large language model for healthcare, raised a $141 million Series B, valuing the company at $1.6 billion.', 'source': 'https://news.crunchbase.com/ai/biggest-funding-rounds-data-storage-biotech/'}, {'type': 'oss', 'org': 'ODSC / Various Open Source Projects', 'date': '2025-01-27', 'note': 'A report on the top 10 trending open-source AI repositories for 2025 included projects like Grok-1 (explainable AI) and OpenHands (software library for hand gesture recognition in medical applications), indicating a focus on transparency and specific healthcare uses.', 'source': 'https://medium.com/odsc/top-10-trending-open-source-ai-repositories-starting-off-2025-c636f0153833'}, {'type': 'patent', 'org': 'USPTO', 'date': '2024-02-13', 'note': 'The USPTO issued inventorship guidance for AI-assisted inventions, clarifying that only natural persons can be named as inventors on U.S. patents.', 'source': 'https://www.federalregister.gov/documents/2024/02/13/2024-02623/inventorship-guidance-for-ai-assisted-inventions'}, {'type': 'partnership', 'org': 'Microsoft / Stanford Medicine / Providence / Cognizant', 'date': '2024-03-11', 'note': 'Microsoft announced new collaborations with healthcare organizations like Stanford Medicine and Providence, and partners such as Cognizant, to deploy generative AI solutions and scale existing ones within healthcare.', 'source': 'https://blogs.microsoft.com/blog/2024/03/11/microsoft-makes-the-promise-of-ai-in-healthcare-real-through-new-collaborations-with-healthcare-organizations-and-partners/'}, {'type': 'other', 'org': 'Bridge2AI-Voice consortium', 'date': '2025-04-14', 'note': 'The Bridge2AI-Voice consortium published an initial feasibility study of its novel mobile application designed for voice data acquisition to improve voice data research.', 'source': 'https://www.frontiersin.org/articles/10.3389/fmed.2025.1384077/full'}, {'type': 'hiring', 'org': 'Microsoft / LinkedIn', 'date': '2024-05-08', 'note': 'A Microsoft and LinkedIn report indicated that 75% of global knowledge workers use AI at work, and 66% of leaders would not hire someone without AI skills, highlighting a significant shift in workforce demands.', 'source': 'https://www.microsoft.com/en-us/worklab/ai-at-work-is-here-now-comes-the-hard-part'}, {'type': 'oss', 'org': 'GitHub Accelerator', 'date': '2024-05-23', 'note': 'The 2024 GitHub Accelerator welcomed 11 open-source AI projects, including Giskard, an open-source library for testing and evaluating large language models (LLMs), which aims to enhance transparency and accountability in AI models.', 'source': 'https://github.blog/2024-05-23-2024-github-accelerator-meet-the-11-projects-shaping-open-source-ai/'}, {'type': 'other', 'org': 'Bridge2AI Voice project', 'date': '2025-06-04', 'note': "The Bridge2AI Voice project announced that researchers can now request controlled access to its original raw audio recordings, expanding the reach of one of the world's most comprehensive voice biomarker datasets.", 'source': 'https://commonfund.nih.gov/bridge2ai/news'}, {'type': 'other', 'org': 'Stanford Medicine / Stanford HAI', 'date': '2025-06-09', 'note': "Stanford's RAISE Health Symposium 2025 featured discussions on equipping the next generation of biomedical professionals for success in the AI era and innovative educational approaches using AI.", 'source': 'https://www.youtube.com/watch?v=FjI-9o1tQ8o'}, {'type': 'partnership', 'org': 'Google Health / US Department of Veterans Affairs (VA)', 'date': '2024-07-10', 'note': "Google has an ongoing data partnership with the US Department of Veterans Affairs, leveraging Google's DeepMind AI and de-identified patient data to predict acute kidney injury.", 'source': 'https://www.medicalproductoutsourcing.com/contents/view_online-exclusives/2024-07-10/partnerships-that-are-driving-ai-in-healthcare/'}, {'type': 'partnership', 'org': 'Royal Philips / Amazon Web Services (AWS)', 'date': '2024-07-10', 'note': 'Royal Philips announced it would use Amazon Web Services (AWS) to scale its solutions for digital pathology, aiming to help pathology labs store, manage, and analyze data with an AI-enabled platform.', 'source': 'https://www.medicalproductoutsourcing.com/contents/view_online-exclusives/2024-07-10/partnerships-that-are-driving-ai-in-healthcare/'}, {'type': 'partnership', 'org': 'First San Francisco Partners (FSFP)', 'date': '2025-07-29', 'note': 'First San Francisco Partners (FSFP) completed a multi-year partnership with a global health clinic to transform its data ecosystem, including establishing consistent metadata practices, strengthening governance, and enhancing AI readiness.', 'source': 'https://www.firstsanfranciscopartners.com/how-a-healthcare-leader-built-ai-ready-data-from-the-ground-up/'}, {'type': 'patent', 'org': 'USPTO', 'date': '2024-08-04', 'note': 'The USPTO released the Artificial Intelligence Patent Dataset (AIPD) 2023 update, which extends the original AIPD to all USPTO patent documents published through 2023 and incorporates an improved methodology for identifying AI within patents.', 'source': 'https://www.uspto.gov/sites/default/files/documents/OCE-AI-Patent-Dataset-2023.pdf'}, {'type': 'funding', 'org': 'Inspiren', 'date': '2025-09-26', 'note': 'Inspiren, a developer of an AI-powered platform and connected-device system for senior living communities, secured $100 million in a Series B round.', 'source': 'https://news.crunchbase.com/ai/the-weeks-10-biggest-funding-rounds-health-and-ai-lead-for-large-financings/'}, {'type': 'funding', 'org': 'Modular', 'date': '2025-09-26', 'note': 'Modular, a developer of an enterprise AI inference stack, raised $250 million in a Series C financing.', 'source': 'https://news.crunchbase.com/ai/the-weeks-10-biggest-funding-rounds-health-and-ai-lead-for-large-financings/'}, {'type': 'funding', 'org': 'Distyl AI', 'date': '2025-09-26', 'note': 'Distyl AI, a developer of AI tools for enterprise customers, scooped up a $175 million funding round.', 'source': 'https://news.crunchbase.com/ai/the-weeks-10-biggest-funding-rounds-health-and-ai-lead-for-large-financings/'}, {'type': 'funding', 'org': 'Empower Semiconductor', 'date': '2025-09-26', 'note': 'Empower Semiconductor, a developer of power-efficient AI processors, closed on more than $140 million in Series D financing.', 'source': 'https://news.crunchbase.com/ai/the-weeks-10-biggest-funding-rounds-health-and-ai-lead-for-large-financings/'}, {'type': 'hiring', 'org': 'Incredible Health', 'date': '2025-10-03', 'note': "Dr. Iman Abuzeid, Co-founder and CEO of Incredible Health, discussed the company's use of AI agents to improve the healthcare hiring experience.", 'source': 'https://www.youtube.com/watch?v=sI9m65yFhS0'}, {'type': 'other', 'org': 'NIH', 'date': '2025-10-09', 'note': "The National Institutes of Health (NIH) announced the Phase 1 winners of its $1-million Data Sharing Index ('S-Index') Challenge, designed to recognize and reward high-quality data sharing.", 'source': 'https://commonfund.nih.gov/bridge2ai/news'}]}
        best_signal={'type': 'funding', 'org': 'National Science Foundation (NSF)', 'date': '2024-10-01', 'note': "The NSF is funding the 'Smart Health and Biomedical Research in the Era of Artificial Intelligence and Advanced Data Science (SCH)' program, with awards of up to $1,200,000 over four years, to support transformative advancements in computer and information science for biomedical and public health.", 'source': 'https://www.nsf.gov/funding/pgm_summ.jsp?pims_id=505494'}
    

    else:
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
        "best_signal": best_signal,
        "content":content
    })