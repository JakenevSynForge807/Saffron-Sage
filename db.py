from threading import Lock
import config
import sqlite3
SCHEMA = """CREATE TABLE IF NOT EXISTS reservations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT,
        last_name TEXT,
        email TEXT,
        date TEXT,
        time TEXT,
        guests INTEGER,
        seating TEXT,
        occasion TEXT,
        special_requests TEXT     
    );
    
    CREATE TABLE IF NOT EXISTS contact (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        message TEXT
    );
    
    CREATE TABLE IF NOT EXISTS usersInfo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT,
        email UNIQUE,
        password TEXT,
        role TEXT 
    );
    
    CREATE TABLE IF NOT EXISTS dishesTable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dishname TEXT,
        dishprice REAL,
        sellerid INTEGER
    );
    
    CREATE TABLE IF NOT EXISTS cartItems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dishid INTEGER,
        buyerid INTEGER,
        quantity INTEGER
    );
    
    CREATE TABLE IF NOT EXISTS orderTable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dishid INTEGER,
        buyerid INTEGER,
        quantity INTEGER,
        fullname TEXT,
        phone INTEGER,
        deliveryAddress TEXT,
        notes TEXT,
        paymentMethod TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        order_group_id INTEGER,
        status TEXT DEFAULT 'pending'        
    );

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
        ON ai_messages(chat_id, id)
"""

_schema_lock = Lock()
_schema_ready = False

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
    conn.executescript(SCHEMA)
    conn.commit()
    
def init_schema(conn):
    conn.executescript(SCHEMA)
    ensure_order_timestamps(conn)

    conn.commit()

def connect():
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    
    return conn

def db():
    global _schema_ready
    conn = connect()

    if not _schema_ready:
        with _schema_lock:
            if not _schema_ready:
                conn.execute("PRAGMA journal_mode = WAL")
                init_schema(conn)
                _schema_ready = True
    return conn