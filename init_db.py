from db import connect, init_schema
conn = connect()

init_schema(conn)
conn.close()

print("Database created!")