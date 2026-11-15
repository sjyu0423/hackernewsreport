"""Read-only SQLite access for the local dashboard API (M4)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class ReadOnlyStore:
    """
    Safe reader over the QwenNews SQLite database.

    Opens connections with ``mode=ro`` so dashboard traffic cannot mutate data
    even if a code path accidentally issues a write.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path).resolve()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if not self.db_path.is_file():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        uri = f"file:{self.db_path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        try:
            yield conn
        finally:
            conn.close()

    def list_reports(
        self,
        *,
        mode: str | None = None,
        limit: int = 20,
        before_id: int | None = None,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        clauses = ["status = 'completed'"]
        params: list[Any] = []
        if mode:
            clauses.append("mode = ?")
            params.append(mode)
        if before_id is not None:
            clauses.append("id < ?")
            params.append(int(before_id))
        # Category filter is soft: match markdown/title text when requested
        if category:
            clauses.append("(markdown LIKE ? OR markdown LIKE ?)")
            params.extend([f"%Category: **{category}%", f"%category: {category}%"])
        where = " AND ".join(clauses)
        sql = f"""
            SELECT id, created_at, hours, story_count, path, mode, as_of,
                   window_start, status, significant_only,
                   substr(markdown, 1, 400) AS markdown_preview
            FROM reports
            WHERE {where}
            ORDER BY id DESC
            LIMIT ?
        """
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_report(self, report_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, created_at, hours, story_count, path, markdown,
                       mode, as_of, window_start, status, significant_only
                FROM reports WHERE id = ?
                """,
                (int(report_id),),
            ).fetchone()
            return dict(row) if row else None

    def latest_report(self, *, mode: str | None = None) -> dict[str, Any] | None:
        clauses = ["status = 'completed'"]
        params: list[Any] = []
        if mode:
            clauses.append("mode = ?")
            params.append(mode)
        where = " AND ".join(clauses)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT id, created_at, hours, story_count, path, markdown,
                       mode, as_of, window_start, status, significant_only
                FROM reports
                WHERE {where}
                ORDER BY id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
            return dict(row) if row else None

    def list_stories(self, *, limit: int = 40, category: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._connect() as conn:
            if category:
                rows = conn.execute(
                    """
                    SELECT * FROM stories
                    WHERE lower(coalesce(category, '')) = lower(?)
                    ORDER BY last_seen_at DESC
                    LIMIT ?
                    """,
                    (category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM stories
                    ORDER BY last_seen_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_story(self, story_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()
            return dict(row) if row else None

    def list_story_articles(self, story_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, sa.linked_at, sa.link_reason,
                       (SELECT group_concat(source, ',')
                        FROM article_sources s WHERE s.article_id = a.id) AS sources
                FROM story_articles sa
                JOIN articles a ON a.id = sa.article_id
                WHERE sa.story_id = ?
                ORDER BY coalesce(a.published_at, a.discovered_at) DESC
                """,
                (story_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_analysis(self, article_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM article_analyses
                WHERE article_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (article_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_watermark(self, mode: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM report_watermarks WHERE mode = ?", (mode,)
            ).fetchone()
            return dict(row) if row else None

    def recent_orchestration_runs(
        self, *, mode: str | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 50))
        with self._connect() as conn:
            # Table may be missing on very old DBs
            try:
                if mode:
                    rows = conn.execute(
                        """
                        SELECT * FROM orchestration_runs
                        WHERE mode = ?
                        ORDER BY id DESC LIMIT ?
                        """,
                        (mode, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT * FROM orchestration_runs
                        ORDER BY id DESC LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
            except sqlite3.OperationalError:
                return []
            return [dict(r) for r in rows]

    def backlog_counts(self) -> dict[str, int]:
        with self._connect() as conn:
            out = {
                "pending_articles": 0,
                "failed_articles": 0,
                "pending_stories": 0,
                "ready_stories": 0,
                "failed_stories": 0,
                "active": 0,
            }
            try:
                out["pending_articles"] = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM article_processing_state "
                        "WHERE mode='hourly' AND status='pending'"
                    ).fetchone()[0]
                )
                out["failed_articles"] = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM article_processing_state "
                        "WHERE mode='hourly' AND status='failed'"
                    ).fetchone()[0]
                )
                out["pending_stories"] = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM story_processing_state "
                        "WHERE mode='hourly' AND status='pending'"
                    ).fetchone()[0]
                )
                out["ready_stories"] = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM story_processing_state "
                        "WHERE mode='hourly' AND status='ready'"
                    ).fetchone()[0]
                )
                out["failed_stories"] = int(
                    conn.execute(
                        "SELECT COUNT(*) FROM story_processing_state "
                        "WHERE mode='hourly' AND status='failed'"
                    ).fetchone()[0]
                )
            except sqlite3.OperationalError:
                return out
            out["active"] = (
                out["pending_articles"]
                + out["failed_articles"]
                + out["pending_stories"]
                + out["ready_stories"]
                + out["failed_stories"]
            )
            return out

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            article_count = int(
                conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            )
            analysis_count = int(
                conn.execute("SELECT COUNT(*) FROM article_analyses").fetchone()[0]
            )
            story_count = int(conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0])
            report_count = int(conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0])
            return {
                "article_count": article_count,
                "analysis_count": analysis_count,
                "story_count": story_count,
                "report_count": report_count,
                "db_path_name": self.db_path.name,
                "db_path": str(self.db_path),
                "db_size_bytes": self.db_path.stat().st_size if self.db_path.is_file() else 0,
            }

    def categories(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT category FROM stories
                WHERE category IS NOT NULL AND trim(category) != ''
                ORDER BY lower(category)
                """
            ).fetchall()
            return [str(r[0]) for r in rows]


def safe_http_url(url: str | None) -> str | None:
    """Return url only if it is http(s); reject javascript: and other schemes."""
    if not url or not isinstance(url, str):
        return None
    text = url.strip()
    if not text or text.lower().startswith("javascript:"):
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return text


def parse_analysis_json(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
