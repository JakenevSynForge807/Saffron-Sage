import sqlite3

conn = sqlite3.connect("market.db")

rows = conn.execute(
    "SELECT * FROM reservations"
).fetchall()

for row in rows:
    print(*row)
    
conn.close()