"""
Transcript Project Manager
FastAPI web app for uploading call transcripts and generating detailed notes,
action items, and next steps — with SQLite PM storage and iCal export.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
import uvicorn

import db
import analyzer
import calendar_export
import tasks_db
import tasks_router

app = FastAPI(title="Transcript PM")
templates = Jinja2Templates(directory="templates")

# ── Initialise both databases ──────────────────────────────────────────────────
db.init_db()
tasks_db.init_db()
tasks_db.seed_data()

# ── Mount the tasks router ─────────────────────────────────────────────────────
app.include_router(tasks_router.router)


# ── Home: list all transcripts ────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    transcripts = db.list_transcripts()
    projects = db.list_projects()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "transcripts": transcripts, "projects": projects},
    )


# ── Upload transcript ─────────────────────────────────────────────────────────

@app.post("/upload")
async def upload_transcript(
    request: Request,
    project_id: Optional[int] = Form(default=None),
    new_project_name: str = Form(default=""),
    file: Optional[UploadFile] = File(default=None),
    paste_content: str = Form(default=""),
    filename_hint: str = Form(default="pasted-transcript.txt"),
):
    # Get content from file or paste
    if file and file.filename:
        content = (await file.read()).decode("utf-8", errors="replace")
        fname = file.filename
    elif paste_content.strip():
        content = paste_content.strip()
        fname = filename_hint.strip() or "pasted-transcript.txt"
    else:
        raise HTTPException(status_code=400, detail="Provide a file or paste content.")

    # Create new project if requested
    if new_project_name.strip():
        project_id = db.create_project(new_project_name.strip())
    elif project_id == 0:
        project_id = None

    # Save transcript
    transcript_id = db.save_transcript(fname, content, project_id)

    # Analyze with Claude
    try:
        result = analyzer.analyze_transcript(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Claude analysis failed: {e}")

    # Persist analysis
    db.save_analysis(
        transcript_id,
        result.summary,
        result.key_decisions,
        result.next_steps,
        result.participants,
        result.topics,
    )

    # Persist action items
    items = [a.model_dump() for a in result.action_items]
    db.save_action_items(transcript_id, items, project_id)

    return RedirectResponse(f"/transcript/{transcript_id}", status_code=303)


# ── View a transcript and its analysis ───────────────────────────────────────

@app.get("/transcript/{transcript_id}", response_class=HTMLResponse)
async def view_transcript(request: Request, transcript_id: int):
    transcript = db.get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    analysis = db.get_analysis(transcript_id)
    action_items = db.list_action_items(transcript_id=transcript_id)
    projects = db.list_projects()

    project = None
    if transcript.get("project_id"):
        project = db.get_project(transcript["project_id"])

    return templates.TemplateResponse(
        "transcript.html",
        {
            "request": request,
            "transcript": transcript,
            "analysis": analysis,
            "action_items": action_items,
            "projects": projects,
            "project": project,
        },
    )


# ── Update action item status ─────────────────────────────────────────────────

@app.post("/action/{item_id}/status")
async def update_status(item_id: int, status: str = Form(...), redirect_to: str = Form(default="/")):
    db.update_action_item_status(item_id, status)
    return RedirectResponse(redirect_to, status_code=303)


# ── Update action item project ────────────────────────────────────────────────

@app.post("/action/{item_id}/project")
async def update_project(
    item_id: int,
    project_id: Optional[int] = Form(default=None),
    redirect_to: str = Form(default="/"),
):
    db.update_action_item_project(item_id, project_id if project_id else None)
    return RedirectResponse(redirect_to, status_code=303)


# ── Projects view ─────────────────────────────────────────────────────────────

@app.get("/projects", response_class=HTMLResponse)
async def list_projects_view(request: Request):
    projects = db.list_projects()
    return templates.TemplateResponse(
        "projects.html", {"request": request, "projects": projects}
    )


@app.get("/project/{project_id}", response_class=HTMLResponse)
async def view_project(request: Request, project_id: int):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    transcripts = db.list_transcripts(project_id=project_id)
    action_items = db.list_action_items(project_id=project_id)
    open_items = [i for i in action_items if i["status"] == "open"]
    done_items = [i for i in action_items if i["status"] == "done"]

    return templates.TemplateResponse(
        "project.html",
        {
            "request": request,
            "project": project,
            "transcripts": transcripts,
            "open_items": open_items,
            "done_items": done_items,
        },
    )


@app.post("/projects/create")
async def create_project(name: str = Form(...), description: str = Form(default="")):
    db.create_project(name.strip(), description.strip())
    return RedirectResponse("/projects", status_code=303)


# ── iCal export ───────────────────────────────────────────────────────────────

@app.get("/export/calendar")
async def export_all_calendar():
    items = db.list_action_items()
    ics = calendar_export.build_ical(items, "All Action Items")
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=action-items.ics"},
    )


@app.get("/export/calendar/project/{project_id}")
async def export_project_calendar(project_id: int):
    project = db.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404)
    items = db.list_action_items(project_id=project_id)
    ics = calendar_export.build_ical(items, f"{project['name']} — Action Items")
    safe_name = project["name"].replace(" ", "-")
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={safe_name}-actions.ics"},
    )


@app.get("/export/calendar/transcript/{transcript_id}")
async def export_transcript_calendar(transcript_id: int):
    transcript = db.get_transcript(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404)
    items = db.list_action_items(transcript_id=transcript_id)
    ics = calendar_export.build_ical(items, transcript["filename"])
    safe_name = Path(transcript["filename"]).stem.replace(" ", "-")
    return Response(
        content=ics,
        media_type="text/calendar",
        headers={"Content-Disposition": f"attachment; filename={safe_name}-actions.ics"},
    )


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
