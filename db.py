import json
import sqlite3
from typing import Any, Dict, List, Optional
from models import JobPosting

DB_PATH = "jobs.db"

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Creates a connection with row-factory set for dict-like access."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = DB_PATH) -> None:
    """Initializes tables and safely runs migrations for schema evolution."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Core jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                position TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT DEFAULT 'Remote',
                tags TEXT,
                description TEXT,
                url TEXT,
                source TEXT DEFAULT 'remoteok',
                date_posted TEXT,
                match_score INTEGER DEFAULT 0,
                analysis TEXT,
                is_reviewed INTEGER DEFAULT 0,
                application_status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Runs / telemetry table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration_seconds REAL,
                sources_checked INTEGER,
                jobs_ingested INTEGER,
                jobs_new INTEGER,
                matches_found INTEGER,
                status TEXT DEFAULT 'success',
                error_message TEXT
            );
        """)

        # Auto-migration check: ensure columns exist without wiping historical data
        cursor.execute("PRAGMA table_info(jobs);")
        existing_cols = {row["name"] for row in cursor.fetchall()}

        expected_migrations = [
            ("location", "TEXT DEFAULT 'Remote'"),
            ("source", "TEXT DEFAULT 'unknown'"),
            ("application_status", "TEXT DEFAULT 'pending'"),
            ("match_score", "INTEGER DEFAULT 0"),
            ("analysis", "TEXT"),
            ("is_reviewed", "INTEGER DEFAULT 0"),
        ]

        for col_name, col_def in expected_migrations:
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_def};")

        conn.commit()

def store_jobs(jobs: List[JobPosting], db_path: str = DB_PATH) -> int:
    """Inserts batch of jobs; skips duplicates via primary key constraint."""
    new_count = 0
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for job in jobs:
            try:
                cursor.execute("""
                    INSERT INTO jobs (id, position, company, location, tags, description, url, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    job.id,
                    job.position,
                    job.company,
                    job.location,
                    json.dumps(job.tags),
                    job.description,
                    job.url,
                    job.source
                ))
                new_count += 1
            except sqlite3.IntegrityError:
                # Duplicate ID detected: silently skip
                continue
        conn.commit()
    return new_count

def update_job_status(job_id: str, status: str, db_path: str = DB_PATH) -> bool:
    """Updates application status ('pending', 'saved', 'applied', 'passed')."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE jobs SET application_status = ?, is_reviewed = 1 WHERE id = ?;
        """, (status, job_id))
        conn.commit()
        return cursor.rowcount > 0

def get_job_by_id(job_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetches a single job dictionary by id."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?;", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_jobs_by_status(status: str, limit: int = 50, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves all jobs with a given application status."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM jobs 
            WHERE application_status = ? 
            ORDER BY created_at DESC LIMIT ?;
        """, (status, limit))
        return [dict(row) for row in cursor.fetchall()]