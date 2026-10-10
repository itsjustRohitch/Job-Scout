import html
from typing import List, Tuple

import httpx
from db import init_db, store_jobs
from adapters.hn_adapter import fetch_hn_jobs
from adapters.jobicy_adapter import fetch_jobicy_jobs
from adapters.linkedin_guest_adapter import fetch_linkedin_india_jobs
from adapters.remotive_adapter import fetch_remotive_jobs
from adapters.wwr_adapter import fetch_wwr_jobs
from models import JobPosting

REMOTEOK_API_URL = "https://remoteok.com/api"
HEADERS = {
    "User-Agent": "JobScoutAgent/2.0 (rohit; candidate matching engine)"
}

def fetch_remoteok_jobs() -> List[JobPosting]:
    try:
        response = httpx.get(REMOTEOK_API_URL, headers=HEADERS, timeout=15.0)
        response.raise_for_status()
        raw_data = response.json()

        postings = []
        for item in raw_data:
            if not isinstance(item, dict) or "id" not in item:
                continue
            postings.append(JobPosting(
                id=str(item.get("id")),
                position=item.get("position", "Unknown"),
                company=item.get("company", "Unknown"),
                location=item.get("location", "Remote"),
                tags=item.get("tags", []),
                description=item.get("description", ""),
                url=item.get("url", f"https://remoteok.com/l/{item.get('id')}"),
                source="remoteok"
            ))
        return postings
    except Exception as e:
        print(f"❌ RemoteOK Fetch Error: {e}")
        return []

def run_pipeline() -> Tuple[List[JobPosting], int]:
    init_db()

    print("📡 [1/6] Fetching RemoteOK postings...")
    rok_jobs = fetch_remoteok_jobs()

    print("📡 [2/6] Fetching Hacker News postings...")
    hn_jobs = fetch_hn_jobs(max_items=20)

    print("📡 [3/6] Fetching We Work Remotely postings...")
    wwr_jobs = fetch_wwr_jobs(limit=25)

    print("📡 [4/6] Fetching Remotive postings...")
    remotive_jobs = fetch_remotive_jobs(limit=25)

    print("📡 [5/6] Fetching Jobicy postings...")
    jobicy_jobs = fetch_jobicy_jobs(limit=25)

    print("📡 [6/6] Fetching LinkedIn India early-career postings...")
    linkedin_jobs = fetch_linkedin_india_jobs(max_items=25)

    all_jobs = rok_jobs + hn_jobs + wwr_jobs + remotive_jobs + jobicy_jobs + linkedin_jobs
    new_count = store_jobs(all_jobs)
    print(f"\n✅ Ingestion complete: {len(all_jobs)} parsed across 6 streams | {new_count} brand-new stored.")
    return all_jobs, new_count

if __name__ == "__main__":
    run_pipeline()