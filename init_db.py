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
    """)

conn.commit(); conn.close()

print("Database created!")