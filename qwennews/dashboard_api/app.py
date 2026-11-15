"""FastAPI application — localhost-only, read-only dashboard API."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from qwennews.config import load_config
from qwennews.dashboard_api import schemas, service
from qwennews.readonly_store import ReadOnlyStore


def _db_path_from_env() -> Path:
    cfg = load_config()
    override = os.getenv("QWENNEWS_DASHBOARD_DB")
    return Path(override) if override else Path(cfg.db_path)


def create_app(*, db_path: Path | None = None) -> FastAPI:
    path = Path(db_path) if db_path is not None else _db_path_from_env()
    store = ReadOnlyStore(path)

    app = FastAPI(
        title="QwenNews Dashboard API",
        version="0.4.0",
        description="Read-only local API for the QwenNews dashboard (bind 127.0.0.1).",
    )

    # Local Next.js only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def reject_mutations(request: Request, call_next):  # noqa: ANN001
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            return JSONResponse({"detail": "Read-only API"}, status_code=405)
        return await call_next(request)

    @app.get("/api/health", response_model=schemas.HealthResponse)
    def health() -> schemas.HealthResponse:
        try:
            store.stats()
            ok = True
        except FileNotFoundError:
            ok = False
        return schemas.HealthResponse(ok=ok)

    @app.get("/api/today", response_model=schemas.TodayResponse)
    def today(
        story_limit: int = Query(15, ge=1, le=40),
    ) -> schemas.TodayResponse:
        try:
            payload = service.build_today(store, story_limit=story_limit)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return schemas.TodayResponse.model_validate(payload)

    @app.get("/api/reports", response_model=schemas.HistoryResponse)
    def list_reports(
        mode: str | None = Query(None, pattern="^(hourly|daily|ondemand)$"),
        limit: int = Query(20, ge=1, le=100),
        before_id: int | None = Query(None, ge=1),
        category: str | None = Query(None, max_length=64),
    ) -> schemas.HistoryResponse:
        try:
            rows = store.list_reports(
                mode=mode, limit=limit, before_id=before_id, category=category
            )
            cats = store.categories()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return schemas.HistoryResponse(
            items=[schemas.ReportSummary.model_validate(service.report_summary(r)) for r in rows],
            categories=cats,
        )

    @app.get("/api/reports/{report_id}", response_model=schemas.ReportDetail)
    def get_report(report_id: int) -> schemas.ReportDetail:
        try:
            row = store.get_report(report_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if row is None:
            raise HTTPException(status_code=404, detail="Report not found")
        return schemas.ReportDetail.model_validate(service.report_detail(row))

    @app.get("/api/hourly", response_model=schemas.HourlyListResponse)
    def hourly(
        limit: int = Query(24, ge=1, le=100),
        before_id: int | None = Query(None, ge=1),
    ) -> schemas.HourlyListResponse:
        try:
            rows = store.list_reports(mode="hourly", limit=limit, before_id=before_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return schemas.HourlyListResponse(
            items=[schemas.ReportSummary.model_validate(service.report_summary(r)) for r in rows]
        )

    @app.get("/api/stories", response_model=list[schemas.StoryCard])
    def stories(
        limit: int = Query(40, ge=1, le=200),
        category: str | None = Query(None, max_length=64),
    ) -> list[schemas.StoryCard]:
        try:
            rows = store.list_stories(limit=limit, category=category)
            return [
                schemas.StoryCard.model_validate(
                    service.story_card(store, s, include_articles=True)
                )
                for s in rows
            ]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/stories/{story_id}", response_model=schemas.StoryCard)
    def story_detail(story_id: str) -> schemas.StoryCard:
        if len(story_id) > 128 or "/" in story_id or ".." in story_id:
            raise HTTPException(status_code=400, detail="Invalid story id")
        try:
            row = store.get_story(story_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if row is None:
            raise HTTPException(status_code=404, detail="Story not found")
        return schemas.StoryCard.model_validate(
            service.story_card(store, row, include_articles=True)
        )

    @app.get("/api/status", response_model=schemas.StatusResponse)
    def status(
        live_ollama: bool = Query(True, description="Run a bounded Ollama probe"),
    ) -> schemas.StatusResponse:
        try:
            payload = service.build_status(store, probe_ollama=live_ollama)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return schemas.StatusResponse.model_validate(payload)

    # Expose store for tests
    app.state.store = store  # type: ignore[attr-defined]
    app.state.db_path = path  # type: ignore[attr-defined]
    return app


app = create_app()
