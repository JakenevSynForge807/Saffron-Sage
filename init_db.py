import sqlite3

conn = sqlite3.connect("saffron.db")
conn.executescript("""
    CREATE TABLE IF NOT EXISTS reservations (
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
    )
    """)

from app import ensure_order_timestamps
ensure_order_timestamps(conn)
conn.commit(); conn.close()

print("Database created!")