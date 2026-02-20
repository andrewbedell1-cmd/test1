"""
Task Manager DB — SQLite layer for the ClickUp-style PM dashboard.
Separate from the transcript PM db (transcript_pm.db); uses pm_tasks.db.
"""

import sqlite3
import json
from datetime import datetime, timedelta, date
from pathlib import Path

DB_PATH = Path("pm_tasks.db")

STATUSES = ["Urgent", "Today", "Upcoming", "Complete"]

AVATAR_COLORS = [
    "#7c3aed", "#2563eb", "#059669", "#d97706",
    "#dc2626", "#0891b2", "#be185d", "#065f46",
]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workstreams (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL UNIQUE,
                color       TEXT    NOT NULL DEFAULT '#6366f1',
                created_at  TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT    NOT NULL,
                notes           TEXT    NOT NULL DEFAULT '',
                workstream_id   INTEGER REFERENCES workstreams(id) ON DELETE SET NULL,
                due_date        TEXT,
                assignee        TEXT    NOT NULL DEFAULT '',
                status          TEXT    NOT NULL DEFAULT 'Upcoming',
                source          TEXT    NOT NULL DEFAULT 'manual',
                source_ref      TEXT    NOT NULL DEFAULT '',
                created_at      TEXT    NOT NULL,
                updated_at      TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_workstream ON tasks(workstream_id);
        """)


# ── Workstreams ────────────────────────────────────────────────────────────────

def list_workstreams() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM workstreams ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]


def get_workstream(ws_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM workstreams WHERE id = ?", (ws_id,)
        ).fetchone()
        return dict(row) if row else None


def create_workstream(name: str, color: str = "#6366f1") -> int:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        # INSERT OR IGNORE to handle race; then fetch the id
        conn.execute(
            "INSERT OR IGNORE INTO workstreams (name, color, created_at) VALUES (?, ?, ?)",
            (name, color, now),
        )
        row = conn.execute(
            "SELECT id FROM workstreams WHERE name = ?", (name,)
        ).fetchone()
        return row[0]


# ── Tasks ──────────────────────────────────────────────────────────────────────

def _enrich(row: dict) -> dict:
    """Add computed fields to a task dict."""
    today_str = date.today().isoformat()
    due = row.get("due_date") or ""
    row["is_overdue"] = bool(due and due < today_str and row["status"] != "Complete")
    row["is_today"] = bool(due and due == today_str)
    # Avatar color derived from assignee name
    name = row.get("assignee") or ""
    row["avatar_color"] = (
        AVATAR_COLORS[sum(ord(c) for c in name) % len(AVATAR_COLORS)]
        if name else "#9ca3af"
    )
    return row


def list_tasks(
    status: str | None = None,
    workstream_id: int | None = None,
    assignee: str | None = None,
) -> list[dict]:
    with get_conn() as conn:
        clauses, params = [], []
        if status:
            clauses.append("t.status = ?")
            params.append(status)
        if workstream_id:
            clauses.append("t.workstream_id = ?")
            params.append(workstream_id)
        if assignee:
            clauses.append("t.assignee = ?")
            params.append(assignee)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"""
            SELECT t.*, w.name AS workstream_name, w.color AS workstream_color
            FROM tasks t
            LEFT JOIN workstreams w ON w.id = t.workstream_id
            {where}
            ORDER BY
                CASE WHEN t.due_date IS NULL OR t.due_date = '' THEN 1 ELSE 0 END,
                t.due_date ASC,
                t.created_at ASC
            """,
            params,
        ).fetchall()
        return [_enrich(dict(r)) for r in rows]


def get_task(task_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT t.*, w.name AS workstream_name, w.color AS workstream_color
            FROM tasks t
            LEFT JOIN workstreams w ON w.id = t.workstream_id
            WHERE t.id = ?
            """,
            (task_id,),
        ).fetchone()
        return _enrich(dict(row)) if row else None


def create_task(
    title: str,
    notes: str = "",
    workstream_id: int | None = None,
    due_date: str | None = None,
    assignee: str = "",
    status: str = "Upcoming",
    source: str = "manual",
    source_ref: str = "",
) -> int:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks
                (title, notes, workstream_id, due_date, assignee, status,
                 source, source_ref, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, notes, workstream_id, due_date or None,
             assignee, status, source, source_ref, now, now),
        )
        return cur.lastrowid


