"""Production entry point: gunicorn -w 1 --threads 4 -b 0.0.0.0:$PORT wsgi:app

Starts the scheduler in the web process when RUN_SCHEDULER is true. With more than one
gunicorn worker, set RUN_SCHEDULER=false and run `python worker.py` separately.
"""
from autoposter.app import create_app
from autoposter.scheduler import start_scheduler

app = create_app()
if app.config["RUN_SCHEDULER"]:
    start_scheduler(app)
