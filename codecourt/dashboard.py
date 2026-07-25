"""Read-only FastAPI dashboard for persisted CodeCourt runs."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .evidence_store import DEFAULT_DATABASE_PATH, EvidenceStore

TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_app(database_path: Path = DEFAULT_DATABASE_PATH) -> FastAPI:
    app = FastAPI(title="CodeCourt")

    @app.get("/", response_class=HTMLResponse)
    def runs(request: Request) -> HTMLResponse:
        store = EvidenceStore(database_path)
        try:
            return TEMPLATES.TemplateResponse(request, "runs.html", {"runs": store.list_runs()})
        finally:
            store.close()

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(request: Request, run_id: str) -> HTMLResponse:
        store = EvidenceStore(database_path)
        try:
            run = store.get_run(run_id)
            if run is None:
                raise HTTPException(status_code=404, detail="Run not found")
            return TEMPLATES.TemplateResponse(
                request,
                "run_detail.html",
                {"run": run, "details": store.run_details(run_id)},
            )
        finally:
            store.close()

    return app


app = create_app()
