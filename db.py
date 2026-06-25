import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")

def init_db():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    goal TEXT NOT NULL,
                    report TEXT NOT NULL,
                    tool_calls INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()

def save_report(goal: str, report: str, tool_calls: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reports (goal, report, tool_calls) VALUES (%s, %s, %s) RETURNING id",
                (goal, report, tool_calls)
            )
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id

def get_reports(limit: int = 20):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, goal, report, tool_calls, created_at FROM reports ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            return [dict(r) for r in cur.fetchall()]
