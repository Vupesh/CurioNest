import sqlite3
import os
from datetime import datetime

DB_PATH = "curionest_logs.db"

DAILY_BUDGET = int(os.getenv("DAILY_TOKEN_BUDGET", "150000"))
HOURLY_BUDGET = int(os.getenv("HOURLY_TOKEN_BUDGET", "15000"))


def _get_connection():
    return sqlite3.connect(DB_PATH)


def check_and_update(tokens_to_add=0):
    now = datetime.utcnow()
    today = now.date().isoformat()
    hour = now.strftime("%Y-%m-%dT%H")

    conn = _get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT daily_tokens, hourly_tokens, day, hour FROM usage_counters WHERE id = 1"
    )
    daily_tokens, hourly_tokens, stored_day, stored_hour = cur.fetchone()

    # ✅ Correct reset logic with persistent state repair
    if stored_day != today:
        daily_tokens = 0
        stored_day = today

    if stored_hour != hour:
        hourly_tokens = 0
        stored_hour = hour

    if daily_tokens >= DAILY_BUDGET:
        conn.close()
        return True, "Daily token budget exceeded"

    if hourly_tokens >= HOURLY_BUDGET:
        conn.close()
        return True, "Hourly token budget exceeded"

    daily_tokens += tokens_to_add
    hourly_tokens += tokens_to_add

    cur.execute(
        """
        UPDATE usage_counters
        SET daily_tokens = ?, hourly_tokens = ?, day = ?, hour = ?
        WHERE id = 1
        """,
        (daily_tokens, hourly_tokens, stored_day, stored_hour),
    )

    conn.commit()
    conn.close()

    return False, None
