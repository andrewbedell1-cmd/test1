import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path("transcript_pm.db")


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                filename TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
                summary TEXT NOT NULL,
                key_decisions TEXT NOT NULL,
                next_steps TEXT NOT NULL,
                participants TEXT NOT NULL,
                topics TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS action_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transcript_id INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
                project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                assignee TEXT,
                due_date TEXT,
                priority TEXT NOT NULL DEFAULT 'medium',
                description TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL
            );
        """)


# ── Projects ──────────────────────────────────────────────────────────────────

def create_project(name: str, description: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, description, created_at) VALUES (?, ?, ?)",
            (name, description, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def list_projects() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.*, COUNT(a.id) AS action_count "
            "FROM projects p LEFT JOIN action_items a ON a.project_id = p.id "
            "GROUP BY p.id ORDER BY p.created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_project(project_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None


# ── Transcripts ───────────────────────────────────────────────────────────────

def save_transcript(filename: str, content: str, project_id: int | None = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO transcripts (project_id, filename, content, created_at) VALUES (?, ?, ?, ?)",
            (project_id, filename, content, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def get_transcript(transcript_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM transcripts WHERE id = ?", (transcript_id,)).fetchone()
        return dict(row) if row else None


def list_transcripts(project_id: int | None = None) -> list[dict]:
    with get_conn() as conn:
        if project_id is not None:
            rows = conn.execute(
                "SELECT t.*, p.name AS project_name FROM transcripts t "
                "LEFT JOIN projects p ON p.id = t.project_id "
                "WHERE t.project_id = ? ORDER BY t.created_at DESC",
                (project_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT t.*, p.name AS project_name FROM transcripts t "
                "LEFT JOIN projects p ON p.id = t.project_id "
                "ORDER BY t.created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


# ── Analyses ──────────────────────────────────────────────────────────────────

def save_analysis(
    transcript_id: int,
    summary: str,
    key_decisions: list[str],
    next_steps: list[str],
    participants: list[str],
    topics: list[str],
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO analyses "
            "(transcript_id, summary, key_decisions, next_steps, participants, topics, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                transcript_id,
                summary,
                json.dumps(key_decisions),
                json.dumps(next_steps),
                json.dumps(participants),
                json.dumps(topics),
                datetime.utcnow().isoformat(),
            ),
        )
        return cur.lastrowid


def get_analysis(transcript_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM analyses WHERE transcript_id = ?", (transcript_id,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["key_decisions"] = json.loads(d["key_decisions"])
        d["next_steps"] = json.loads(d["next_steps"])
        d["participants"] = json.loads(d["participants"])
        d["topics"] = json.loads(d["topics"])
        return d


# ── Action Items ──────────────────────────────────────────────────────────────

def save_action_items(transcript_id: int, items: list[dict], project_id: int | None = None) -> list[int]:
    ids = []
    with get_conn() as conn:
        for item in items:
            cur = conn.execute(
                "INSERT INTO action_items "
                "(transcript_id, project_id, title, assignee, due_date, priority, description, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
                (
                    transcript_id,
                    project_id,
                    item["title"],
                    item.get("assignee"),
                    item.get("due_date"),
                    item.get("priority", "medium"),
                    item.get("description", ""),
                    datetime.utcnow().isoformat(),
                ),
            )
            ids.append(cur.lastrowid)
    return ids


def list_action_items(
    transcript_id: int | None = None,
    project_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    with get_conn() as conn:
        clauses, params = [], []
        if transcript_id is not None:
            clauses.append("a.transcript_id = ?")
            params.append(transcript_id)
        if project_id is not None:
            clauses.append("a.project_id = ?")
            params.append(project_id)
        if status is not None:
            clauses.append("a.status = ?")
            params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT a.*, p.name AS project_name FROM action_items a "
            f"LEFT JOIN projects p ON p.id = a.project_id {where} "
            f"ORDER BY CASE a.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, a.due_date ASC",
            params,
        ).fetchall()
        return [dict(r) for r in rows]


def update_action_item_status(item_id: int, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE action_items SET status = ? WHERE id = ?", (status, item_id))


def update_action_item_project(item_id: int, project_id: int | None):
    with get_conn() as conn:
        conn.execute("UPDATE action_items SET project_id = ? WHERE id = ?", (project_id, item_id))
