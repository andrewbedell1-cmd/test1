"""
FastAPI router — /tasks  (ClickUp-style PM dashboard)
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import tasks_db

router = APIRouter(prefix="/tasks")
templates = Jinja2Templates(directory="templates")

# ── Jinja2 helpers ─────────────────────────────────────────────────────────────

def _avatar_color(name: str) -> str:
    colors = tasks_db.AVATAR_COLORS
    return colors[sum(ord(c) for c in name) % len(colors)] if name else "#9ca3af"


templates.env.filters["avatar_color"] = _avatar_color
templates.env.globals["today_str"] = date.today().isoformat


# ── Dashboard ──────────────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    workstream_id: Optional[int] = None,
    assignee: Optional[str] = None,
):
    all_tasks = tasks_db.list_tasks(workstream_id=workstream_id, assignee=assignee)
    grouped = {
        s: [t for t in all_tasks if t["status"] == s]
        for s in tasks_db.STATUSES
    }
    workstreams = tasks_db.list_workstreams()
    assignees = tasks_db.list_assignees()

    return templates.TemplateResponse(
        "tasks_dashboard.html",
        {
            "request": request,
            "grouped": grouped,
            "statuses": tasks_db.STATUSES,
            "workstreams": workstreams,
            "assignees": assignees,
            "filter_workstream_id": workstream_id,
            "filter_assignee": assignee,
            "today": date.today().isoformat(),
        },
    )


# ── New task ───────────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
async def new_task_form(request: Request, status: Optional[str] = None):
    workstreams = tasks_db.list_workstreams()
    return templates.TemplateResponse(
        "task_form.html",
        {
            "request": request,
            "task": None,
            "workstreams": workstreams,
            "statuses": tasks_db.STATUSES,
            "prefill_status": status or "Upcoming",
        },
    )


@router.post("/new")
async def create_task(
    title: str = Form(...),
    notes: str = Form(default=""),
    workstream_id: Optional[int] = Form(default=None),
    new_workstream: str = Form(default=""),
    due_date: str = Form(default=""),
    assignee: str = Form(default=""),
    status: str = Form(default="Upcoming"),
):
    if status not in tasks_db.STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    ws_id = workstream_id
    if new_workstream.strip():
        ws_id = tasks_db.create_workstream(new_workstream.strip())

    tasks_db.create_task(
        title=title.strip(),
        notes=notes.strip(),
        workstream_id=ws_id,
        due_date=due_date or None,
        assignee=assignee.strip(),
        status=status,
    )
    return RedirectResponse("/tasks", status_code=303)


# ── Edit task ──────────────────────────────────────────────────────────────────

@router.get("/{task_id}", response_class=HTMLResponse)
async def edit_task_form(request: Request, task_id: int):
    task = tasks_db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    workstreams = tasks_db.list_workstreams()
    return templates.TemplateResponse(
        "task_form.html",
        {
            "request": request,
            "task": task,
            "workstreams": workstreams,
            "statuses": tasks_db.STATUSES,
            "prefill_status": task["status"],
        },
    )


@router.post("/{task_id}/update")
async def update_task(
    task_id: int,
    title: str = Form(...),
    notes: str = Form(default=""),
    workstream_id: Optional[int] = Form(default=None),
    new_workstream: str = Form(default=""),
    due_date: str = Form(default=""),
    assignee: str = Form(default=""),
    status: str = Form(default="Upcoming"),
):
    if not tasks_db.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    if status not in tasks_db.STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    ws_id = workstream_id
    if new_workstream.strip():
        ws_id = tasks_db.create_workstream(new_workstream.strip())

    tasks_db.update_task(
        task_id=task_id,
        title=title.strip(),
        notes=notes.strip(),
        workstream_id=ws_id,
        due_date=due_date or None,
        assignee=assignee.strip(),
        status=status,
    )
    return RedirectResponse("/tasks", status_code=303)


# ── Quick status update (inline dropdown on dashboard) ────────────────────────

@router.post("/{task_id}/status")
async def update_status(task_id: int, status: str = Form(...)):
    if status not in tasks_db.STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    if not tasks_db.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    tasks_db.update_task_status(task_id, status)
    return RedirectResponse("/tasks", status_code=303)


# ── Delete task ────────────────────────────────────────────────────────────────

@router.post("/{task_id}/delete")
async def delete_task(task_id: int):
    if not tasks_db.get_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    tasks_db.delete_task(task_id)
    return RedirectResponse("/tasks", status_code=303)
