import sqlite3
from pathlib import Path

conn = sqlite3.connect(Path(__file__).with_name("saffron.db").as_uri() + "?mode=ro", uri=True)

rows = conn.execute(
    "SELECT * FROM reservations"
).fetchall()

for row in rows:
    print(*row)
    
conn.close()