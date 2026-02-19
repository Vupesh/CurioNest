import sqlite3

conn = sqlite3.connect("curionest_logs.db")
cur = conn.cursor()

for row in cur.execute("SELECT * FROM usage_counters"):
    print(row)

conn.close()
