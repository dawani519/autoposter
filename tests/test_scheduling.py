from datetime import datetime, timedelta

from sqlalchemy import select, update

from autoposter.models import Post, PostStatus
from autoposter.planner import plan_day, time_slots
from autoposter.poster import process_due_posts
from tests.conftest import fake_publish_error

# 2030-01-01 05:00 UTC = 06:00 in Lagos (UTC+1), before the 07:00-23:00 window.
EARLY = datetime(2030, 1, 1, 5, 0)


def posts(app):
    with app.extensions["db"].Session() as s:
        return s.scalars(select(Post).order_by(Post.scheduled_time)).all()


def plan(app, now):
    with app.app_context():
        return plan_day(now=now)


def publish(app, now):
    with app.app_context():
        return process_due_posts(now=now)


# ---------- time slots ----------

def test_slots_spread_across_window_in_local_time(app):
    slots = time_slots(4, EARLY.date(), app.config)
    # 07:00, 11:00, 15:00, 19:00 Lagos == 06:00, 10:00, 14:00, 18:00 UTC
    assert [s.hour for s in slots] == [6, 10, 14, 18]
    assert time_slots(0, EARLY.date(), app.config) == []


# ---------- planning ----------

def test_plan_writes_posts_for_each_schedule(app, make):
    x, li = make.account("x"), make.account("linkedin")
    tech, food = make.niche("Tech"), make.niche("Food")
    make.schedule(tech["id"], x["id"], posts_per_day=4)
    make.schedule(food["id"], li["id"], posts_per_day=2, needs_approval=True)

    summary = plan(app, EARLY)
    assert summary["created"] == 6 and summary["errors"] == []
    rows = posts(app)
    assert {(p.account_id, p.status) for p in rows} == {
        (x["id"], PostStatus.SCHEDULED), (li["id"], PostStatus.PENDING_APPROVAL)}
    platforms = [c["platform"] for c in app.extensions["generator"].calls]
    assert platforms.count("x") == 4 and platforms.count("linkedin") == 2


def test_plan_is_idempotent(app, make):
    account, niche = make.account(), make.niche()
    make.schedule(niche["id"], account["id"], posts_per_day=3)
    plan(app, EARLY)
    assert plan(app, EARLY + timedelta(minutes=30))["created"] == 0
    assert len(posts(app)) == 3


def test_plan_skips_slots_already_passed(app, make):
    account, niche = make.account(), make.niche()
    make.schedule(niche["id"], account["id"], posts_per_day=4)
    # 15:30 UTC = 16:30 Lagos: only the 19:00 Lagos slot is still ahead.
    summary = plan(app, datetime(2030, 1, 1, 15, 30))
    assert summary["created"] == 1
    assert posts(app)[0].scheduled_time == datetime(2030, 1, 1, 18, 0)


def test_ai_failure_creates_nothing_and_retries_later(app, make):
    account, niche = make.account(), make.niche()
    make.schedule(niche["id"], account["id"], posts_per_day=3)
    app.extensions["generator"].fail = "AI is down"
    summary = plan(app, EARLY)
    assert summary["created"] == 0 and summary["errors"][0]["error"] == "AI is down"
    assert posts(app) == []  # no placeholder posts

    app.extensions["generator"].fail = None
    assert plan(app, EARLY + timedelta(minutes=30))["created"] == 3


def test_schedule_without_account_skipped(app, client, make):
    account, niche = make.account(), make.niche()
    make.schedule(niche["id"], account["id"])
    client.delete(f"/api/accounts/{account['id']}")
    summary = plan(app, EARLY)
    assert summary["created"] == 0 and summary["skipped_schedules"][0]["reason"] == "no account selected"


def test_recent_posts_passed_to_ai(app, make):
    account, niche = make.account(), make.niche()
    make.schedule(niche["id"], account["id"], posts_per_day=2)
    plan(app, EARLY)
    calls = app.extensions["generator"].calls
    assert calls[0]["recent"] == [] and calls[1]["recent"] == [posts(app)[0].content]


# ---------- publishing ----------

def scheduled_post(app, account_id, when, content="Hello", status=PostStatus.SCHEDULED):
    with app.extensions["db"].Session.begin() as s:
        post = Post(account_id=account_id, content=content, scheduled_time=when, status=status)
        s.add(post)
        s.flush()
        return post.id


def get_post(app, post_id):
    with app.extensions["db"].Session() as s:
        return s.get(Post, post_id)


