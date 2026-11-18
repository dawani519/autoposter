"""Background jobs: plan posts every PLAN_INTERVAL_MINUTES, publish due posts every minute."""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from autoposter.models import utcnow
from autoposter.planner import plan_day
from autoposter.poster import process_due_posts

log = logging.getLogger(__name__)


def _job(app, name, fn):
    def run():
        with app.app_context():
            status = app.extensions["scheduler_status"]
            try:
                status[name] = {"at": utcnow().isoformat() + "Z", "result": fn()}
            except Exception as exc:
                log.exception("Scheduled job %s failed", name)
                status[name] = {"at": utcnow().isoformat() + "Z", "error": str(exc)}

    return run


def start_scheduler(app):
    scheduler = BackgroundScheduler(timezone="UTC")
    common = {"max_instances": 1, "coalesce": True}
    scheduler.add_job(_job(app, "plan", plan_day), "interval",
                      minutes=app.config["PLAN_INTERVAL_MINUTES"], next_run_time=datetime.now(timezone.utc), id="plan", **common)
    scheduler.add_job(_job(app, "publish", process_due_posts), "interval", minutes=1, id="publish", **common)
    scheduler.start()
    app.extensions["scheduler_status"]["running"] = True
    log.info("Scheduler started: planning every %s minutes, publishing every minute",
             app.config["PLAN_INTERVAL_MINUTES"])
    return scheduler

