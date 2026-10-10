import os
import time
import threading
import httpx
from dotenv import load_dotenv

import db
from enricher import enrich_job_if_needed

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN missing in .env")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma3:4b"

def register_bot_commands():
    """Registers bot commands with Telegram so they appear in the UI command menu."""
    commands = [
        {"command": "status", "description": "View scout metrics and triage tallies"},
        {"command": "saved", "description": "List jobs marked for application"},
        {"command": "pitch", "description": "Generate cold pitch: /pitch <job_id>"},
        {"command": "run", "description": "Trigger an immediate scout pipeline sweep"},
        {"command": "help", "description": "Show available bot commands"}
    ]
    try:
        resp = httpx.post(f"{BASE_URL}/setMyCommands", json={"commands": commands}, timeout=10.0)
        if resp.status_code == 200:
            print("📋 Registered Telegram command menu successfully.")
    except Exception as e:
        print(f"⚠️ Failed to register command menu: {e}")

def send_reply(chat_id: str, text: str, parse_mode: str = "HTML"):
    try:
        httpx.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10.0
        )
    except Exception as e:
        print(f"⚠️ Failed to send Telegram reply: {e}")

def answer_callback_query(callback_query_id: str, text: str):
    try:
        httpx.post(
            f"{BASE_URL}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text, "show_alert": False},
            timeout=10.0
        )
    except Exception as e:
        print(f"⚠️ Failed to answer callback query: {e}")

def get_pipeline_stats() -> str:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs;")
        total_jobs = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 60;")
        matches = cursor.fetchone()[0]

        cursor.execute("SELECT application_status, COUNT(*) FROM jobs GROUP BY application_status;")
        counts = dict(cursor.fetchall())

    return (
        f"📊 <b>Job Scout Pipeline Status</b>\n\n"
        f"📥 <b>Total Ingested:</b> {total_jobs}\n"
        f"🎯 <b>Matches (>=60):</b> {matches}\n\n"
        f"<b>Tracker Breakdown:</b>\n"
        f"• 🎉 Applied: <b>{counts.get('applied', 0)}</b>\n"
        f"• ⭐ Saved: <b>{counts.get('saved', 0)}</b>\n"
        f"• 🗑️ Passed: <b>{counts.get('pass', 0)}</b>\n"
        f"• ⏳ Pending: <b>{counts.get('pending', 0)}</b>"
    )

def get_saved_jobs(limit: int = 5) -> str:
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, position, company, url 
            FROM jobs 
            WHERE application_status = 'saved'
            ORDER BY match_score DESC
            LIMIT ?;
        """, (limit,))
        rows = cursor.fetchall()

    if not rows:
        return "⭐ No jobs currently marked as <b>Saved</b>."

    lines = ["⭐ <b>Active Saved Roles:</b>\n"]
    for row in rows:
        lines.append(f"• <b>{row['position']}</b> @ {row['company']}\n  🆔 <code>{row['id']}</code>\n  🔗 <a href='{row['url']}'>Apply Link</a>")
    return "\n\n".join(lines)

def generate_pitch(job_identifier: str) -> str:
    """Uses Gemma 3:4B to draft a concise, high-impact cold message."""
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, position, company, description 
            FROM jobs 
            WHERE id = ? OR company LIKE ?
            LIMIT 1;
        """, (job_identifier, f"%{job_identifier}%"))
        row = cursor.fetchone()

    if not row:
        return f"⚠️ No posting found matching ID/Company: <code>{job_identifier}</code>"

    job_id = row["id"]
    pos = row["position"]
    comp = row["company"]

    # Target deep enrichment before prompt construction
    full_desc = enrich_job_if_needed(job_id)

    from analyzer import load_candidate_profile, build_system_context
    profile = load_candidate_profile()
    profile_ctx = build_system_context(profile)

    prompt = f"""You are a direct, senior software engineer. Write a cold outreach message (max 120 words) from {profile.get('name', 'Rohit')} to the hiring team at {comp} for the {pos} role.

Candidate Background:
{profile_ctx}

Job Details:
{full_desc[:2500]}

Rules:
1. No generic greetings ("I hope this finds you well"). Start directly with value.
2. Specifically cite Rohit's Python data pipeline / LLM orchestration work and connect it directly to their tech needs.
3. Professional, crisp, low fluff, ending with a straightforward call to chat."""

    try:
        resp = httpx.post(
            OLLAMA_GENERATE_URL,
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=90.0
        )
        if resp.status_code == 200:
            pitch_text = resp.json().get("response", "").strip()
            return f"✉️ <b>Pitch for {pos} @ {comp}:</b>\n\n{pitch_text}"
        return f"⚠️ LLM Error: HTTP {resp.status_code}"
    except Exception as e:
        return f"⚠️ Failed to generate pitch: {str(e)[:60]}"

