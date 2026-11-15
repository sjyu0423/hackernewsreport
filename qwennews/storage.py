"""SQLite persistence for articles, source sightings, and collection runs."""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from qwennews.models import Article, CollectionStats, ContentExtractionStatus, ensure_utc, utc_now

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL UNIQUE,
    original_url TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TEXT,
    discovered_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    author TEXT,
    article_text TEXT,
    content_extraction_status TEXT NOT NULL,
    hn_score INTEGER,
    hn_comment_count INTEGER,
    hn_discussion_url TEXT
);

CREATE TABLE IF NOT EXISTS article_sources (
    article_id TEXT NOT NULL,
    source TEXT NOT NULL,
    source_item_id TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY (article_id, source),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    articles_seen INTEGER NOT NULL DEFAULT 0,
    articles_new INTEGER NOT NULL DEFAULT 0,
    articles_updated INTEGER NOT NULL DEFAULT 0,
    duplicates INTEGER NOT NULL DEFAULT 0,
    extraction_success INTEGER NOT NULL DEFAULT 0,
    extraction_failed INTEGER NOT NULL DEFAULT 0,
    extraction_skipped INTEGER NOT NULL DEFAULT 0,
    extraction_blocked INTEGER NOT NULL DEFAULT 0,
    source_errors_json TEXT,
    disabled_sources_json TEXT,
    elapsed_seconds REAL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS collection_run_sources (
    run_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    items_fetched INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    PRIMARY KEY (run_id, source),
    FOREIGN KEY (run_id) REFERENCES collection_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_articles_discovered_at ON articles(discovered_at);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_article_sources_source ON article_sources(source);
CREATE INDEX IF NOT EXISTS idx_articles_canonical_url ON articles(canonical_url);

CREATE TABLE IF NOT EXISTS article_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    model_id TEXT NOT NULL,
    config_version TEXT NOT NULL,
    analysis_json TEXT NOT NULL,
    metrics_json TEXT,
    raw_response TEXT,
    thinking TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (article_id, content_hash, model_id, config_version),
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_article_analyses_article
    ON article_analyses(article_id, created_at DESC);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    hours INTEGER NOT NULL,
    story_count INTEGER NOT NULL,
    path TEXT,
    markdown TEXT NOT NULL,
    mode TEXT,
    as_of TEXT,
    window_start TEXT,
    status TEXT,
    significant_only INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_reported_at TEXT,
    significant_update_at TEXT,
    primary_article_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_articles (
    story_id TEXT NOT NULL,
    article_id TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    link_reason TEXT,
    PRIMARY KEY (story_id, article_id),
    FOREIGN KEY (story_id) REFERENCES stories(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS story_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT,
    article_id TEXT,
    decision TEXT NOT NULL,
    evidence_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_watermarks (
    mode TEXT PRIMARY KEY,
    watermark_at TEXT NOT NULL,
    last_report_id INTEGER,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_stories_last_seen ON stories(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_story_articles_article ON story_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_story_events_story ON story_events(story_id, created_at);
"""


def _dt_to_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    value = ensure_utc(value)
    assert value is not None
    return value.isoformat().replace("+00:00", "Z")


def _dt_from_iso(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.replace("Z", "+00:00")
    return ensure_utc(datetime.fromisoformat(text))


class ArticleStore:
    """Small persistent store with idempotent upserts."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)
            self._migrate_reports_table(conn)
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("schema_version", "3"),
            )
            conn.commit()
        logger.info("Initialized database at %s", self.db_path)

    def _migrate_reports_table(self, conn: sqlite3.Connection) -> None:
        """Add M2 columns to legacy reports tables without destroying rows."""
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(reports)").fetchall()}
        alterations = {
            "mode": "ALTER TABLE reports ADD COLUMN mode TEXT",
            "as_of": "ALTER TABLE reports ADD COLUMN as_of TEXT",
            "window_start": "ALTER TABLE reports ADD COLUMN window_start TEXT",
            "status": "ALTER TABLE reports ADD COLUMN status TEXT",
            "significant_only": (
                "ALTER TABLE reports ADD COLUMN significant_only INTEGER DEFAULT 0"
            ),
        }
        for name, ddl in alterations.items():
            if name not in cols:
                conn.execute(ddl)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def upsert_article(self, article: Article) -> str:
        """
        Insert or update an article by stable id / canonical URL.

        Returns one of: "new", "updated", "duplicate".
        """
        now = utc_now()
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM articles WHERE id = ? OR canonical_url = ?",
                (article.id, article.canonical_url),
            ).fetchone()

            if existing is None:
                conn.execute(
                    """
                    INSERT INTO articles (
                        id, canonical_url, original_url, title, published_at,
                        discovered_at, updated_at, author, article_text,
                        content_extraction_status, hn_score, hn_comment_count,
                        hn_discussion_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        article.id,
                        article.canonical_url,
                        article.original_url,
                        article.title,
                        _dt_to_iso(article.published_at),
                        _dt_to_iso(article.discovered_at),
                        _dt_to_iso(now),
                        article.author,
                        article.article_text,
                        article.content_extraction_status.value,
                        article.hn_score,
                        article.hn_comment_count,
                        article.hn_discussion_url,
                    ),
                )
                self._upsert_source(conn, article, now, first=True)
                conn.commit()
                return "new"

            article_id = existing["id"]
            changed = self._merge_and_update(conn, existing, article, now)
            self._upsert_source(conn, article, now, first=False, article_id=article_id)
            conn.commit()
            return "updated" if changed else "duplicate"

    def _merge_and_update(
        self,
        conn: sqlite3.Connection,
        existing: sqlite3.Row,
        article: Article,
        now: datetime,
    ) -> bool:
        """Merge non-empty fields; return True if the article row changed meaningfully."""
        title = article.title or existing["title"]
        original_url = existing["original_url"] or article.original_url
        published_at = _dt_to_iso(article.published_at) or existing["published_at"]
        author = article.author or existing["author"]

        # Prefer successful extraction; do not wipe good text on later failures.
        article_text = existing["article_text"]
        status = existing["content_extraction_status"]
        if article.content_extraction_status == ContentExtractionStatus.SUCCESS:
            article_text = article.article_text
            status = ContentExtractionStatus.SUCCESS.value
        elif not article_text and article.article_text:
            article_text = article.article_text
            status = article.content_extraction_status.value
        elif status == ContentExtractionStatus.PENDING.value:
            status = article.content_extraction_status.value

        hn_score = article.hn_score if article.hn_score is not None else existing["hn_score"]
        hn_comment_count = (
            article.hn_comment_count
            if article.hn_comment_count is not None
            else existing["hn_comment_count"]
        )
        hn_discussion_url = article.hn_discussion_url or existing["hn_discussion_url"]

        changed = any(
            [
                title != existing["title"],
                published_at != existing["published_at"],
                author != existing["author"],
                article_text != existing["article_text"],
                status != existing["content_extraction_status"],
                hn_score != existing["hn_score"],
                hn_comment_count != existing["hn_comment_count"],
                hn_discussion_url != existing["hn_discussion_url"],
            ]
        )

        conn.execute(
            """
            UPDATE articles SET
                title = ?,
                original_url = ?,
                published_at = ?,
                author = ?,
                article_text = ?,
                content_extraction_status = ?,
                hn_score = ?,
                hn_comment_count = ?,
                hn_discussion_url = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                title,
                original_url,
                published_at,
                author,
                article_text,
                status,
                hn_score,
                hn_comment_count,
                hn_discussion_url,
                _dt_to_iso(now),
                existing["id"],
            ),
        )
        return changed

    def _upsert_source(
        self,
        conn: sqlite3.Connection,
        article: Article,
        now: datetime,
        *,
        first: bool,
        article_id: str | None = None,
    ) -> None:
        aid = article_id or article.id
        sources = [article.source, *article.extra_sources]
        for source in dict.fromkeys(sources):  # preserve order, unique
            row = conn.execute(
                "SELECT 1 FROM article_sources WHERE article_id = ? AND source = ?",
                (aid, source),
            ).fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO article_sources (
                        article_id, source, source_item_id, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        aid,
                        source,
                        article.source_item_id if source == article.source else None,
                        _dt_to_iso(now if not first else article.discovered_at),
                        _dt_to_iso(now),
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE article_sources
                    SET last_seen_at = ?,
                        source_item_id = COALESCE(?, source_item_id)
                    WHERE article_id = ? AND source = ?
                    """,
                    (
                        _dt_to_iso(now),
                        article.source_item_id if source == article.source else None,
                        aid,
                        source,
                    ),
                )

    def update_extraction(
        self,
        article_id: str,
        *,
        text: str | None,
        status: ContentExtractionStatus,
    ) -> None:
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT article_text, content_extraction_status FROM articles WHERE id = ?",
                (article_id,),
            ).fetchone()
            if existing is None:
                return
            # Do not overwrite successful text with a later failure.
            if (
                existing["content_extraction_status"] == ContentExtractionStatus.SUCCESS.value
                and status != ContentExtractionStatus.SUCCESS
            ):
                return
            conn.execute(
                """
                UPDATE articles
                SET article_text = ?, content_extraction_status = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    text if status == ContentExtractionStatus.SUCCESS else existing["article_text"],
                    status.value,
                    _dt_to_iso(utc_now()),
                    article_id,
                ),
            )
            if status == ContentExtractionStatus.SUCCESS and text:
                conn.execute(
                    "UPDATE articles SET article_text = ? WHERE id = ?",
                    (text, article_id),
                )
            conn.commit()

    def start_run(self) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO collection_runs (started_at, status)
                VALUES (?, ?)
                """,
                (_dt_to_iso(utc_now()), "running"),
            )
            conn.commit()
            return int(cur.lastrowid)

    def finish_run(
        self,
        run_id: int,
        stats: CollectionStats,
        *,
        status: str = "completed",
        source_results: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE collection_runs SET
                    finished_at = ?,
                    status = ?,
                    articles_seen = ?,
                    articles_new = ?,
                    articles_updated = ?,
                    duplicates = ?,
                    extraction_success = ?,
                    extraction_failed = ?,
                    extraction_skipped = ?,
                    extraction_blocked = ?,
                    source_errors_json = ?,
                    disabled_sources_json = ?,
                    elapsed_seconds = ?
                WHERE id = ?
                """,
                (
                    _dt_to_iso(utc_now()),
                    status,
                    stats.articles_seen,
                    stats.articles_new,
                    stats.articles_updated,
                    stats.duplicates,
                    stats.extraction_success,
                    stats.extraction_failed,
                    stats.extraction_skipped,
                    stats.extraction_blocked,
                    json.dumps(stats.source_errors),
                    json.dumps(stats.disabled_sources),
                    stats.elapsed_seconds,
                    run_id,
                ),
            )
            if source_results:
                for source, payload in source_results.items():
                    conn.execute(
                        """
                        INSERT INTO collection_run_sources (
                            run_id, source, status, items_fetched, error
                        ) VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(run_id, source) DO UPDATE SET
                            status=excluded.status,
                            items_fetched=excluded.items_fetched,
                            error=excluded.error
                        """,
                        (
                            run_id,
                            source,
                            payload.get("status", "unknown"),
                            int(payload.get("items_fetched", 0)),
                            payload.get("error"),
                        ),
                    )
            conn.commit()

    def recent_articles(self, hours: int = 24, limit: int = 100) -> list[dict[str, Any]]:
        cutoff = utc_now() - timedelta(hours=hours)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT a.*, GROUP_CONCAT(s.source, ',') AS sources
                FROM articles a
                LEFT JOIN article_sources s ON s.article_id = a.id
                WHERE a.discovered_at >= ? OR a.updated_at >= ?
                GROUP BY a.id
                ORDER BY COALESCE(a.published_at, a.discovered_at) DESC
                LIMIT ?
                """,
                (_dt_to_iso(cutoff), _dt_to_iso(cutoff), limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            article_count = conn.execute("SELECT COUNT(*) AS c FROM articles").fetchone()["c"]
            by_source = conn.execute(
                """
                SELECT source, COUNT(*) AS c
                FROM article_sources
                GROUP BY source
                ORDER BY source
                """
            ).fetchall()
            by_status = conn.execute(
                """
                SELECT content_extraction_status AS status, COUNT(*) AS c
                FROM articles
                GROUP BY content_extraction_status
                ORDER BY status
                """
            ).fetchall()
            runs = conn.execute(
                """
                SELECT id, started_at, finished_at, status, articles_seen, articles_new,
                       duplicates, extraction_success, extraction_failed, elapsed_seconds
                FROM collection_runs
                ORDER BY id DESC
                LIMIT 5
                """
            ).fetchall()
            return {
                "article_count": article_count,
                "by_source": {row["source"]: row["c"] for row in by_source},
                "by_extraction_status": {row["status"]: row["c"] for row in by_status},
                "recent_runs": [dict(row) for row in runs],
                "db_path": str(self.db_path),
            }

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
            return dict(row) if row else None

    def get_analysis(
        self,
        article_id: str,
        *,
        content_hash: str,
        model_id: str,
        config_version: str,
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM article_analyses
                WHERE article_id = ? AND content_hash = ?
                  AND model_id = ? AND config_version = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id, content_hash, model_id, config_version),
            ).fetchone()
            return dict(row) if row else None

    def get_latest_analysis(self, article_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM article_analyses
                WHERE article_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (article_id,),
            ).fetchone()
            return dict(row) if row else None

    def save_analysis(
        self,
        *,
        article_id: str,
        content_hash: str,
        model_id: str,
        config_version: str,
        analysis: Any,
        metrics: dict[str, Any] | None = None,
        raw_response: str | None = None,
        thinking: str | None = None,
    ) -> None:
        analysis_json = analysis if isinstance(analysis, str) else analysis.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO article_analyses (
                    article_id, content_hash, model_id, config_version,
                    analysis_json, metrics_json, raw_response, thinking, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(article_id, content_hash, model_id, config_version)
                DO UPDATE SET
                    analysis_json=excluded.analysis_json,
                    metrics_json=excluded.metrics_json,
                    raw_response=excluded.raw_response,
                    thinking=excluded.thinking,
                    created_at=excluded.created_at
                """,
                (
                    article_id,
                    content_hash,
                    model_id,
                    config_version,
                    analysis_json,
                    json.dumps(metrics or {}),
                    raw_response,
                    thinking,
                    _dt_to_iso(utc_now()),
                ),
            )
            conn.commit()

    def save_report(
        self,
        *,
        path: str | None,
        hours: int,
        story_count: int,
        markdown: str,
        mode: str | None = None,
        as_of: str | None = None,
        window_start: str | None = None,
        status: str = "completed",
        significant_only: bool = False,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO reports (
                    created_at, hours, story_count, path, markdown,
                    mode, as_of, window_start, status, significant_only
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _dt_to_iso(utc_now()),
                    hours,
                    story_count,
                    path,
                    markdown,
                    mode,
                    as_of,
                    window_start,
                    status,
                    1 if significant_only else 0,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def analysis_count(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) AS c FROM article_analyses").fetchone()["c"])

    # --- M2 story memory ---

    def create_story(
        self,
        *,
        story_id: str,
        title: str,
        primary_article_id: str | None,
        category: str | None = None,
        seen_at: str | None = None,
    ) -> None:
        now = seen_at or _dt_to_iso(utc_now())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO stories (
                    id, title, category, first_seen_at, last_seen_at,
                    significant_update_at, primary_article_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    story_id,
                    title,
                    category,
                    now,
                    now,
                    now,
                    primary_article_id,
                    now,
                    now,
                ),
            )
            conn.commit()

    def add_article_to_story(
        self,
        story_id: str,
        article_id: str,
        *,
        link_reason: str | None = None,
        linked_at: str | None = None,
    ) -> None:
        now = linked_at or _dt_to_iso(utc_now())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO story_articles (story_id, article_id, linked_at, link_reason)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(story_id, article_id) DO UPDATE SET
                    link_reason=COALESCE(excluded.link_reason, story_articles.link_reason)
                """,
                (story_id, article_id, now, link_reason),
            )
            conn.commit()

    def get_story_id_for_article(self, article_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT story_id FROM story_articles WHERE article_id = ? LIMIT 1",
                (article_id,),
            ).fetchone()
            return str(row["story_id"]) if row else None

    def list_stories(self, limit: int = 500) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM stories
                ORDER BY COALESCE(significant_update_at, last_seen_at) DESC
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
                SELECT a.*, GROUP_CONCAT(s.source, ',') AS sources,
                       sa.link_reason, sa.linked_at
                FROM story_articles sa
                JOIN articles a ON a.id = sa.article_id
                LEFT JOIN article_sources s ON s.article_id = a.id
                WHERE sa.story_id = ?
                GROUP BY a.id
                ORDER BY a.discovered_at ASC
                """,
                (story_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def touch_story(
        self,
        story_id: str,
        *,
        significant_update: bool,
        title: str | None = None,
        category: str | None = None,
        seen_at: str | None = None,
    ) -> None:
        now = seen_at or _dt_to_iso(utc_now())
        with self._connect() as conn:
            row = conn.execute(
                "SELECT title, category FROM stories WHERE id = ?", (story_id,)
            ).fetchone()
            if row is None:
                return
            conn.execute(
                """
                UPDATE stories SET
                    title = ?,
                    category = ?,
                    last_seen_at = ?,
                    significant_update_at = CASE
                        WHEN ? THEN ?
                        ELSE significant_update_at
                    END,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    title or row["title"],
                    category if category is not None else row["category"],
                    now,
                    1 if significant_update else 0,
                    now,
                    now,
                    story_id,
                ),
            )
            conn.commit()

    def mark_story_reported(self, story_id: str, reported_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE stories SET last_reported_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (reported_at, reported_at, story_id),
            )
            conn.commit()

    def record_story_event(self, decision: Any) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO story_events (
                    story_id, article_id, decision, evidence_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    getattr(decision, "story_id", None),
                    getattr(decision, "article_id", None),
                    str(getattr(decision, "decision", decision)),
                    json.dumps(getattr(decision, "evidence", {}) or {}),
                    _dt_to_iso(utc_now()),
                ),
            )
            conn.commit()

    def list_story_events(
        self, story_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if story_id:
                rows = conn.execute(
                    """
                    SELECT * FROM story_events
                    WHERE story_id = ?
                    ORDER BY id DESC LIMIT ?
                    """,
                    (story_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM story_events ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_watermark(self, mode: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM report_watermarks WHERE mode = ?",
                (mode,),
            ).fetchone()
            return dict(row) if row else None

    def set_watermark(
        self,
        mode: str,
        watermark_at: str,
        *,
        last_report_id: int | None = None,
    ) -> None:
        now = _dt_to_iso(utc_now())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_watermarks (mode, watermark_at, last_report_id, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(mode) DO UPDATE SET
                    watermark_at=excluded.watermark_at,
                    last_report_id=excluded.last_report_id,
                    updated_at=excluded.updated_at
                """,
                (mode, watermark_at, last_report_id, now),
            )
            conn.commit()
