import sqlite3

conn = sqlite3.connect("curionest_logs.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS usage_counters (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    daily_tokens INTEGER DEFAULT 0,
    hourly_tokens INTEGER DEFAULT 0,
    day TEXT,
    hour TEXT
)
""")

cur.execute("""
INSERT OR IGNORE INTO usage_counters (id, daily_tokens, hourly_tokens, day, hour)
VALUES (1, 0, 0, '', '')
""")

conn.commit()
conn.close()

print("usage_counters table ready")
