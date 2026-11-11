"""Tiny portable data layer.

Production: Supabase Postgres via DATABASE_URL (use the transaction pooler,
port 6543). Local dev / tests: SQLite file. SQL is written once with '?'
placeholders and plain types so it runs on both.
"""
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "")
IS_PG = DATABASE_URL.startswith("postgres")
_lock = threading.RLock()
_conn = None

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS orgs (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT DEFAULT 'guest', created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY, name TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS members (
        user_id TEXT NOT NULL, org_id TEXT NOT NULL, role TEXT NOT NULL,
        PRIMARY KEY (user_id, org_id))""",
    """CREATE TABLE IF NOT EXISTS brands (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, name TEXT, description TEXT,
        tone_summary TEXT, palette TEXT, rulebook_version INTEGER DEFAULT 1, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS clauses (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, brand_id TEXT NOT NULL, code TEXT, section TEXT,
        title TEXT, text TEXT, kind TEXT, check_type TEXT, params TEXT, visual INTEGER DEFAULT 0,
        status TEXT DEFAULT 'confirmed', embedding TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS facts (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, brand_id TEXT NOT NULL, code TEXT, fkey TEXT,
        value TEXT, valid_until TEXT, source TEXT)""",
    """CREATE TABLE IF NOT EXISTS terms (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, brand_id TEXT NOT NULL, term TEXT, kind TEXT,
        replacement TEXT, clause_code TEXT, unless_preceded_by TEXT)""",
    """CREATE TABLE IF NOT EXISTS drafts (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, brand_id TEXT NOT NULL, title TEXT, channel TEXT,
        status TEXT, created_by TEXT, current_version INTEGER DEFAULT 1, sample_id TEXT,
        created_at TEXT, updated_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS versions (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, draft_id TEXT NOT NULL, n INTEGER, text TEXT,
        image_b64 TEXT, alt_text TEXT, note TEXT, created_by TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS checks (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, version_id TEXT NOT NULL, content_hash TEXT,
        model TEXT, ai_status TEXT, dropped_uncited INTEGER DEFAULT 0, duration_ms INTEGER,
        summary TEXT, ran_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS findings (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, check_id TEXT NOT NULL, version_id TEXT NOT NULL,
        category TEXT, severity TEXT, confidence REAL, source TEXT, rule TEXT, quote TEXT,
        start_idx INTEGER, end_idx INTEGER, cite_type TEXT, cite_code TEXT, cite_text TEXT,
        explanation TEXT, fix_text TEXT, claim_status TEXT, decision TEXT, decision_note TEXT,
        edited_fix TEXT, decided_by TEXT, decided_at TEXT, ord INTEGER)""",
    """CREATE TABLE IF NOT EXISTS events (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, draft_id TEXT, actor TEXT, role TEXT,
        action TEXT, comment TEXT, at TEXT)""",
    """CREATE TABLE IF NOT EXISTS check_cache (
        content_hash TEXT PRIMARY KEY, payload TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS eval_runs (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, ran_at TEXT, results TEXT)""",
    # Reviewer decisions the checker learns from (origin: reviewer | calibration)
    """CREATE TABLE IF NOT EXISTS feedback (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, brand_id TEXT NOT NULL, finding_id TEXT,
        cite_code TEXT, source TEXT, rule TEXT, category TEXT, confidence REAL, quote TEXT,
        decision TEXT, note TEXT, origin TEXT DEFAULT 'reviewer', created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS learning_settings (
        org_id TEXT NOT NULL, brand_id TEXT NOT NULL, code TEXT NOT NULL, enabled INTEGER DEFAULT 1,
        updated_at TEXT, PRIMARY KEY (org_id, brand_id, code))""",
    "CREATE INDEX IF NOT EXISTS ix_feedback_brand ON feedback (org_id, brand_id)",
    # Rulebook history (improvement 3): a snapshot per change, so every check names the version it used
    """CREATE TABLE IF NOT EXISTS rulebook_versions (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, brand_id TEXT NOT NULL, version INTEGER, note TEXT,
        actor TEXT, created_at TEXT, snapshot TEXT)""",
    # Guideline-gap assistant suggestions (pending -> approved / rejected)
    """CREATE TABLE IF NOT EXISTS clause_suggestions (
        id TEXT PRIMARY KEY, org_id TEXT NOT NULL, brand_id TEXT NOT NULL, code TEXT, reason TEXT, old_text TEXT,
        new_text TEXT, do_examples TEXT, dont_examples TEXT, why TEXT, model TEXT, status TEXT DEFAULT 'pending',
        created_at TEXT, decided_by TEXT, decided_at TEXT, version INTEGER)""",
    "CREATE INDEX IF NOT EXISTS ix_drafts_org ON drafts (org_id, status)",
    "CREATE INDEX IF NOT EXISTS ix_versions_draft ON versions (draft_id, n)",
    "CREATE INDEX IF NOT EXISTS ix_findings_check ON findings (check_id)",
    "CREATE INDEX IF NOT EXISTS ix_clauses_brand ON clauses (brand_id)",
    "CREATE INDEX IF NOT EXISTS ix_events_draft ON events (draft_id)",
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id():
    return uuid.uuid4().hex


def _connect():
    if IS_PG:
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True,
                               prepare_threshold=None, connect_timeout=10)
    path = os.getenv("SQLITE_PATH", "/tmp/brandproof.db")
    c = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def conn():
    global _conn
    if _conn is None:
        _conn = _connect()
        for stmt in SCHEMA:
            _conn.execute(stmt)
    return _conn


def _sql(q):
    return q.replace("?", "%s") if IS_PG else q


def _run(q, params=()):
    global _conn
    with _lock:
        try:
            return conn().execute(_sql(q), params)
        except Exception as e:  # reconnect once on dropped serverless connections
            if IS_PG and "closed" in str(e).lower():
                _conn = None
                return conn().execute(_sql(q), params)
            raise


def all(q, params=()):
    with _lock:  # fetch under the lock too: the connection is shared between request threads
        cur = _run(q, params)
        return [dict(r) for r in cur.fetchall()]


def one(q, params=()):
    with _lock:
        cur = _run(q, params)
        r = cur.fetchone()
        return dict(r) if r else None


def exec(q, params=()):
    _run(q, params)


def many(q, rows):
    if not rows:
        return
    with _lock:
        if IS_PG:
            with conn().cursor() as cur:
                cur.executemany(_sql(q), rows)
        else:
            conn().executemany(q, rows)


def insert(table, row):
    cols = list(row.keys())
    exec(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
         [row[c] for c in cols])
    return row


def insert_many(table, rows):
    if not rows:
        return
    cols = list(rows[0].keys())
    many(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
         [[r[c] for c in cols] for r in rows])


def jload(v, default=None):
    if v is None or v == "":
        return default
    if isinstance(v, (dict, list)):
        return v
    try:
        return json.loads(v)
    except Exception:
        return default


def jdump(v):
    return json.dumps(v, ensure_ascii=False)
