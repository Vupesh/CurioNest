import sqlite3
from collections import Counter

conn = sqlite3.connect("curionest_logs.db")
cursor = conn.cursor()

cursor.execute("SELECT event_type, details FROM logs")
rows = cursor.fetchall()

counter = Counter()

token_usage = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
}

for event_type, details in rows:

    counter[event_type] += 1

    if event_type == "OPENAI_USAGE":
        try:
            data = eval(details)
            token_usage["prompt_tokens"] += data.get("prompt_tokens", 0)
            token_usage["completion_tokens"] += data.get("completion_tokens", 0)
            token_usage["total_tokens"] += data.get("total_tokens", 0)
        except Exception:
            pass

print("\n=== EVENT COUNTS ===")
for k, v in counter.items():
    print(f"{k}: {v}")

print("\n=== TOKEN USAGE ===")
for k, v in token_usage.items():
    print(f"{k}: {v}")