def test_publishes_due_posts_only(app, make):
    account = make.account("x", api_key="real-key")
    due = scheduled_post(app, account["id"], EARLY)
    later = scheduled_post(app, account["id"], EARLY + timedelta(hours=1))
    pending = scheduled_post(app, account["id"], EARLY, status=PostStatus.PENDING_APPROVAL)

    assert publish(app, EARLY) == {"posted": 1, "failed": 0, "retrying": 0}
    published = app.extensions["publishers"]["x"].published
    assert published[0]["text"] == "Hello" and published[0]["creds"]["api_key"] == "real-key"  # decrypted
    p = get_post(app, due)
    assert p.status == PostStatus.POSTED and p.external_id == "x-1" and p.posted_at
    assert get_post(app, later).status == PostStatus.SCHEDULED
    assert get_post(app, pending).status == PostStatus.PENDING_APPROVAL


def test_each_post_goes_to_its_own_account(app, make):
    x, li = make.account("x"), make.account("linkedin")
    scheduled_post(app, x["id"], EARLY, "for x")
    scheduled_post(app, li["id"], EARLY, "for linkedin")
    publish(app, EARLY)
    assert [p["text"] for p in app.extensions["publishers"]["x"].published] == ["for x"]
    li_published = app.extensions["publishers"]["linkedin"].published
    assert [p["text"] for p in li_published] == ["for linkedin"]
    assert li_published[0]["creds"]["author_urn"] == "urn:li:person:abc123"


def test_post_claimed_elsewhere_is_not_published_twice(app, make):
    account = make.account()
    post_id = scheduled_post(app, account["id"], EARLY)
    with app.extensions["db"].Session.begin() as s:  # another worker grabbed it
        s.execute(update(Post).where(Post.id == post_id).values(status=PostStatus.POSTING))
    assert publish(app, EARLY)["posted"] == 0
    assert app.extensions["publishers"]["x"].published == []


def test_rate_limit_retries_then_fails(app, make):
    account = make.account()
    post_id = scheduled_post(app, account["id"], EARLY)
    app.extensions["publishers"]["x"].error = fake_publish_error("rate limited", retryable=True)

    now = EARLY
    for attempt in (1, 2):
        assert publish(app, now)["retrying"] == 1
        p = get_post(app, post_id)
        assert p.status == PostStatus.SCHEDULED and p.attempts == attempt
        assert p.scheduled_time == now + timedelta(minutes=15)
        assert publish(app, now)["retrying"] == 0  # not due again yet
        now = p.scheduled_time

    assert publish(app, now)["failed"] == 1
    p = get_post(app, post_id)
    assert p.status == PostStatus.FAILED and p.attempts == 3 and "rate limited" in p.last_error


def test_permanent_error_fails_immediately(app, make):
    account = make.account()
    post_id = scheduled_post(app, account["id"], EARLY)
    app.extensions["publishers"]["x"].error = fake_publish_error("duplicate content")
    assert publish(app, EARLY)["failed"] == 1
    assert get_post(app, post_id).last_error == "duplicate content"


def test_unexpected_error_never_leaves_post_stuck(app, make):
    account = make.account()
    post_id = scheduled_post(app, account["id"], EARLY)
    app.extensions["publishers"]["x"].error = RuntimeError("bug")
    publish(app, EARLY)
    assert get_post(app, post_id).status == PostStatus.FAILED


def test_too_long_post_fails_without_calling_platform(app, make):
    account = make.account()
    post_id = scheduled_post(app, account["id"], EARLY, content="a" * 300)
    publish(app, EARLY)
    p = get_post(app, post_id)
    assert p.status == PostStatus.FAILED and "allows 280" in p.last_error
    assert app.extensions["publishers"]["x"].published == []


def test_full_flow_with_approval(app, client, make):
    account, niche = make.account(), make.niche()
    make.schedule(niche["id"], account["id"], posts_per_day=1, needs_approval=True)
    plan(app, EARLY)
    [post] = client.get("/api/posts?status=pending_approval").json
    publish(app, EARLY + timedelta(hours=2))
    assert app.extensions["publishers"]["x"].published == []  # not approved yet

    client.post(f"/api/posts/{post['id']}/approve")
    publish(app, EARLY + timedelta(hours=2))
    assert len(app.extensions["publishers"]["x"].published) == 1
    assert client.get("/api/posts?status=posted").json[0]["url"] == "https://x.com/i/web/status/x-1"