def handle_text_command(text: str, chat_id: str):
    parts = text.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd in ["/status", "/stats"]:
        send_reply(chat_id, get_pipeline_stats())

    elif cmd == "/saved":
        send_reply(chat_id, get_saved_jobs())

    elif cmd == "/pitch":
        if not arg:
            send_reply(chat_id, "ℹ️ Usage: <code>/pitch &lt;job_id_or_company&gt;</code>\nExample: <code>/pitch techolution</code>")
            return
        send_reply(chat_id, f"✍️ Enriching requirements & drafting pitch for <code>{arg}</code>...")
        pitch = generate_pitch(arg)
        send_reply(chat_id, pitch)

    elif cmd == "/run":
        send_reply(chat_id, "🚀 Triggering scout cycle in background...")
        from main import run_scout_cycle
        threading.Thread(target=run_scout_cycle, daemon=True).start()

    elif cmd in ["/start", "/help"]:
        help_text = (
            "🤖 <b>Job Scout Command Deck</b>\n\n"
            "<code>/status</code> - View pipeline tallies\n"
            "<code>/saved</code> - View saved jobs and IDs\n"
            "<code>/pitch &lt;id/company&gt;</code> - Generate outreach email\n"
            "<code>/run</code> - Trigger an immediate scout sweep\n"
            "<code>/help</code> - Show command list\n"
        )
        send_reply(chat_id, help_text)

def run_listener():
    register_bot_commands()
    print("🤖 Telegram Action Listener started. Polling for commands & clicks...")
    offset = 0

    while True:
        try:
            resp = httpx.get(
                f"{BASE_URL}/getUpdates",
                params={"offset": offset, "timeout": 20},
                timeout=30.0
            )

            if resp.status_code != 200:
                print(f"⚠️ Telegram polling error [{resp.status_code}]")
                time.sleep(3)
                continue

            for item in resp.json().get("result", []):
                offset = item["update_id"] + 1

                if "callback_query" in item:
                    cb = item["callback_query"]
                    cb_data = cb.get("data", "")
                    if ":" in cb_data:
                        action, job_id = cb_data.split(":", 1)
                        db.update_job_status(job_id, action)
                        toasts = {
                            "applied": "🎉 Marked as APPLIED!",
                            "saved": "⭐ Saved for review.",
                            "pass": "🗑️ Passed and archived."
                        }
                        answer_callback_query(cb["id"], toasts.get(action, "Updated"))
                        print(f"📥 State changed: Job [{job_id}] -> {action.upper()}")

                elif "message" in item:
                    msg = item["message"]
                    sender_id = str(msg.get("chat", {}).get("id", ""))
                    msg_text = msg.get("text", "")

                    if CHAT_ID and sender_id != CHAT_ID:
                        continue

                    if msg_text.startswith("/"):
                        print(f"💬 Command received: {msg_text}")
                        handle_text_command(msg_text, sender_id)

        except httpx.RequestError:
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n🛑 Listener stopped.")
            break

if __name__ == "__main__":
    run_listener()