import html
import re
from typing import List, Optional
import httpx
from models import JobPosting

HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"

def get_latest_hiring_post_id() -> Optional[int]:
    """Finds the latest 'Who is hiring?' submission by 'whoishiring'."""
    try:
        user_resp = httpx.get(f"{HN_BASE_URL}/user/whoishiring.json", timeout=10.0)
        if user_resp.status_code != 200:
            return None
        
        submitted_ids = user_resp.json().get("submitted", [])
        for post_id in submitted_ids[:5]:
            item_resp = httpx.get(f"{HN_BASE_URL}/item/{post_id}.json", timeout=10.0)
            if item_resp.status_code == 200:
                item = item_resp.json()
                title = item.get("title", "")
                if "Who is hiring?" in title and item.get("type") == "story":
                    print(f"📌 Found thread: {title} (ID: {post_id})")
                    return post_id
        return None
    except Exception as e:
        print(f"❌ Failed to fetch HN hiring thread: {e}")
        return None

def parse_hn_comment(comment_data: dict) -> Optional[JobPosting]:
    raw_text = comment_data.get("text", "")
    if not raw_text or comment_data.get("deleted") or comment_data.get("dead"):
        return None

    # 1. Unescape HTML entities (converts &#x2F; -> / and &amp; -> &)
    unescaped_text = html.unescape(raw_text)

    # 2. Strip HTML tags
    clean_text = re.sub(r"<.*?>", " ", unescaped_text)
    clean_text = " ".join(clean_text.split())

    # 3. Parse header line (split by |)
    first_chunk = clean_text.split("\n")[0] if "\n" in clean_text else clean_text[:250]
    parts = [p.strip() for p in first_chunk.split("|") if p.strip()]

    company = "HN Startup"
    position = "Software Engineer"

    if len(parts) >= 2:
        # Avoid URLs or overly long strings as company names
        candidate_company = parts[0]
        if not candidate_company.startswith("http") and len(candidate_company) < 40:
            company = candidate_company
        
        candidate_role = parts[1]
        if len(candidate_role) < 60:
            position = candidate_role
    elif len(parts) == 1:
        if len(parts[0]) < 40 and not parts[0].startswith("http"):
            company = parts[0]

    item_id = str(comment_data.get("id"))
    hn_url = f"https://news.ycombinator.com/item?id={item_id}"

    return JobPosting(
        id=f"hn_{item_id}",
        position=position,
        company=company,
        location="Remote / Hybrid",
        tags=["hackernews", "startup"],
        description=clean_text[:2000],
        url=hn_url,
        source="hacker_news"
    )

def fetch_hn_jobs(max_items: int = 25) -> List[JobPosting]:
    thread_id = get_latest_hiring_post_id()
    if not thread_id:
        print("⚠️ Could not locate active HN hiring thread.")
        return []

    try:
        thread_resp = httpx.get(f"{HN_BASE_URL}/item/{thread_id}.json", timeout=10.0)
        kid_ids = thread_resp.json().get("kids", [])[:max_items]
        
        jobs: List[JobPosting] = []
        print(f"📡 Fetching {len(kid_ids)} HN postings...")
        
        for kid_id in kid_ids:
            c_resp = httpx.get(f"{HN_BASE_URL}/item/{kid_id}.json", timeout=10.0)
            if c_resp.status_code == 200:
                parsed = parse_hn_comment(c_resp.json())
                if parsed:
                    jobs.append(parsed)
                    
        return jobs
    except Exception as e:
        print(f"❌ Error fetching comments: {e}")
        return []