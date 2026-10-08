import os
import sqlite3
import html
import httpx
from dotenv import load_dotenv
from analyzer import analyze_job_fit

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not BOT_TOKEN or not CHAT_ID:
    print("⚠️ Warning: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")

def update_schema_for_dispatch(db_path: str = "jobs.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN is_dispatched INTEGER DEFAULT 0;")
        cursor.execute("ALTER TABLE jobs ADD COLUMN llm_dossier TEXT DEFAULT NULL;")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()

def send_telegram_message(message: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = httpx.post(url, json=payload, timeout=15.0)
        if response.status_code == 200:
            return True
        print(f"❌ Telegram API Error [{response.status_code}]: {response.text}")
        return False
    except Exception as e:
        print(f"❌ Network/Request Exception: {e}")
        return False

def dispatch_top_matches(db_path: str = "jobs.db", min_score: int = 60, limit: int = 3):
    update_schema_for_dispatch(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, position, company, match_score, evaluation_reason, description, url 
        FROM jobs 
        WHERE (is_dispatched = 0 OR is_dispatched IS NULL) 
          AND match_score >= ?
        ORDER BY match_score DESC
        LIMIT ?;
    """, (min_score, limit))
    
    matches = cursor.fetchall()

    if not matches:
        print("⚡ No new high-signal jobs to dispatch.")
        conn.close()
        return

    print(f"🚀 Analyzing and dispatching {len(matches)} top jobs to Telegram...\n")

    for job_id, title, company, score, reason, description, url in matches:
        print(f"🧠 Generating LLM dossier for: {title} @ {company}...")
        
        # 1. Run local LLM fit analysis
        dossier = analyze_job_fit(title, company, description or "")
        
        # 2. Escape variables to prevent broken HTML parsing
        safe_title = html.escape(str(title))
        safe_company = html.escape(str(company))
        safe_reason = html.escape(str(reason))
        safe_dossier = html.escape(str(dossier))
        
        # 3. Construct HTML payload
        text = (
            f"🎯 <b>Match Score: {score}/100</b>\n"
            f"💼 <b>Role:</b> {safe_title}\n"
            f"🏢 <b>Company:</b> {safe_company}\n"
            f"📌 <b>Signal:</b> <i>{safe_reason}</i>\n\n"
            f"📋 <b>Scout Dossier:</b>\n{safe_dossier}\n\n"
            f"🔗 <a href=\"{url}\">Apply Here</a>"
        )
        
        # 4. Dispatch
        success = send_telegram_message(text)
        if success:
            cursor.execute("""
                UPDATE jobs 
                SET is_dispatched = 1, llm_dossier = ? 
                WHERE id = ?;
            """, (dossier, job_id))
            conn.commit()
            print(f"✅ Dispatched with dossier: {title} @ {company}\n")
        else:
            print(f"❌ Failed to dispatch: {title}\n")

    conn.close()
    print("🏁 Daily scout dispatch completed.")

if __name__ == "__main__":
    dispatch_top_matches()