import os
import time
import sqlite3
import threading
import httpx
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN missing in .env")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_reply(chat_id: str, text: str, parse_mode: str = "HTML"):
    """Sends a text message back to the specified Telegram chat."""
    try:
        httpx.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10.0
        )
    except Exception as e:
        print(f"⚠️ Failed to send Telegram reply: {e}")

def update_job_status(job_id: str, new_status: str, db_path: str = "jobs.db") -> bool:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE jobs
            SET application_status = ?, is_reviewed = 1
            WHERE id = ?;
        """, (new_status, job_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated
    except Exception as e:
        print(f"❌ DB update error: {e}")
        return False

def answer_callback_query(callback_query_id: str, text: str):
    """Acknowledges button clicks with a toast notification."""
    try:
        httpx.post(
            f"{BASE_URL}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text, "show_alert": False},
            timeout=10.0
        )
    except Exception as e:
        print(f"⚠️ Failed to answer callback query: {e}")

def get_pipeline_stats(db_path: str = "jobs.db") -> str:
    """Calculates live pipeline tallies from SQLite."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM jobs;")
    total_jobs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 60;")
    matches = cursor.fetchone()[0]

    cursor.execute("SELECT application_status, COUNT(*) FROM jobs GROUP BY application_status;")
    counts = dict(cursor.fetchall())
    conn.close()

    applied = counts.get("applied", 0)
    saved = counts.get("saved", 0)
    passed = counts.get("pass", 0)
    pending = counts.get("pending", 0)

    return (
        f"📊 <b>Job Scout Pipeline Status</b>\n\n"
        f"📥 <b>Total Ingested:</b> {total_jobs}\n"
        f"🎯 <b>Matches (>=60):</b> {matches}\n\n"
        f"<b>Tracker Breakdown:</b>\n"
        f"• 🎉 Applied: <b>{applied}</b>\n"
        f"• ⭐ Saved: <b>{saved}</b>\n"
        f"• 🗑️ Passed: <b>{passed}</b>\n"
        f"• ⏳ Pending Triage: <b>{pending}</b>"
    )

def get_saved_jobs(db_path: str = "jobs.db", limit: int = 5) -> str:
    """Returns top saved opportunities awaiting application."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT position, company, url 
        FROM jobs 
        WHERE application_status = 'saved'
        ORDER BY match_score DESC
        LIMIT ?;
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return "⭐ No jobs currently marked as <b>Saved</b>."

    lines = ["⭐ <b>Active Saved Roles:</b>\n"]
    for pos, comp, url in rows:
        lines.append(f"• <b>{pos}</b> @ {comp}\n  🔗 <a href='{url}'>Apply Link</a>")
    return "\n\n".join(lines)

def handle_text_command(text: str, chat_id: str):
    """Dispatches slash commands received from Telegram."""
    cmd = text.strip().split()[0].lower()

    if cmd in ["/status", "/stats"]:
        stats_msg = get_pipeline_stats()
        send_reply(chat_id, stats_msg)

    elif cmd == "/saved":
        saved_msg = get_saved_jobs()
        send_reply(chat_id, saved_msg)

    elif cmd == "/run":
        send_reply(chat_id, "🚀 Triggering scout cycle in background...")
        # Run sweep without blocking long-polling listener
        from main import run_scout_cycle
        def worker():
            run_scout_cycle()
            send_reply(chat_id, "✅ Manual scout cycle complete.")
        threading.Thread(target=worker, daemon=True).start()

    elif cmd in ["/start", "/help"]:
        help_text = (
            "🤖 <b>Job Scout Command Deck</b>\n\n"
            "• <code>/status</code> - View pipeline metrics and triage tallies\n"
            "• <code>/saved</code> - List roles saved for application\n"
            "• <code>/run</code> - Trigger an immediate scout sweep\n"
            "• <code>/help</code> - Show available commands"
        )
        send_reply(chat_id, help_text)

def run_listener():
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

            data = resp.json()
            updates = data.get("result", [])

            for item in updates:
                offset = item["update_id"] + 1

                # 1. Handle Inline Button Clicks
                if "callback_query" in item:
                    cb = item["callback_query"]
                    cb_id = cb["id"]
                    cb_data = cb.get("data", "")

                    if ":" in cb_data:
                        action, job_id = cb_data.split(":", 1)
                        success = update_job_status(job_id, action)

                        status_messages = {
                            "applied": "🎉 Marked as APPLIED! Added to tracking list.",
                            "saved": "⭐ Saved for review later.",
                            "pass": "🗑️ Passed and archived."
                        }
                        toast = status_messages.get(action, f"Updated to: {action}")
                        answer_callback_query(cb_id, toast)
                        print(f"📥 State changed: Job [{job_id}] -> {action.upper()} (DB updated: {success})")

                # 2. Handle Text Slash Commands
                elif "message" in item:
                    msg = item["message"]
                    sender_chat_id = str(msg.get("chat", {}).get("id", ""))
                    msg_text = msg.get("text", "")

                    # Security check: only allow commands from your configured CHAT_ID
                    if CHAT_ID and sender_chat_id != CHAT_ID:
                        continue

                    if msg_text.startswith("/"):
                        print(f"💬 Command received: {msg_text}")
                        handle_text_command(msg_text, sender_chat_id)

        except httpx.RequestError as e:
            print(f"⚠️ Polling network exception: {e}")
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n🛑 Listener stopped by user.")
            break

if __name__ == "__main__":
    run_listener()