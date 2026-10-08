import sqlite3
import json
import httpx
from typing import List
from models import JobPosting
from hn_adapter import fetch_hn_jobs

REMOTEOK_API_URL = "https://remoteok.com/api"
HEADERS = {
    "User-Agent": "JobScoutAgent/2.0 (rohit; candidate matching engine)"
}

def init_db(db_path: str = "jobs.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            position TEXT,
            company TEXT,
            location TEXT DEFAULT 'Remote',
            tags TEXT,
            description TEXT,
            url TEXT,
            source TEXT DEFAULT 'remoteok',
            match_score INTEGER DEFAULT NULL,
            evaluation_reason TEXT DEFAULT NULL,
            is_reviewed INTEGER DEFAULT 0,
            is_dispatched INTEGER DEFAULT 0,
            llm_dossier TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # Auto-migrate any columns if using an older database file
    cursor.execute("PRAGMA table_info(jobs);")
    existing_cols = {row[1] for row in cursor.fetchall()}
    
    for col, col_type in [("location", "TEXT DEFAULT 'Remote'"), ("source", "TEXT DEFAULT 'remoteok'")]:
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col} {col_type};")

    conn.commit()
    conn.close()

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

def store_jobs(jobs: List[JobPosting], db_path: str = "jobs.db") -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    new_jobs_count = 0

    for job in jobs:
        try:
            cursor.execute("""
                INSERT INTO jobs (id, position, company, location, tags, description, url, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                job.id,
                job.position,
                job.company,
                job.location,
                json.dumps(job.tags),
                job.description,
                job.url,
                job.source
            ))
            new_jobs_count += 1
        except sqlite3.IntegrityError:
            # Primary key collision: already ingested
            continue

    conn.commit()
    conn.close()
    return new_jobs_count

def run_pipeline():
    init_db()
    
    print("📡 [1/2] Fetching RemoteOK postings...")
    rok_jobs = fetch_remoteok_jobs()
    
    print("📡 [2/2] Fetching Hacker News postings...")
    hn_jobs = fetch_hn_jobs(max_items=20)
    
    all_jobs = rok_jobs + hn_jobs
    new_count = store_jobs(all_jobs)
    print(f"✅ Ingestion complete: {len(all_jobs)} total parsed, {new_count} brand-new stored.")

if __name__ == "__main__":
    run_pipeline()