import os
import bcrypt
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
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    goal TEXT NOT NULL,
                    report TEXT NOT NULL,
                    tool_calls INTEGER NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    ticker TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(user_id, ticker)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS portfolio (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    ticker TEXT NOT NULL,
                    shares NUMERIC NOT NULL,
                    cost_per_share NUMERIC NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS cost_per_share NUMERIC NOT NULL DEFAULT 0
            """)
        conn.commit()

# ---------- Auth ----------

def create_user(email: str, password: str):
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                (email, password_hash)
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    return user_id

def get_user_by_email(email: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
    return dict(row) if row else None

def get_user_by_id(user_id: int):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
    return dict(row) if row else None

def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())

# ---------- Reports ----------

def save_report(goal: str, report: str, tool_calls: int, user_id: int = None) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reports (goal, report, tool_calls, user_id) VALUES (%s, %s, %s, %s) RETURNING id",
                (goal, report, tool_calls, user_id)
            )
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id

def get_reports(user_id: int, limit: int = 50):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, goal, report, tool_calls, created_at FROM reports WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit)
            )
            return [dict(r) for r in cur.fetchall()]

def delete_report(report_id: int, user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM reports WHERE id = %s AND user_id = %s",
                (report_id, user_id)
            )
        conn.commit()

# ---------- Watchlist ----------

def get_watchlist_tickers(user_id: int):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT ticker FROM watchlist WHERE user_id = %s ORDER BY created_at ASC",
                (user_id,)
            )
            return [r["ticker"] for r in cur.fetchall()]

def add_to_watchlist(user_id: int, ticker: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO watchlist (user_id, ticker) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (user_id, ticker.upper())
            )
        conn.commit()

def remove_from_watchlist(user_id: int, ticker: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM watchlist WHERE user_id = %s AND ticker = %s",
                (user_id, ticker.upper())
            )
        conn.commit()

# ---------- Portfolio ----------

def get_portfolio(user_id: int):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, ticker, shares, cost_per_share FROM portfolio WHERE user_id = %s ORDER BY created_at ASC",
                (user_id,)
            )
            return [dict(r) for r in cur.fetchall()]

def add_position(user_id: int, ticker: str, shares: float, cost_per_share: float = 0):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO portfolio (user_id, ticker, shares, cost_per_share) VALUES (%s, %s, %s, %s) RETURNING id",
                (user_id, ticker.upper(), shares, cost_per_share)
            )
            row_id = cur.fetchone()[0]
        conn.commit()
    return row_id

def update_position(position_id: int, user_id: int, shares: float, cost_per_share: float):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE portfolio SET shares = %s, cost_per_share = %s WHERE id = %s AND user_id = %s",
                (shares, cost_per_share, position_id, user_id)
            )
        conn.commit()

def delete_position(position_id: int, user_id: int):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM portfolio WHERE id = %s AND user_id = %s",
                (position_id, user_id)
            )
        conn.commit()