def update_task(
    task_id: int,
    title: str,
    notes: str,
    workstream_id: int | None,
    due_date: str | None,
    assignee: str,
    status: str,
) -> None:
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET title=?, notes=?, workstream_id=?, due_date=?,
                assignee=?, status=?, updated_at=?
            WHERE id=?
            """,
            (title, notes, workstream_id, due_date or None,
             assignee, status, now, task_id),
        )


def update_task_status(task_id: int, status: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status=?, updated_at=? WHERE id=?",
            (status, datetime.utcnow().isoformat(), task_id),
        )


def delete_task(task_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))


def list_assignees() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT assignee FROM tasks WHERE assignee != '' ORDER BY assignee"
        ).fetchall()
        return [r[0] for r in rows]


# ── Seed Data ──────────────────────────────────────────────────────────────────

def seed_data() -> None:
    """Insert representative sample tasks. No-op if tasks already exist."""
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        if count > 0:
            return

    today = date.today()
    now = datetime.utcnow().isoformat()

    # Create workstreams
    ws = {
        "Engineering": create_workstream("Engineering", "#7c3aed"),
        "Product":     create_workstream("Product",     "#2563eb"),
        "Marketing":   create_workstream("Marketing",   "#f59e0b"),
        "Operations":  create_workstream("Operations",  "#ef4444"),
        "Design":      create_workstream("Design",      "#059669"),
    }

    tasks = [
        # ── Urgent ────────────────────────────────────────────────────────────
        {
            "title": "Fix production login bug",
            "notes": "Users randomly logged out — JWT expiry logic seems off. Check refresh token flow.",
            "workstream_id": ws["Engineering"],
            "due_date": today.isoformat(),
            "assignee": "Alice",
            "status": "Urgent",
        },
        {
            "title": "Respond to enterprise trial request",
            "notes": "Acme Corp wants a 30-day enterprise trial. Needs CTO approval before replying.",
            "workstream_id": ws["Operations"],
            "due_date": today.isoformat(),
            "assignee": "Bob",
            "status": "Urgent",
        },
        {
            "title": "Patch CVE-2024-3094 in prod dependencies",
            "notes": "Critical security advisory. Update affected packages and redeploy.",
            "workstream_id": ws["Engineering"],
            "due_date": today.isoformat(),
            "assignee": "Alice",
            "status": "Urgent",
        },
        # ── Today ─────────────────────────────────────────────────────────────
        {
            "title": "Finalize Q2 product roadmap",
            "notes": "Review feature list with stakeholders and sign off by EOD.",
            "workstream_id": ws["Product"],
            "due_date": today.isoformat(),
            "assignee": "Carol",
            "status": "Today",
        },
        {
            "title": "Send weekly metrics report",
            "notes": "Compile DAU, MRR, and churn stats. Email to leadership by 5 pm.",
            "workstream_id": ws["Marketing"],
            "due_date": today.isoformat(),
            "assignee": "Dave",
            "status": "Today",
        },
        {
            "title": "Review and merge PR #247",
            "notes": "Database migration PR. Must land before the 5 pm deploy window.",
            "workstream_id": ws["Engineering"],
            "due_date": today.isoformat(),
            "assignee": "Alice",
            "status": "Today",
        },
        # ── Upcoming ──────────────────────────────────────────────────────────
        {
            "title": "Set up onboarding email drip sequence",
            "notes": "3-email sequence for new signups. Copy draft is in Notion.",
            "workstream_id": ws["Marketing"],
            "due_date": (today + timedelta(days=3)).isoformat(),
            "assignee": "Dave",
            "status": "Upcoming",
        },
        {
            "title": "Migrate auth to OAuth2 / PKCE",
            "notes": "Replace legacy session auth. Design doc linked in Jira epic.",
            "workstream_id": ws["Engineering"],
            "due_date": (today + timedelta(days=7)).isoformat(),
            "assignee": "Bob",
            "status": "Upcoming",
        },
        {
            "title": "Q2 OKR planning workshop",
            "notes": "Schedule 2-hour session with leads. Prepare OKR template beforehand.",
            "workstream_id": ws["Product"],
            "due_date": (today + timedelta(days=5)).isoformat(),
            "assignee": "Carol",
            "status": "Upcoming",
        },
        {
            "title": "Renew AWS reserved instances",
            "notes": "Three r6i.xlarge instances expire next month. Get pricing by Wed.",
            "workstream_id": ws["Operations"],
            "due_date": (today + timedelta(days=10)).isoformat(),
            "assignee": "Bob",
            "status": "Upcoming",
        },
        {
            "title": "Write v2 API documentation",
            "notes": "All endpoints need examples and error codes. Use OpenAPI spec as base.",
            "workstream_id": ws["Engineering"],
            "due_date": (today + timedelta(days=14)).isoformat(),
            "assignee": "Alice",
            "status": "Upcoming",
        },
        {
            "title": "Redesign settings page",
            "notes": "New Figma mockups ready. Implement responsive layout.",
            "workstream_id": ws["Design"],
            "due_date": (today + timedelta(days=6)).isoformat(),
            "assignee": "Eve",
            "status": "Upcoming",
        },
        # ── Complete ──────────────────────────────────────────────────────────
        {
            "title": "Upgrade Node.js to v20 LTS",
            "notes": "All services updated and tested. Deployed to prod on Monday.",
            "workstream_id": ws["Engineering"],
            "due_date": (today - timedelta(days=1)).isoformat(),
            "assignee": "Alice",
            "status": "Complete",
        },
        {
            "title": "Design homepage mockups",
            "notes": "Figma mockups approved by stakeholders. Ready for dev handoff.",
            "workstream_id": ws["Design"],
            "due_date": (today - timedelta(days=2)).isoformat(),
            "assignee": "Eve",
            "status": "Complete",
        },
        {
            "title": "Conduct user interviews for search feature",
            "notes": "5 interviews completed. Key themes documented in research doc.",
            "workstream_id": ws["Product"],
            "due_date": (today - timedelta(days=3)).isoformat(),
            "assignee": "Carol",
            "status": "Complete",
        },
    ]

    for t in tasks:
        create_task(**t)
