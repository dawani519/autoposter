"""Daily planning: write each schedule's posts for today and spread them across the posting window.

Safe to run as often as you like: it only fills the slots that are still missing, so a run
that failed halfway (e.g. the AI was down) is completed by the next one.
"""
import logging
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import current_app
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from autoposter.ai import GenerationError
from autoposter.db import get_db
from autoposter.models import Account, Niche, Post, PostStatus, Schedule, utcnow

log = logging.getLogger(__name__)

RECENT_POSTS_FOR_CONTEXT = 5


def _parse_hhmm(value):
    return datetime.strptime(value, "%H:%M").time()


def day_bounds_utc(local_day, tz):
    """[start, end) of a local calendar day, as naive UTC."""
    start = datetime.combine(local_day, time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return _to_naive_utc(start), _to_naive_utc(end)


def _to_naive_utc(dt):
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def time_slots(posts_per_day, local_day, cfg):
    """Evenly spaced posting times (naive UTC) within the posting window on local_day."""
    if posts_per_day <= 0:
        return []
    tz = ZoneInfo(cfg["TIMEZONE"])
    start = datetime.combine(local_day, _parse_hhmm(cfg["POSTING_WINDOW_START"]), tzinfo=tz)
    end = datetime.combine(local_day, _parse_hhmm(cfg["POSTING_WINDOW_END"]), tzinfo=tz)
    if end <= start:
        raise ValueError("POSTING_WINDOW_END must be after POSTING_WINDOW_START")
    interval = (end - start) / posts_per_day
    return [_to_naive_utc(start + interval * i) for i in range(posts_per_day)]


def plan_day(now=None):
    """Write the missing posts for today. Returns a summary dict."""
    cfg = current_app.config
    generator = current_app.extensions["generator"]
    db = get_db()
    now = now or utcnow()
    tz = ZoneInfo(cfg["TIMEZONE"])
    local_day = now.replace(tzinfo=timezone.utc).astimezone(tz).date()
    day_start, day_end = day_bounds_utc(local_day, tz)

    summary = {"created": 0, "skipped_schedules": [], "errors": []}
    with db.Session() as s:
        schedules = s.scalars(
            select(Schedule).options(
                selectinload(Schedule.niche).selectinload(Niche.hashtags), selectinload(Schedule.account)
            )
        ).all()

    for sched in schedules:
        if sched.niche is None:  # possible in databases from the original version
            summary["skipped_schedules"].append({"schedule_id": sched.id, "reason": "no niche selected"})
            continue
        if sched.account is None:
            summary["skipped_schedules"].append({"schedule_id": sched.id, "reason": "no account selected"})
            continue
        account: Account = sched.account
        with db.Session() as s:
            planned = s.scalar(
                select(func.count(Post.id)).where(
                    Post.niche_id == sched.niche_id,
                    Post.account_id == account.id,
                    Post.scheduled_time >= day_start,
                    Post.scheduled_time < day_end,
                )
            )
        slots = [t for t in time_slots(sched.posts_per_day, local_day, cfg)[planned:] if t > now]
        for slot in slots:
            with db.Session() as s:
                recent = s.scalars(
                    select(Post.content)
                    .where(Post.niche_id == sched.niche_id, Post.account_id == account.id)
                    .order_by(Post.created_at.desc())
                    .limit(RECENT_POSTS_FOR_CONTEXT)
                ).all()
            try:
                content = generator.generate(sched.niche, account.platform, recent)
            except GenerationError as exc:
                # Don't post filler text; the next run tries again.
                log.warning("Schedule %s: couldn't write a post: %s", sched.id, exc)
                summary["errors"].append({"schedule_id": sched.id, "error": str(exc)})
                break
            status = PostStatus.PENDING_APPROVAL if sched.needs_approval else PostStatus.SCHEDULED
            with db.Session.begin() as s:
                s.add(Post(niche_id=sched.niche_id, account_id=account.id, content=content,
                           scheduled_time=slot, status=status))
            summary["created"] += 1
    log.info("Planning done: %s", summary)
    return summary
