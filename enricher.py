import html
import re
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from db import get_connection

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

LINKEDIN_DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

def clean_html_text(raw_html: str) -> str:
    """Strips markup and excessive whitespace into structured text."""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(cleaned_lines)

def extract_linkedin_id(job_url_or_id: str) -> Optional[str]:
    """Extracts raw numeric ID from a job ID (e.g. 'li_4475402350') or LinkedIn URL."""
    match = re.search(r"(\d{8,})", job_url_or_id)
    return match.group(1) if match else None

def fetch_linkedin_full_description(job_id_or_url: str) -> Optional[str]:
    """Fetches full job description via LinkedIn guest jobPosting endpoint."""
    raw_id = extract_linkedin_id(job_id_or_url)
    if not raw_id:
        return None

    target_url = LINKEDIN_DETAIL_URL.format(job_id=raw_id)
    try:
        resp = httpx.get(target_url, headers=HEADERS, timeout=12.0)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        desc_div = soup.find("div", class_=lambda c: c and "show-more-less-html__markup" in c)
        if not desc_div:
            desc_div = soup.find("section", class_=lambda c: c and "description" in c)

        if desc_div:
            return clean_html_text(str(desc_div))
        return clean_html_text(resp.text)[:4000]
    except Exception as e:
        print(f"⚠️ Failed to enrich LinkedIn job {raw_id}: {e}")
        return None

def enrich_job_if_needed(job_id: str) -> str:
    """
    Checks if job description is short/preview. If so, enriches and persists
    the full description to SQLite, then returns the updated text.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, description, url, source FROM jobs WHERE id = ?;", (job_id,))
        row = cursor.fetchone()
        if not row:
            return ""

        current_desc = row["description"] or ""
        source = row["source"]
        url = row["url"]

        # If it's already a complete description (> 400 chars) and not a stub preview, return it
        if len(current_desc) > 400 and not current_desc.startswith("Role:"):
            return current_desc

        full_desc = None
        if "linkedin" in source or "linkedin.com" in url:
            full_desc = fetch_linkedin_full_description(job_id)

        if full_desc and len(full_desc) > len(current_desc):
            cursor.execute("UPDATE jobs SET description = ? WHERE id = ?;", (full_desc, job_id))
            conn.commit()
            return full_desc

        return current_desc