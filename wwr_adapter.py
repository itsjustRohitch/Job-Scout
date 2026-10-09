import html
import re
from typing import List
import httpx
import feedparser
from models import JobPosting

WWR_PROGRAMMING_RSS = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

def clean_description(raw_html: str) -> str:
    """Strips HTML tags and compresses extra whitespace."""
    if not raw_html:
        return ""
    text = html.unescape(raw_html)
    clean = re.sub(r"<.*?>", " ", text)
    return " ".join(clean.split())[:2000]

def fetch_wwr_jobs(feed_url: str = WWR_PROGRAMMING_RSS, limit: int = 25) -> List[JobPosting]:
    """Fetches RSS via httpx with explicit timeout, then parses XML with feedparser."""
    print(f"📡 Fetching We Work Remotely RSS: {feed_url}...")
    try:
        response = httpx.get(feed_url, headers=HEADERS, timeout=15.0, follow_redirects=True)
        if response.status_code != 200:
            print(f"⚠️ WWR RSS returned HTTP status {response.status_code}")
            return []
        
        feed = feedparser.parse(response.text)
    except Exception as e:
        print(f"❌ Failed to download WWR RSS feed: {e}")
        return []

    if not feed.entries:
        print("⚠️ No entries found in WWR feed.")
        return []

    jobs: List[JobPosting] = []

    for entry in feed.entries[:limit]:
        raw_title = entry.get("title", "")
        if ":" in raw_title:
            parts = raw_title.split(":", 1)
            company = parts[0].strip()
            position = parts[1].strip()
        else:
            company = "We Work Remotely"
            position = raw_title.strip()

        entry_id = entry.get("id", entry.get("link", ""))
        clean_id = f"wwr_{re.sub(r'[^a-zA-Z0-9]', '', entry_id)[-24:]}"

        description = clean_description(entry.get("description", entry.get("summary", "")))
        tags = [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")]

        jobs.append(JobPosting(
            id=clean_id,
            position=position or "Software Engineer",
            company=company or "Remote Company",
            location="Remote",
            tags=tags if tags else ["remote", "programming"],
            description=description,
            url=entry.get("link", ""),
            source="we_work_remotely"
        ))

    return jobs

if __name__ == "__main__":
    print("Testing We Work Remotely Adapter...")
    sample_jobs = fetch_wwr_jobs(limit=5)
    print(f"✅ Fetched {len(sample_jobs)} postings:")
    for j in sample_jobs:
        print(f"💼 [{j.source}] {j.position} @ {j.company}")
        print(f"   🔗 {j.url}")