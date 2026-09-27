import schedule
import time
from main import create_and_upload

def run_pipeline():
    return create_and_upload()


def main():
    print("Scheduler started. Uploading every 9 hours.")
    run_pipeline()
    schedule.every(9).hours.do(run_pipeline)
    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
