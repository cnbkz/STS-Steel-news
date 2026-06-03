"""
database.py - SQLite DB 초기화 및 CRUD 관리
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "newsletter.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """DB 및 테이블 초기화"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash     TEXT UNIQUE NOT NULL,
            title        TEXT NOT NULL,
            url          TEXT NOT NULL,
            source       TEXT,
            content      TEXT,
            image_url    TEXT,
            category     TEXT,
            published_at TEXT,
            score        INTEGER DEFAULT 0,
            collected_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS newsletters (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            volume        INTEGER NOT NULL,
            week_label    TEXT,
            subject       TEXT,
            html_body     TEXT,
            plain_text    TEXT,
            kakao_summary TEXT,
            headline      TEXT,
            status        TEXT DEFAULT 'draft',
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at       TEXT
        );

        CREATE TABLE IF NOT EXISTS send_logs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            newsletter_id    INTEGER REFERENCES newsletters(id),
            channel          TEXT NOT NULL,
            recipient_masked TEXT NOT NULL,
            status           TEXT NOT NULL,
            error_message    TEXT,
            sent_at          TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subscribers (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT NOT NULL,
            email             TEXT UNIQUE NOT NULL,
            phone             TEXT,
            group_name        TEXT,
            email_subscribed  INTEGER DEFAULT 1,
            kakao_subscribed  INTEGER DEFAULT 1,
            created_at        TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


# ─── Articles ──────────────────────────────────────────────
def insert_article(article: dict) -> bool:
    """기사 저장 (중복 시 무시). 성공하면 True 반환."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR IGNORE INTO articles
            (url_hash, title, url, source, content, image_url, category, published_at, score)
            VALUES (:url_hash, :title, :url, :source, :content, :image_url, :category, :published_at, :score)
        """, article)
        conn.commit()
        return conn.execute("SELECT changes()").fetchone()[0] > 0
    finally:
        conn.close()


def get_recent_articles(limit=30):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM articles ORDER BY score DESC, collected_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_article_count():
    conn = get_connection()
    try:
        return conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    finally:
        conn.close()


def clear_articles():
    conn = get_connection()
    try:
        conn.execute("DELETE FROM articles")
        conn.commit()
    finally:
        conn.close()


# ─── Newsletters ───────────────────────────────────────────
def save_newsletter(nl: dict) -> int:
    """뉴스레터 저장, 생성된 id 반환."""
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO newsletters
            (volume, week_label, subject, html_body, plain_text, kakao_summary, headline, status)
            VALUES (:volume, :week_label, :subject, :html_body, :plain_text, :kakao_summary, :headline, :status)
        """, nl)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_newsletter_status(nl_id: int, status: str, sent_at: str = None):
    conn = get_connection()
    try:
        if sent_at:
            conn.execute(
                "UPDATE newsletters SET status=?, sent_at=? WHERE id=?",
                (status, sent_at, nl_id)
            )
        else:
            conn.execute("UPDATE newsletters SET status=? WHERE id=?", (status, nl_id))
        conn.commit()
    finally:
        conn.close()


def get_newsletters(limit=20):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM newsletters ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_newsletter_by_id(nl_id: int):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM newsletters WHERE id=?", (nl_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_next_volume():
    conn = get_connection()
    try:
        row = conn.execute("SELECT MAX(volume) FROM newsletters").fetchone()
        return (row[0] or 0) + 1
    finally:
        conn.close()


# ─── Send Logs ────────────────────────────────────────────
def log_send(newsletter_id: int, channel: str, recipient_email: str, status: str, error: str = None):
    masked = recipient_email[:3] + "***@" + recipient_email.split("@")[-1] if "@" in recipient_email else recipient_email[:3] + "***"
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO send_logs (newsletter_id, channel, recipient_masked, status, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (newsletter_id, channel, masked, status, error))
        conn.commit()
    finally:
        conn.close()


def get_send_stats(newsletter_id: int = None):
    conn = get_connection()
    try:
        if newsletter_id:
            rows = conn.execute(
                "SELECT channel, status, COUNT(*) as cnt FROM send_logs WHERE newsletter_id=? GROUP BY channel, status",
                (newsletter_id,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT channel, status, COUNT(*) as cnt FROM send_logs GROUP BY channel, status"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_send_logs(limit=100):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT sl.*, n.week_label, n.volume FROM send_logs sl LEFT JOIN newsletters n ON sl.newsletter_id=n.id ORDER BY sl.sent_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── Subscribers ──────────────────────────────────────────
def upsert_subscriber(sub: dict):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO subscribers (name, email, phone, group_name, email_subscribed, kakao_subscribed)
            VALUES (:name, :email, :phone, :group_name, :email_subscribed, :kakao_subscribed)
            ON CONFLICT(email) DO UPDATE SET
                name=excluded.name,
                phone=excluded.phone,
                group_name=excluded.group_name,
                email_subscribed=excluded.email_subscribed,
                kakao_subscribed=excluded.kakao_subscribed
        """, sub)
        conn.commit()
    finally:
        conn.close()


def get_subscribers(active_only=True):
    conn = get_connection()
    try:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM subscribers WHERE email_subscribed=1 ORDER BY group_name, name"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM subscribers ORDER BY group_name, name"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def delete_subscriber(email: str):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM subscribers WHERE email=?", (email,))
        conn.commit()
    finally:
        conn.close()


def get_subscriber_count():
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM subscribers WHERE email_subscribed=1").fetchone()[0]
        return {"total": total, "active": active}
    finally:
        conn.close()
