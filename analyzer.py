import json
import os
import httpx

OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"
PROFILE_PATH = os.path.join(os.path.dirname(__file__), "profile.json")

def load_candidate_profile() -> dict:
    """Loads candidate data from profile.json or returns safe defaults."""
    if not os.path.exists(PROFILE_PATH):
        return {
            "name": "Candidate",
            "core_skills": ["Python", "Backend Development"],
            "notable_projects": [],
            "pitch_style": "Technical and concise"
        }
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def build_system_context(profile: dict) -> str:
    skills_str = ", ".join(profile.get("core_skills", []))
    projects_str = "\n".join([
        f"- {p['name']}: {p['description']}" 
        for p in profile.get("notable_projects", [])
    ])
    
    return f"""Candidate Name: {profile.get('name', 'Candidate')}
Core Skills: {skills_str}
Key Projects:
{projects_str}
Pitch Tone: {profile.get('pitch_style', 'Technical, direct')}"""

def analyze_job_fit(position: str, company: str, description: str) -> str:
    """Uses local Gemma 3:4B to evaluate fit against the candidate's real profile."""
    profile = load_candidate_profile()
    profile_context = build_system_context(profile)
    
    prompt = f"""You are a technical career coach. Evaluate how well this candidate fits the following job posting.

=== CANDIDATE PROFILE ===
{profile_context}

=== TARGET JOB ===
Position: {position}
Company: {company}
Description:
{description[:1500]}

=== INSTRUCTIONS ===
Generate EXACTLY 3 bullet points using this format:
* Alignment: [Specific technical match between candidate's projects/skills and the job]
* Missing Tool: [One critical tool/skill from the job description the candidate needs to highlight or learn]
* Project Angle: [A concise, concrete project pitch showing how the candidate can solve a real problem for this company]

Do not include conversational filler, greetings, or extra text."""

    try:
        response = httpx.post(
            OLLAMA_GENERATE_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=90.0
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        else:
            return f"⚠️ LLM evaluation error (Status {response.status_code})"
    except Exception as e:
        return f"⚠️ LLM offline or unreachable: {str(e)[:50]}"

if __name__ == "__main__":
    print("Testing dynamic profile integration...")
    sample_desc = "Seeking a Backend Python Engineer to build scalable data ingestion pipelines, design RESTful APIs, and handle event-driven microservices."
    dossier = analyze_job_fit("Backend Engineer", "DataFlow Corp", sample_desc)
    print("\nGenerated Dossier:")
    print(dossier)