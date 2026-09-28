import schedule
import time
from main import create_and_upload
from config import SCHEDULE_INTERVAL_HOURS
from pipeline.server_control import ensure_server_started, ensure_server_stopped

def run_pipeline():
    if not ensure_server_started():
        print("[IndicF5] Error: Could not start IndicF5 server. Skipping scheduled run.")
        return None
    try:
        return create_and_upload()
    finally:
        ensure_server_stopped()


def main():
    print(f"Scheduler started. Uploading every {SCHEDULE_INTERVAL_HOURS} hours.")
    run_pipeline()
    schedule.every(SCHEDULE_INTERVAL_HOURS).hours.do(run_pipeline)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
