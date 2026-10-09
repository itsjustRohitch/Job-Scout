import os
import time
import sqlite3
import httpx
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()

if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN missing in .env")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

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
    """Sends a quick toast/banner notification back to the user in Telegram."""
    try:
        httpx.post(
            f"{BASE_URL}/answerCallbackQuery",
            json={"callback_query_id": callback_query_id, "text": text, "show_alert": False},
            timeout=10.0
        )
    except Exception as e:
        print(f"⚠️ Failed to answer callback query: {e}")

def run_listener():
    print("🤖 Telegram Action Listener started. Polling for button clicks...")
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

        except httpx.RequestError as e:
            print(f"⚠️ Polling network exception: {e}")
            time.sleep(2)
        except KeyboardInterrupt:
            print("\n🛑 Listener stopped by user.")
            break

if __name__ == "__main__":
    run_listener()