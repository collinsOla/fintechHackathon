import requests
import xml.etree.ElementTree as ET
import time
import json
import re

# 1. API Parameters
BASE_URL = "http://export.arxiv.org/api/query?"
query = 'cat:q-fin* OR cat:cs.LG' # Q-finance, CS
MAX_RESULTS = 1000
START_INDEX = 0
OUTPUT_FILENAME = "arxiv_fintech_papers_metadata.json"

# Full request URL
search_url = f"{BASE_URL}search_query={query}&start={START_INDEX}&max_results={MAX_RESULTS}&sortBy=submittedDate"

# 2. Execute Request and Obey Rate Limit
print(f"Requesting: {search_url}")
response = requests.get(search_url)

fintech_papers = []

if response.status_code == 200:
    # 3. Define BOTH Atom and ArXiv Namespaces for correct parsing
    NS = {
        'atom': 'http://www.w3.org/2005/Atom',
        'arxiv': 'http://arxiv.org/schemas/atom'
    }
    
    root = ET.fromstring(response.content)
    
    print("--- Starting XML Parsing ---")

    # Helper function for extracting simple text content
    def safe_extract(element, tag, namespace):
        found_tag = element.find(tag, namespace)
        return found_tag.text.strip() if found_tag is not None and found_tag.text is not None else 'N/A'

    # Loop through each entry (paper) in the Atom feed
    for entry in root.findall('atom:entry', NS):
        try:
            # --- CORE ATOM FIELDS ---
            title = safe_extract(entry, 'atom:title', NS)
            abstract = safe_extract(entry, 'atom:summary', NS)
            
            # Extract ArXiv ID and Version from the primary link
            id_link = safe_extract(entry, 'atom:id', NS)
            arxiv_id_match = re.search(r'arxiv\.org/abs/([\d\.A-Za-z]+v\d+)', id_link)
            
            if arxiv_id_match:
                full_id_version = arxiv_id_match.group(1)
                arxiv_id = full_id_version.split('v')[0]
                version = full_id_version.split('v')[-1]
            else:
                arxiv_id = id_link.split('/')[-1] if 'arxiv.org/abs/' in id_link else 'N/A'
                version = 'v1'
                
            # --- DATE FIELDS ---
            published_date = safe_extract(entry, 'atom:published', NS)
            updated_date = safe_extract(entry, 'atom:updated', NS)
            
            # --- CATEGORIES ---
            all_categories = []
            primary_category = 'N/A'
            
            for cat_tag in entry.findall('atom:category', NS):
                term = cat_tag.attrib.get('term')
                if term:
                    all_categories.append(term)
            
            if all_categories:
                primary_category = all_categories[0]
            
            # --- MATURITY/CREDIBILITY FIELDS (Using ArXiv Namespace) ---
            doi = safe_extract(entry, 'arxiv:doi', NS)
            journal_ref = safe_extract(entry, 'arxiv:journal_ref', NS)
            comments = safe_extract(entry, 'arxiv:comment', NS)

            

            fintech_papers.append({
                'arxiv_id': arxiv_id,
                'version': version,
                'title': title,
                'published_date': published_date,
                'updated_date': updated_date,
                'abstract': abstract,
                'primary_category': primary_category,
                'all_categories': all_categories,
                'comments': comments,
                'journal_ref': journal_ref,
                'doi': doi,
            })
            
        except Exception as e:
            print(f"Skipping entry due to parsing error: {e}")
            continue

    print(f"\n✅ Successfully harvested {len(fintech_papers)} papers.")
    
    # 4. Save Data to JSON File
    try:
        with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
            json.dump(fintech_papers, f, ensure_ascii=False, indent=4)
        print(f"💾 Data successfully saved to {OUTPUT_FILENAME}")
    except IOError as e:
        print(f"Error saving file: {e}")
        
else:
    print(f"❌ Error fetching data: HTTP {response.status_code}")

# ALWAYS respect the rate limit!
time.sleep(3)