"""Run only the background scheduler (use with RUN_SCHEDULER=false on the web process).

    python worker.py
"""
import time

from autoposter.app import create_app
from autoposter.scheduler import start_scheduler

if __name__ == "__main__":
    app = create_app()
    start_scheduler(app)
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        pass
