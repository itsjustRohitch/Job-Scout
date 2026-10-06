import sqlite3
import json
import re

TARGET_PROFILE = {
    # Preferred roles (regex-friendly word boundaries)
    "roles": [
        r"\bsoftware engineer\b",
        r"\bsoftware developer\b",
        r"\bdeveloper\b",
        r"\bbackend\b",
        r"\bfull stack\b",
        r"\bdata analyst\b",
        r"\bmachine learning\b",
        r"\bml engineer\b",
        r"\bai engineer\b",
        r"\bpython\b"
    ],
    # Hard drop: Completely irrelevant industries/tracks
    "negative_roles": [
        r"\bsales\b",
        r"\badvisor\b",
        r"\bconsultant\b",
        r"\bdirector\b",
        r"\bautomotriz\b",
        r"\bmechanic\b",
        r"\bcustomer support\b",
        r"\bqa evaluator\b",
        r"\bvideo data annotator\b"
    ],
    # Seniority levels you do NOT want right now
    "senior_terms": [
        r"\bsenior\b",
        r"\bsr\.?\b",
        r"\blead\b",
        r"\bstaff\b",
        r"\bprincipal\b",
        r"\barchitect\b",
        r"\bhead of\b",
        r"\biii\b"
    ],
    # Terms that signal prime entry-level targets
    "entry_terms": [
        r"\bintern\b",
        r"\binternship\b",
        r"\bjunior\b",
        r"\bjr\.?\b",
        r"\bentry\b",
        r"\bassociate\b",
        r"\bgraduate\b"
    ],
    # Core technical skills to score
    "skills": [
        r"\bpython\b",
        r"\bsql\b",
        r"\bapi\b",
        r"\bbackend\b",
        r"\bfastapi\b",
        r"\bdjango\b",
        r"\bml\b",
        r"\bai\b",
        r"\bdata analysis\b"
    ]
}

def matches_any(pattern_list: list[str], text: str) -> list[str]:
    """Helper to find all matching regex patterns in text."""
    hits = []
    for pattern in pattern_list:
        if re.search(pattern, text, re.IGNORECASE):
            # Clean regex syntax for human-readable reasons
            clean_name = pattern.replace(r"\b", "").replace(r"\.?", "")
            hits.append(clean_name)
    return hits

def score_job(title: str, tags: list[str], description: str) -> tuple[int, str]:
    title_clean = title.lower()
    tags_clean = " ".join([t.lower() for t in tags])
    eval_text = f"{title_clean} {tags_clean}"

    # 1. Hard Disqualification Check
    disqualified = matches_any(TARGET_PROFILE["negative_roles"], eval_text)
    if disqualified:
        return (0, f"Disqualified: matched {', '.join(disqualified)}")

    score = 0
    reasons = []

    # 2. Target Role Match (Up to 50 pts)
    matched_roles = matches_any(TARGET_PROFILE["roles"], title_clean)
    if matched_roles:
        score += 50
        reasons.append(f"Role: {', '.join(matched_roles)}")

    # 3. Target Skills Match (15 pts per skill, max 45 pts)
    matched_skills = matches_any(TARGET_PROFILE["skills"], eval_text)
    if matched_skills:
        skill_pts = min(len(matched_skills) * 15, 45)
        score += skill_pts
        reasons.append(f"Skills: {', '.join(matched_skills)}")

    # 4. Seniority Check: Boost or Penalize
    senior_hits = matches_any(TARGET_PROFILE["senior_terms"], title_clean)
    entry_hits = matches_any(TARGET_PROFILE["entry_terms"], title_clean)

    if entry_hits:
        score += 15
        reasons.append(f"Entry-level bonus (+15): {', '.join(entry_hits)}")
    elif senior_hits:
        score -= 40
        reasons.append(f"Seniority penalty (-40): {', '.join(senior_hits)}")

    # Clamp score between 0 and 100
    score = max(0, min(100, score))

    if score == 0:
        return (0, "Irrelevant or cancelled by seniority penalty")

    return (score, " | ".join(reasons))

def reset_and_reevaluate(db_path: str = "jobs.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Reset all jobs to unreviewed so we can re-score everything with the fixed logic
    cursor.execute("UPDATE jobs SET is_reviewed = 0, match_score = NULL, evaluation_reason = NULL;")
    conn.commit()

    cursor.execute("SELECT id, position, company, tags, description, url FROM jobs;")
    jobs = cursor.fetchall()

    print(f"🔄 Re-evaluating all {len(jobs)} jobs with fixed regex & seniority rules...\n")
    
    top_matches = 0

    for job_id, title, company, tags_json, desc, url in jobs:
        tags = json.loads(tags_json) if tags_json else []
        score, reason = score_job(title, tags, desc or "")

        cursor.execute("""
            UPDATE jobs 
            SET match_score = ?, evaluation_reason = ?, is_reviewed = 1 
            WHERE id = ?;
        """, (score, reason, job_id))

        # Show anything with a viable score of 50 or above
        if score >= 50:
            top_matches += 1
            print(f"🎯 [{score}/100] {title} @ {company}")
            print(f"   Reason: {reason}")
            print(f"   Link:   {url}\n")

    conn.commit()
    conn.close()
    print(f"✅ Re-evaluation complete. Found {top_matches} high-signal jobs.")

def run_evaluation_loop(db_path: str = "jobs.db"):
    """Evaluates only newly ingested, unreviewed jobs."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Query only records that haven't been evaluated yet
    cursor.execute("""
        SELECT id, position, company, tags, description, url 
        FROM jobs 
        WHERE is_reviewed = 0 OR is_reviewed IS NULL;
    """)
    unreviewed = cursor.fetchall()

    if not unreviewed:
        print("⚡ No new unreviewed jobs to evaluate.")
        conn.close()
        return

    print(f"🧠 Evaluating {len(unreviewed)} new jobs...")
    scored_count = 0

    for job_id, title, company, tags_json, desc, url in unreviewed:
        tags = json.loads(tags_json) if tags_json else []
        score, reason = score_job(title, tags, desc or "")

        cursor.execute("""
            UPDATE jobs 
            SET match_score = ?, evaluation_reason = ?, is_reviewed = 1 
            WHERE id = ?;
        """, (score, reason, job_id))

        if score >= 50:
            scored_count += 1

    conn.commit()
    conn.close()
    print(f"✅ Evaluated {len(unreviewed)} jobs ({scored_count} matched profile criteria).")

def reset_and_reevaluate(db_path: str = "jobs.db"):
    """Admin function: Wipes previous review states and re-scores all jobs from scratch."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET is_reviewed = 0, match_score = NULL, evaluation_reason = NULL;")
    conn.commit()
    conn.close()
    run_evaluation_loop(db_path)

if __name__ == "__main__":
    run_evaluation_loop()