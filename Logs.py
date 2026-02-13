import sqlite3

conn = sqlite3.connect("curionest_logs.db")
cursor = conn.cursor()

for row in cursor.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 10"):
    print(row)

conn.close()
