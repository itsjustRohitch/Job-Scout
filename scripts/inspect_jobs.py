import sqlite3
import json

conn = sqlite3.connect("jobs.db")
cursor = conn.cursor()

# 1. Total jobs count
cursor.execute("SELECT COUNT(*) FROM jobs;")
total = cursor.fetchone()[0]
print(f"📊 Total jobs stored: {total}\n")

# 2. Fetch top 5 roles with titles and companies
cursor.execute("""
    SELECT position, company, tags 
    FROM jobs 
    LIMIT 10;
""")

print("--- Sample Roles Ingested ---")
for idx, (title, company, tags_json) in enumerate(cursor.fetchall(), 1):
    tags = json.loads(tags_json)
    print(f"{idx}. {title} @ {company}")
    print(f"   Tags: {', '.join(tags[:4]) if tags else 'None'}\n")

conn.close()