import os
import re
import json
import httpx
from typing import Dict, Any

import db
import enricher
import dispatch
from evaluate import score_job
from bot_listener import generate_pitch

# --- 1. Tool Implementations ---

def tool_get_unreviewed_jobs(limit: int = 5) -> str:
    """Fetches up to `limit` unreviewed jobs with match_score >= 50."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, position, company, location, match_score, url 
            FROM jobs 
            WHERE application_status = 'pending' AND match_score >= 50
            ORDER BY match_score DESC, created_at DESC 
            LIMIT ?;
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
    return json.dumps(rows, indent=2)

def tool_enrich_job(job_id: str) -> str:
    """Enriches job requirements by fetching the full description text."""
    try:
        enriched_text = enricher.enrich_job_if_needed(job_id)
        if enriched_text and len(enriched_text) > 100:
            return json.dumps({
                "status": "enriched",
                "length": len(enriched_text),
                "preview": enriched_text[:300]
            })
        return json.dumps({"status": "no_new_enrichment_needed_or_available"})
    except Exception as e:
        return json.dumps({"error": f"Enrichment failed: {e}"})

def tool_evaluate_and_pitch(job_id: str) -> str:
    """Evaluates candidate fit and generates a personalized Ollama pitch."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
        job = cursor.fetchone()
        if not job:
            return json.dumps({"error": "Job not found"})
        
        job_dict = dict(job)
        title = job_dict.get("position", "")
        description = job_dict.get("description", "") or ""
        tags = [job_dict.get("source", "")]

        # Heuristic scoring
        score, reason = score_job(title=title, tags=tags, description=description)

        # Update database with fresh score
        cursor.execute("UPDATE jobs SET match_score = ? WHERE id = ?;", (score, job_id))
        conn.commit()

        # Generate pitch using job_id string
        pitch = ""
        if score >= 65:
            try:
                pitch = generate_pitch(job_id)
            except Exception as e:
                pitch = f"Pitch generation error: {e}"

        return json.dumps({
            "job_id": job_id,
            "score": score,
            "reason": reason,
            "pitch": pitch
        })

def tool_dispatch_alert(job_id: str, pitch: str) -> str:
    """Dispatches a high-signal match alert with the pitch to Telegram and updates status."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
        job = cursor.fetchone()
        if not job:
            return json.dumps({"error": "Job not found"})
        
        job_dict = dict(job)
        success = dispatch.send_telegram_alert(
            job_id=job_id,
            title=job_dict.get("position", ""),
            company=job_dict.get("company", ""),
            score=job_dict.get("match_score", 0),
            reason=job_dict.get("description", "")[:150] or "Strong keyword alignment",
            dossier=pitch,
            url=job_dict.get("url", "")
        )
        if success:
            # Mark job so the agent doesn't repeatedly evaluate the same role
            cursor.execute("UPDATE jobs SET application_status = 'saved' WHERE id = ?;", (job_id,))
            conn.commit()

        return json.dumps({"dispatched": success, "status_updated": "saved"})

def tool_update_status(job_id: str, status: str) -> str:
    """Updates the triage status of a job in SQLite (e.g. 'saved', 'pass')."""
    success = db.update_job_status(job_id, status)
    return json.dumps({"job_id": job_id, "status": status, "success": success})

# Tool Registry
TOOL_REGISTRY = {
    "get_unreviewed_jobs": tool_get_unreviewed_jobs,
    "enrich_job": tool_enrich_job,
    "evaluate_and_pitch": tool_evaluate_and_pitch,
    "dispatch_alert": tool_dispatch_alert,
    "update_status": tool_update_status
}

# --- 2. ReAct Prompt & LLM Execution ---

REACT_SYSTEM_PROMPT = """You are an Autonomous Career Scout Agent. Your goal is to review newly ingested software engineering job opportunities, perform on-demand enrichment, evaluate candidate stack fit, and alert the user via Telegram only for high-signal matches.

Available Tools:
1. get_unreviewed_jobs(limit: int): Returns a JSON list of pending jobs in SQLite.
2. enrich_job(job_id: str): Deep-scrapes the full JD requirements for a job URL.
3. evaluate_and_pitch(job_id: str): Scores candidate fit and drafts a tailored cold pitch.
4. dispatch_alert(job_id: str, pitch: str): Sends a priority alert to the user's Telegram.
5. update_status(job_id: str, status: str): Sets status to 'saved' or 'pass'.

You must follow the ReAct format strictly:
Thought: Describe your reasoning about what to do next.
Action: tool_name
Action Input: {"param_name": "param_value"}
Observation: (Result returned from the tool)
... (Repeat Thought -> Action -> Action Input -> Observation as needed)
Thought: I have evaluated the pending roles and taken necessary actions.
Final Answer: Summary of what you investigated, scored, dispatched, or discarded.
"""

def call_ollama(prompt: str, model: str = "gemma3:4b") -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 256,
            "stop": ["Observation:", "Observation"]
        }
    }
    try:
        res = httpx.post(url, json=payload, timeout=120.0)
        return res.json().get("response", "").strip()
    except Exception as e:
        return f"Error calling LLM: {e}"

# --- 3. Autonomous Supervisor Execution Loop ---

def run_agent_loop(objective: str, max_iterations: int = 8):
    print(f"\n🎯 [Agent Initialized] Objective: {objective}\n")
    trajectory = f"{REACT_SYSTEM_PROMPT}\n\nObjective: {objective}\n"

    for step in range(1, max_iterations + 1):
        print(f"--- Cycle {step}/{max_iterations} ---")
        llm_output = call_ollama(trajectory)
        print(llm_output)
        trajectory += llm_output + "\n"

        # Check if agent finished via Final Answer or Summary
        if "Final Answer:" in llm_output or "Summary:" in llm_output:
            print("\n✅ [Agent Finished Execution Cleanly]")
            break

        # Parse Action and Action Input
        action_match = re.search(r"Action:\s*(\w+)", llm_output)
        input_match = re.search(r"Action Input:\s*({.*?}|\[.*?\]|\".*?\"|\d+)", llm_output, re.DOTALL)

        if not action_match or not input_match:
            print("⚠️ ReAct syntax could not be parsed; prompting agent for correction.")
            trajectory += "Observation: Invalid syntax. Output 'Action: <tool_name>' followed by 'Action Input: <valid_json>'.\n"
            continue

        tool_name = action_match.group(1).strip()
        raw_input = input_match.group(1).strip()

        if tool_name not in TOOL_REGISTRY:
            observation = f"Error: Tool '{tool_name}' does not exist."
        else:
            try:
                # Handle inputs that are JSON objects, primitives, or raw values
                parsed_args = json.loads(raw_input) if raw_input.startswith(("{", "[")) else raw_input
                if isinstance(parsed_args, dict):
                    observation = TOOL_REGISTRY[tool_name](**parsed_args)
                elif isinstance(parsed_args, list):
                    observation = TOOL_REGISTRY[tool_name](*parsed_args)
                else:
                    observation = TOOL_REGISTRY[tool_name](parsed_args)
            except Exception as e:
                observation = f"Tool execution failed: {e}"

        print(f"⚙️ Observation: {observation}\n")
        trajectory += f"Observation: {observation}\n"

if __name__ == "__main__":
    test_objective = "Check the top 3 unreviewed jobs, inspect the requirements of the highest matching one, evaluate it, and notify me if score >= 75."
    run_agent_loop(test_objective)