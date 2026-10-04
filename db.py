import sqlite3
from pathlib import Path

def ensure_order_timestamps(conn):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(orderTable)")}
    if not columns:
        return
    if "created_at" not in columns:
        conn.execute("ALTER TABLE orderTable ADD COLUMN created_at TEXT")
    if "order_group_id" not in columns:
        conn.execute("ALTER TABLE orderTable ADD COLUMN order_group_id INTEGER")
    # Existing dates are unknown; only stamp newly inserted orders.
    conn.execute("""CREATE TRIGGER IF NOT EXISTS stamp_order_created_at
        AFTER INSERT ON orderTable WHEN NEW.created_at IS NULL
        BEGIN
            UPDATE orderTable SET created_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END""")
    conn.commit()

def ensure_chat_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ai_chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT 'New chat',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ai_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES ai_chats(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_ai_chats_user_updated
            ON ai_chats(user_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_ai_messages_chat
            ON ai_messages(chat_id, id);
    """)
    conn.commit()

def db():
    conn = sqlite3.connect(Path(__file__).with_name("saffron.db"))
    conn.row_factory = sqlite3.Row
    ensure_order_timestamps(conn)
    ensure_chat_tables(conn)
    
    return conn