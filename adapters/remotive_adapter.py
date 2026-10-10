import html
import re
from typing import List
import httpx
from models import JobPosting

REMOTIVE_URL = "https://remotive.com/api/remote-jobs?category=software-dev&limit=25"
HEADERS = {"User-Agent": "JobScoutAgent/2.0 (rohit; job-matcher)"}

def clean_description(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    clean = re.sub(r"<.*?>", " ", text)
    return " ".join(clean.split())[:2000]

def fetch_remotive_jobs(limit: int = 25) -> List[JobPosting]:
    print("📡 Fetching Remotive postings...")
    try:
        resp = httpx.get(REMOTIVE_URL, headers=HEADERS, timeout=15.0)
        if resp.status_code != 200:
            print(f"⚠️ Remotive returned HTTP {resp.status_code}")
            return []
        
        data = resp.json().get("jobs", [])
        postings: List[JobPosting] = []

        for item in data[:limit]:
            job_id = f"remotive_{item.get('id')}"
            postings.append(JobPosting(
                id=job_id,
                position=item.get("title", "Software Engineer"),
                company=item.get("company_name", "Remote Company"),
                location=item.get("candidate_required_location", "Remote"),
                tags=item.get("tags", []),
                description=clean_description(item.get("description", "")),
                url=item.get("url", ""),
                source="remotive"
            ))
        return postings
    except Exception as e:
        print(f"❌ Failed to fetch Remotive: {e}")
        return []

if __name__ == "__main__":
    jobs = fetch_remotive_jobs(5)
    print(f"✅ Fetched {len(jobs)} Remotive jobs:")
    for j in jobs:
        print(f"  • {j.position} @ {j.company}")