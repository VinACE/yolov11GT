#!/usr/bin/env python3
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime, timedelta
import pytz
import requests
import os


API_BASE = os.environ.get("ANALYTICS_API_BASE", "http://localhost:8000")


def reset_job() -> None:
    try:
        r = requests.post(f"{API_BASE}/reset-daily", timeout=10)
        print(f"[{datetime.utcnow().isoformat()}] Reset response: {r.status_code} {r.text}")
    except Exception as e:
        print(f"Reset failed: {e}")


def main() -> None:
    tz = pytz.timezone("Asia/Kolkata")
    scheduler = BlockingScheduler(timezone=tz)
    # Daily at 12:00 PM IST
    scheduler.add_job(reset_job, "cron", hour=12, minute=0)
    print("Starting daily reset scheduler at 12:00 PM IST...")
    scheduler.start()


if __name__ == "__main__":
    main()


