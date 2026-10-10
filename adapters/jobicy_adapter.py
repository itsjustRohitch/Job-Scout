import html
import re
from typing import List
import httpx
from models import JobPosting

JOBICY_URL = "https://jobicy.com/api/v2/remote-jobs?count=25&industry=engineering"
HEADERS = {"User-Agent": "JobScoutAgent/2.0 (rohit; job-matcher)"}

def clean_description(raw_html: str) -> str:
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    clean = re.sub(r"<.*?>", " ", text)
    return " ".join(clean.split())[:2000]

def fetch_jobicy_jobs(limit: int = 25) -> List[JobPosting]:
    print("📡 Fetching Jobicy postings...")
    try:
        resp = httpx.get(JOBICY_URL, headers=HEADERS, timeout=15.0)
        if resp.status_code != 200:
            print(f"⚠️ Jobicy returned HTTP {resp.status_code}")
            return []

        data = resp.json().get("jobs", [])
        postings: List[JobPosting] = []

        for item in data[:limit]:
            job_id = f"jobicy_{item.get('id')}"
            tags = item.get("jobIndustry", [])
            if isinstance(tags, str):
                tags = [tags]

            postings.append(JobPosting(
                id=job_id,
                position=item.get("jobTitle", "Software Engineer"),
                company=item.get("companyName", "Remote Company"),
                location=item.get("jobGeo", "Remote"),
                tags=tags,
                description=clean_description(item.get("jobDescription", item.get("jobExcerpt", ""))),
                url=item.get("url", ""),
                source="jobicy"
            ))
        return postings
    except Exception as e:
        print(f"❌ Failed to fetch Jobicy: {e}")
        return []

if __name__ == "__main__":
    jobs = fetch_jobicy_jobs(5)
    print(f"✅ Fetched {len(jobs)} Jobicy jobs:")
    for j in jobs:
        print(f"  • {j.position} @ {j.company}")