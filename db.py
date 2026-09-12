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

def db():
    conn = sqlite3.connect(Path(__file__).with_name("saffron.db"))
    conn.row_factory = sqlite3.Row
    ensure_order_timestamps(conn)
    
    return conn