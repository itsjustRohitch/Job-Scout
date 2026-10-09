import os
import sqlite3
import html
import httpx
from dotenv import load_dotenv
from analyzer import analyze_job_fit

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

def send_telegram_alert(job_id: str, title: str, company: str, score: int, reason: str, dossier: str, url: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        print("⚠️ Telegram credentials not configured.")
        return False

    endpoint = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    clean_title = html.escape(title)
    clean_company = html.escape(company)
    clean_reason = html.escape(reason)
    clean_dossier = html.escape(dossier)

    message_text = (
        f"🎯 <b>Match Score: {score}/100</b>\n"
        f"💼 <b>Role:</b> {clean_title}\n"
        f"🏢 <b>Company:</b> {clean_company}\n"
        f"📌 <b>Signal:</b> <i>{clean_reason}</i>\n\n"
        f"📋 <b>Scout Dossier:</b>\n"
        f"{clean_dossier}"
    )

    # Telegram callback data limit is 64 bytes; pass action + db job_id
    payload = {
        "chat_id": CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "🔗 View Posting", "url": url}
                ],
                [
                    {"text": "✅ Applied", "callback_data": f"applied:{job_id}"},
                    {"text": "⭐ Save", "callback_data": f"saved:{job_id}"},
                    {"text": "❌ Pass", "callback_data": f"pass:{job_id}"}
                ]
            ]
        }
    }

    try:
        resp = httpx.post(endpoint, json=payload, timeout=15.0)
        if resp.status_code == 200:
            return True
        else:
            print(f"❌ Telegram API Error [{resp.status_code}]: {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to deliver Telegram message: {e}")
        return False

def dispatch_top_jobs(db_path: str = "jobs.db", min_score: int = 60, limit: int = 3):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, position, company, match_score, evaluation_reason, description, url
        FROM jobs
        WHERE match_score >= ? AND is_dispatched = 0
        ORDER BY match_score DESC
        LIMIT ?;
    """, (min_score, limit))

    jobs_to_send = cursor.fetchall()

    if not jobs_to_send:
        print("ℹ️ No new matched jobs awaiting dispatch.")
        conn.close()
        return

    print(f"🚀 Analyzing and dispatching {len(jobs_to_send)} top jobs to Telegram...\n")

    for job in jobs_to_send:
        job_id, pos, comp, score, reason, desc, url = job
        print(f"🧠 Generating LLM dossier for: {pos} @ {comp}...")

        dossier = analyze_job_fit(pos, comp, desc)

        if send_telegram_alert(job_id, pos, comp, score, reason, dossier, url):
            cursor.execute("""
                UPDATE jobs
                SET is_dispatched = 1, llm_dossier = ?
                WHERE id = ?;
            """, (dossier, job_id))
            conn.commit()
            print(f"✅ Dispatched with action buttons: {pos} @ {comp}")
        else:
            print(f"❌ Failed to dispatch: {pos}")

    conn.close()
    print("\n🏁 Scout dispatch cycle complete.")

if __name__ == "__main__":
    dispatch_top_jobs()