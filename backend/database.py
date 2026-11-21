"""SQLite helpers. Plain sqlite3 (no ORM) so it stays easy to read."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "lms_chatbot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL DEFAULT 'New chat',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  sources TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  pages INTEGER NOT NULL DEFAULT 0,
  text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_documents_chat ON documents(chat_id);
"""


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)


# ---------- chats ----------
def create_chat(title="New chat"):
    with get_db() as db:
        cur = db.execute("INSERT INTO chats (title) VALUES (?)", (title,))
        return cur.lastrowid


def list_chats():
    with get_db() as db:
        rows = db.execute(
            "SELECT id, title, updated_at FROM chats ORDER BY updated_at DESC, id DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_chat(chat_id):
    with get_db() as db:
        row = db.execute("SELECT id, title FROM chats WHERE id = ?", (chat_id,)).fetchone()
        return dict(row) if row else None


def set_title(chat_id, title):
    with get_db() as db:
        db.execute("UPDATE chats SET title = ? WHERE id = ?", (title, chat_id))


def delete_chat(chat_id):
    with get_db() as db:
        db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))


# ---------- messages ----------
def add_message(chat_id, role, content, sources=None):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO messages (chat_id, role, content, sources) VALUES (?, ?, ?, ?)",
            (chat_id, role, content, json.dumps(sources or [])),
        )
        db.execute("UPDATE chats SET updated_at = datetime('now') WHERE id = ?", (chat_id,))
        return cur.lastrowid


def get_messages(chat_id):
    with get_db() as db:
        rows = db.execute(
            "SELECT id, role, content, sources FROM messages WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        ).fetchall()
    return [{**dict(r), "sources": json.loads(r["sources"])} for r in rows]


def delete_last_assistant(chat_id):
    """Remove the last message only if it is an assistant reply (used by Regenerate)."""
    msgs = get_messages(chat_id)
    if msgs and msgs[-1]["role"] == "assistant":
        with get_db() as db:
            db.execute("DELETE FROM messages WHERE id = ?", (msgs[-1]["id"],))


# ---------- documents ----------
def add_document(chat_id, filename, pages, text):
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO documents (chat_id, filename, pages, text) VALUES (?, ?, ?, ?)",
            (chat_id, filename, pages, text),
        )
        return cur.lastrowid


def list_documents(chat_id, with_text=False):
    cols = "id, filename, pages" + (", text" if with_text else "")
    with get_db() as db:
        rows = db.execute(
            f"SELECT {cols} FROM documents WHERE chat_id = ? ORDER BY id", (chat_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_document(doc_id):
    with get_db() as db:
        db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
