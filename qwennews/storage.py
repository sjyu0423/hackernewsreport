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
            conn.execute(
                "INSERT INTO schema_meta(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                ("schema_version", "1"),
            )
            conn.commit()
        logger.info("Initialized database at %s", self.db_path)

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
