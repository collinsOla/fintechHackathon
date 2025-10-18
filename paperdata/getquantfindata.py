import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime, timedelta, timezone
import time

BASE_URL = "https://export.arxiv.org/oai2"
NAMESPACE = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/"
}

def harvest_qfin(from_date, until_date, max_records=15):
    """Harvest arXiv Quantitative Finance (q-fin) papers."""
    records = []
    params = {
        "verb": "ListRecords",
        "metadataPrefix": "arXiv",
        "from": from_date,
        "until": until_date,
        "set": "q-fin"
    }

    while True:
        print(f"Fetching batch... total so far: {len(records)}")
        resp = requests.get(BASE_URL, params=params)
        resp.raise_for_status()

        root = ET.fromstring(resp.content)
        for rec in root.findall(".//oai:record", NAMESPACE):
            meta = rec.find(".//arxiv:arXiv", NAMESPACE)
            if meta is None:
                continue

            record = {
                "id": meta.findtext("arxiv:id", default="", namespaces=NAMESPACE),
                "created": meta.findtext("arxiv:created", default="", namespaces=NAMESPACE),
                "updated": meta.findtext("arxiv:updated", default="", namespaces=NAMESPACE),
                "title": meta.findtext("arxiv:title", default="", namespaces=NAMESPACE).strip(),
                "abstract": meta.findtext("arxiv:abstract", default="", namespaces=NAMESPACE).strip(),
                "categories": meta.findtext("arxiv:categories", default="", namespaces=NAMESPACE),
                "set": "q-fin"
            }
            records.append(record)

            if len(records) >= max_records:
                print(f"Reached {max_records} records. Stopping.")
                return records

        # Pagination using resumptionToken
        token = root.find(".//oai:resumptionToken", NAMESPACE)
        if token is not None and token.text:
            params = {"verb": "ListRecords", "resumptionToken": token.text}
            time.sleep(1.5)  # polite delay
        else:
            break

    return records


if __name__ == "__main__":
    # Fetch last 30 days of Quantitative Finance papers
    until = datetime.now(timezone.utc).date()
    from_date = until - timedelta(days=30)

    papers = harvest_qfin(from_date.isoformat(), until.isoformat(), max_records=15)

    print(f"\nCollected {len(papers)} Quantitative Finance papers. Saving to JSON...")

    with open("arxiv_recent_qfin_15.json", "w", encoding="utf-8") as f:
        json.dump(papers, f, ensure_ascii=False, indent=2)

    print("✅ Saved as arxiv_recent_qfin_15.json")
