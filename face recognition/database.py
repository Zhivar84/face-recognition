"""Databases for students and attendance events (SQLite)."""
from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent / "attendance.db"

# فیلدهای قابل ویرایش دانشجو از طریق پنل داشبورد
STUDENT_FIELDS = ("full_name", "student_no", "major", "email", "phone")


@contextmanager
def get_conn():
    # timeout: هم‌زمانی داشبورد با monitor.py روی SQLite
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_columns(conn) -> None:
    """مهاجرت امن: افزودن ستون‌های جدید به جدول students بدون از دست دادن داده."""
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(students)")}
    for col in ("major", "email", "phone", "photo"):
        if col not in existing:
            conn.execute(f"ALTER TABLE students ADD COLUMN {col} TEXT")


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                student_no TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL REFERENCES students(id),
                event TEXT NOT NULL CHECK (event IN ('IN', 'OUT')),
                similarity REAL,
                logged_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
            CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id, logged_at);
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        _ensure_columns(conn)


def add_student(
    full_name: str,
    student_no: str,
    major: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO students (full_name, student_no, major, email, phone) VALUES (?, ?, ?, ?, ?)",
            (full_name, student_no, major, email, phone),
        )
        return cur.lastrowid


def get_student(student_no: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE student_no = ?", (student_no,)
        ).fetchone()


def get_student_by_id(student_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE id = ?", (student_id,)
        ).fetchone()


def student_no_taken(student_no: str, exclude_id: int | None = None) -> bool:
    with get_conn() as conn:
        if exclude_id is None:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_no = ?", (student_no,)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM students WHERE student_no = ? AND id <> ?",
                (student_no, exclude_id),
            ).fetchone()
        return row is not None


def update_student(student_id: int, fields: dict) -> bool:
    """فقط فیلدهای سفیدشده در STUDENT_FIELDS نوشته می‌شوند."""
    cols = [c for c in STUDENT_FIELDS if c in fields]
    if not cols:
        return False
    assignments = ", ".join(f"{c} = ?" for c in cols)
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE students SET {assignments} WHERE id = ?",
            [fields[c] for c in cols] + [student_id],
        )
        return cur.rowcount > 0


def delete_student(student_id: int) -> bool:
    with get_conn() as conn:
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        cur = conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        return cur.rowcount > 0


def list_students():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM students ORDER BY id").fetchall()


def set_student_photo(student_id: int, filename: str | None) -> None:
    """فایل عکس خارج از STUDENT_FIELDS است تا ویرایش اطلاعات، عکس را پاک نکند."""
    with get_conn() as conn:
        conn.execute("UPDATE students SET photo = ? WHERE id = ?", (filename, student_id))


def last_event(student_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM attendance WHERE student_id = ? ORDER BY logged_at DESC, id DESC LIMIT 1",
            (student_id,),
        ).fetchone()


def log_event(student_id: int, event: str, similarity: float | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO attendance (student_id, event, similarity) VALUES (?, ?, ?)",
            (student_id, event, similarity),
        )


def daily_report(day: date):
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT s.full_name, s.student_no, a.student_id, a.event, a.logged_at, a.similarity
            FROM attendance a JOIN students s ON s.id = a.student_id
            WHERE date(a.logged_at) = ?
            ORDER BY a.logged_at
            """,
            (day.isoformat(),),
        ).fetchall()


# ---------- تنظیمات ساعت مجاز ورود و خروج ----------

DEFAULT_SETTINGS = {
    "hours_enabled": "0",
    "in_start": "07:00",
    "in_end": "12:00",
    "out_start": "15:00",
    "out_end": "22:00",
    "eod_enabled": "1",
    "eod_time": "23:00",
    "eod_last_date": "",
}


def get_settings() -> dict:
    out = dict(DEFAULT_SETTINGS)
    with get_conn() as conn:
        for r in conn.execute("SELECT key, value FROM settings"):
            if r["key"] in out:
                out[r["key"]] = r["value"]
    return out


def save_settings(values: dict) -> dict:
    with get_conn() as conn:
        for key, value in values.items():
            if key in DEFAULT_SETTINGS:
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, str(value)),
                )
    return get_settings()


def is_hhmm(value: str) -> bool:
    return bool(re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", value or ""))


def _in_window(hhmm: str, start: str, end: str) -> bool:
    if not (is_hhmm(start) and is_hhmm(end)):
        return True                      # بازه تعریف‌نشده = همه ساعت‌ها مجاز
    if start <= end:
        return start <= hhmm <= end
    return hhmm >= start or hhmm <= end   # بازه‌ای که از نیمه‌شب می‌گذرد


def classify_event(event: str, logged_at: str, settings: dict | None = None) -> str:
    """'ok' یا 'suspicious' بر اساس بازه ساعت مجاز؛ logged_at قالب 'YYYY-MM-DD HH:MM:SS'."""
    s = settings if settings is not None else get_settings()
    if s["hours_enabled"] != "1":
        return "ok"
    hhmm = (logged_at or "")[11:16]
    if len(hhmm) != 5:
        return "ok"
    if event == "IN":
        window = (s["in_start"], s["in_end"])
    elif event == "OUT":
        window = (s["out_start"], s["out_end"])
    else:
        return "ok"
    return "ok" if _in_window(hhmm, *window) else "suspicious"

