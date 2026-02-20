from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from typing import Optional, List, Dict
from datetime import datetime

app = Flask(__name__)

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.db')

SAMPLE_TASKS: List[Dict] = [
    {
        'title': 'Fix critical login bug',
        'notes': 'Users getting 500 errors when logging in via OAuth. Needs hotfix ASAP.',
        'project': 'Backend',
        'due_date': '2026-02-20',
        'assignee': 'Alice Chen',
        'status': 'Urgent',
    },
    {
        'title': 'Deploy payment hotfix to production',
        'notes': 'EU customers unable to complete checkout. Revenue impact ~$5k/hour.',
        'project': 'DevOps',
        'due_date': '2026-02-20',
        'assignee': 'Bob Martinez',
        'status': 'Urgent',
    },
    {
        'title': 'Update API documentation',
        'notes': 'Swagger docs are outdated for v3 endpoints. Need to document the new auth flow.',
        'project': 'Backend',
        'due_date': '2026-02-21',
        'assignee': 'Alice Chen',
        'status': 'Today',
    },
    {
        'title': 'Design system components review',
        'notes': 'Review and approve new button and input component designs from the design team.',
        'project': 'Design',
        'due_date': '2026-02-21',
        'assignee': 'David Park',
        'status': 'Today',
    },
    {
        'title': 'Implement dark mode',
        'notes': 'Add dark mode toggle to user settings page. Follow design system specs.',
        'project': 'Frontend',
        'due_date': '2026-02-25',
        'assignee': 'David Park',
        'status': 'Upcoming',
    },
    {
        'title': 'Migrate database to PostgreSQL',
        'notes': 'Plan and execute migration from MySQL. Coordinate downtime window with ops team.',
        'project': 'Backend',
        'due_date': '2026-03-01',
        'assignee': 'Bob Martinez',
        'status': 'Upcoming',
    },
    {
        'title': 'User research interviews',
        'notes': 'Conduct 5 user interviews for the new onboarding flow redesign.',
        'project': 'Product',
        'due_date': '2026-02-28',
        'assignee': 'Eve Johnson',
        'status': 'Upcoming',
    },
    {
        'title': 'Set up CI/CD pipeline',
        'notes': 'Configure GitHub Actions for automated testing and deployment to staging.',
        'project': 'DevOps',
        'due_date': '2026-02-23',
        'assignee': 'David Park',
        'status': 'Upcoming',
    },
    {
        'title': 'Q1 roadmap presentation',
        'notes': 'Prepared and delivered Q1 roadmap slides to all stakeholders. Very well received.',
        'project': 'Product',
        'due_date': '2026-02-15',
        'assignee': 'Eve Johnson',
        'status': 'Complete',
    },
    {
        'title': 'Onboarding flow redesign',
        'notes': 'New onboarding flow designed and approved. Engineering handoff complete.',
        'project': 'Design',
        'due_date': '2026-02-18',
        'assignee': 'Carol Kim',
        'status': 'Complete',
    },
]


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            notes      TEXT    DEFAULT '',
            project    TEXT    DEFAULT '',
            due_date   TEXT    DEFAULT '',
            assignee   TEXT    DEFAULT '',
            status     TEXT NOT NULL DEFAULT 'Upcoming',
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()

    count: int = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    if count == 0:
        created_at: str = datetime.now().isoformat()
        for task in SAMPLE_TASKS:
            conn.execute(
                'INSERT INTO tasks (title, notes, project, due_date, assignee, status, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?)',
                (task['title'], task['notes'], task['project'],
                 task['due_date'], task['assignee'], task['status'], created_at)
            )
        conn.commit()
        print(f'Seeded {len(SAMPLE_TASKS)} sample tasks.')

    conn.close()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    conn = get_db()
    rows = conn.execute('SELECT * FROM tasks ORDER BY created_at DESC').fetchall()
    conn.close()

    tasks_by_status: Dict[str, List[dict]] = {
        'Urgent': [],
        'Today': [],
        'Upcoming': [],
        'Complete': [],
    }

    for row in rows:
        task: dict = dict(row)
        status: str = task.get('status', 'Upcoming')
        if status in tasks_by_status:
            tasks_by_status[status].append(task)

    return render_template('index.html', tasks_by_status=tasks_by_status)


@app.route('/tasks', methods=['POST'])
def create_task():
    data: Optional[dict] = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    title: str = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Title is required'}), 400

    notes: str    = data.get('notes', '')
    project: str  = data.get('project', '')
    due_date: str = data.get('due_date', '')
    assignee: str = data.get('assignee', '')
    status: str   = data.get('status', 'Upcoming')
    created_at: str = datetime.now().isoformat()

    conn = get_db()
    cursor = conn.execute(
        'INSERT INTO tasks (title, notes, project, due_date, assignee, status, created_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (title, notes, project, due_date, assignee, status, created_at)
    )
    task_id: int = cursor.lastrowid
    conn.commit()
    row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()

    return jsonify(dict(row)), 201


@app.route('/tasks/<int:task_id>', methods=['GET'])
def get_task(task_id: int):
    conn = get_db()
    row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()

    if row is None:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(dict(row))


@app.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id: int):
    data: Optional[dict] = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    conn = get_db()
    row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404

    task: dict    = dict(row)
    title: str    = data.get('title',    task['title'])
    notes: str    = data.get('notes',    task['notes'])
    project: str  = data.get('project',  task['project'])
    due_date: str = data.get('due_date', task['due_date'])
    assignee: str = data.get('assignee', task['assignee'])
    status: str   = data.get('status',   task['status'])

    conn.execute(
        'UPDATE tasks SET title=?, notes=?, project=?, due_date=?, assignee=?, status=? WHERE id=?',
        (title, notes, project, due_date, assignee, status, task_id)
    )
    conn.commit()
    row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    conn.close()

    return jsonify(dict(row))


@app.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id: int):
    conn = get_db()
    row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if row is None:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404

    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Task deleted successfully'})


if __name__ == '__main__':
    init_db()
    print('Task Manager running at http://localhost:5000')
    app.run(debug=True, port=5000)
