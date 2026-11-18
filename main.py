"""Run AutoPoster: the dashboard plus (unless RUN_SCHEDULER=false) the background scheduler.

    python main.py
"""
from autoposter.app import create_app
from autoposter.scheduler import start_scheduler

app = create_app()

if __name__ == "__main__":
    if app.config["RUN_SCHEDULER"]:
        start_scheduler(app)
    app.run(host="0.0.0.0", port=app.config["PORT"], debug=False, threaded=True)
