import html
import re
from typing import List
import httpx
from bs4 import BeautifulSoup
from models import JobPosting

LINKEDIN_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

EXCLUDE_TITLE_TOKENS = {
    "senior", "sr.", "sr", "lead", "principal", "manager", 
    "architect", "staff", "director", "head", "5-", "6-", "7-", "8-", "10+"
}

TARGET_QUERIES = [
    "Python Intern",
    "Software Engineer Intern",
    "Junior Backend Developer",
    "Associate Software Engineer"
]

def clean_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = html.unescape(raw_text)
    clean = re.sub(r"\s+", " ", text)
    return clean.strip()

def is_entry_level(title: str) -> bool:
    title_lower = title.lower()
    for token in EXCLUDE_TITLE_TOKENS:
        if token in title_lower:
            return False
    return True

def fetch_linkedin_india_jobs(max_items: int = 25) -> List[JobPosting]:
    print("📡 Fetching LinkedIn India early-career postings...")
    postings: List[JobPosting] = []
    seen_ids = set()

    for query in TARGET_QUERIES:
        if len(postings) >= max_items:
            break

        params = {
            "keywords": query,
            "location": "India",
            "f_TPR": "r604800", # Past 1 week
            "start": 0
        }

        try:
            resp = httpx.get(LINKEDIN_SEARCH_URL, params=params, headers=HEADERS, timeout=15.0)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            job_cards = soup.find_all("li")

            for card in job_cards:
                title_elem = card.find("h3", class_="base-search-card__title")
                company_elem = card.find("h4", class_="base-search-card__subtitle")
                location_elem = card.find("span", class_="job-search-card__location")
                link_elem = card.find("a", class_="base-card__full-link")

                if not (title_elem and company_elem and link_elem):
                    continue

                title = clean_text(title_elem.text)
                if not is_entry_level(title):
                    continue

                company = clean_text(company_elem.text)
                loc = clean_text(location_elem.text) if location_elem else "India"
                job_url = link_elem.get("href", "").split("?")[0]

                urn_match = re.search(r"(\d+)", job_url)
                job_id = f"li_{urn_match.group(1)}" if urn_match else f"li_{abs(hash(job_url))}"

                if job_id in seen_ids:
                    continue

                seen_ids.add(job_id)
                postings.append(JobPosting(
                    id=job_id,
                    position=title,
                    company=company,
                    location=loc,
                    tags=["India", "LinkedIn", "EarlyCareer", "Backend"],
                    description=f"Role: {title} at {company}. Location: {loc}. Early career target in India. Check direct posting for details.",
                    url=job_url,
                    source="linkedin_india"
                ))

                if len(postings) >= max_items:
                    break

        except Exception as e:
            print(f"⚠️ Error fetching query '{query}': {e}")
            continue

    return postings

if __name__ == "__main__":
    jobs = fetch_linkedin_india_jobs(max_items=8)
    print(f"\n✅ Fetched {len(jobs)} filtered target postings:")
    for j in jobs:
        print(f"  • {j.position} @ {j.company} ({j.location})")
        print(f"    🔗 {j.url}")