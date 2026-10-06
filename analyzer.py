import subprocess
import time
import httpx
import re

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_HEALTH = "http://localhost:11434"
MODEL_NAME = "gemma3:4b"

CANDIDATE_PROFILE = """
Candidate: Rohit
Target Roles: Junior Backend Developer / Software Engineer / Data Analyst
Skills: Python, SQL, SQLite, Pydantic, REST APIs, Git, Basic ML, Data Structures & Algorithms
Profile: Final-year B.Tech student targeting internships and entry-level positions.
"""

def is_ollama_online() -> bool:
    """Quick 1-second ping to check if the Ollama local daemon is listening."""
    try:
        r = httpx.get(OLLAMA_HEALTH, timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False

def ensure_ollama_running() -> bool:
    """
    If Ollama is down, boots 'ollama serve' as a silent background process
    and polls until it is ready.
    """
    if is_ollama_online():
        return True

    print("⚠️ Ollama is not active. Launching background daemon...")
    try:
        # Launch headless process on Windows without opening a console window
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        )
        
        # Wait up to 6 seconds for the daemon to initialize
        for _ in range(6):
            time.sleep(1.0)
            if is_ollama_online():
                print("✅ Ollama background service is up and running.")
                return True
                
        print("❌ Ollama launch timed out.")
        return False
    except FileNotFoundError:
        print("❌ 'ollama' executable not found in system PATH.")
        return False

def clean_html(raw_html: str) -> str:
    cleanr = re.compile(r"<.*?>")
    cleantext = re.sub(cleanr, "", raw_html)
    return " ".join(cleantext.split())

def analyze_job_fit(job_title: str, company: str, job_description: str) -> str:
    """
    Runs job fit analysis. Falls back gracefully if Ollama cannot be started.
    """
    if not ensure_ollama_running():
        return "• LLM Gap Analysis skipped (Ollama service unavailable)."

    cleaned_desc = clean_html(job_description)[:1000]
    prompt = f"""
You are a direct, technical career mentor. Compare the candidate against this job.

{CANDIDATE_PROFILE}

Role: {job_title} @ {company}
Description snippet:
{cleaned_desc}

Provide EXACTLY three concise bullet points:
• Alignment: 1 core skill match between candidate and role.
• Missing Tool: 1-2 specific tech stack items in the description that the candidate must highlight or review.
• Project Angle: 1 actionable way to pitch this project (Python/SQLite ingestion agent) for this specific role.

Keep each bullet under 20 words. No conversational filler or introductions.
"""

    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "keep_alive": "10m"
            },
            timeout=90.0  # Increased to 90s for cold model loading into memory
        )
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        return "• LLM Gap Analysis unavailable (Non-200 API response)."
    except httpx.TimeoutException:
        return "• LLM Gap Analysis timed out (System busy)."
    except Exception as e:
        return f"• LLM Gap Analysis skipped: {e}"

if __name__ == "__main__":
    print("Testing auto-start & analysis pipeline...")
    sample_desc = "<p>Looking for a Python Backend Intern with experience in SQL, APIs, and Docker to build data pipelines.</p>"
    result = analyze_job_fit("Backend Intern", "Startup Inc", sample_desc)
    print("\n--- Output ---")
    print(result)