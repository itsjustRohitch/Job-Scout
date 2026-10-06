import sqlite3
import json
import httpx
from pydantic import BaseModel, Field
from typing import List, Optional

# --- 1. DATA MODEL (Data Contract) ---
# This ensures every job has valid types before touching our database.
class JobPosting(BaseModel):
    id: str
    position: str
    company: str
    url: str
    tags: List[str] = Field(default_factory=list)
    description: Optional[str] = ""

# --- 2. DATABASE SETUP ---
def init_db(db_path: str = "jobs.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # id TEXT PRIMARY KEY ensures no duplicates can ever be inserted
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            position TEXT,
            company TEXT,
            url TEXT,
            tags TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

# --- 3. INGESTION ENGINE ---
def run_pipeline():
    conn = init_db()
    cursor = conn.cursor()
    
    url = "https://remoteok.com/api"
    # RemoteOK requires a custom User-Agent header, otherwise it blocks Python scripts
    headers = {"User-Agent": "JobScoutBot/1.0 (Student Project)"}
    
    print("📡 Fetching live jobs from API...")
    response = httpx.get(url, headers=headers, timeout=15.0)
    
    if response.status_code != 200:
        print(f"❌ Failed to fetch: HTTP {response.status_code}")
        return

    raw_items = response.json()
    # The first item in RemoteOK's API output is a legal disclaimer, not a job, so we skip it
    job_items = [item for item in raw_items if "id" in item]
    
    new_jobs_count = 0

    print(f"🔍 Parsing {len(job_items)} postings through Pydantic...")
    for item in job_items:
        try:
            # Pydantic validates and normalizes the raw dict
            job = JobPosting(
                id=str(item.get("id")),
                position=item.get("position", "Unknown Title"),
                company=item.get("company", "Unknown Company"),
                url=item.get("url", ""),
                tags=item.get("tags", []) if isinstance(item.get("tags"), list) else [],
                description=item.get("description", "")
            )
            
            # INSERT OR IGNORE skips silently if job.id already exists in SQLite
            cursor.execute("""
                INSERT OR IGNORE INTO jobs (id, position, company, url, tags, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                job.id,
                job.position,
                job.company,
                job.url,
                json.dumps(job.tags),  # Store list as a JSON string in SQLite
                job.description
            ))
            
            # If a row was actually inserted (not ignored), increment counter
            if cursor.rowcount > 0:
                new_jobs_count += 1
                
        except Exception as err:
            # If an item has weird corrupted data, log and keep going
            print(f"⚠️ Skipped malformed record: {err}")
            continue

    conn.commit()
    conn.close()
    print(f"✅ Success! Ingested {new_jobs_count} brand-new jobs into jobs.db")

if __name__ == "__main__":
    run_pipeline()