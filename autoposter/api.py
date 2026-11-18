"""JSON API used by the dashboard."""
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from autoposter.ai import max_length
from autoposter.db import get_db
from autoposter.models import Account, Hashtag, Niche, Post, PostStatus, Schedule, utcnow
from autoposter.planner import plan_day
from autoposter.poster import account_credentials, process_due_posts
from autoposter.publishers import PLATFORMS, PublishError, post_url

api = Blueprint("api", __name__, url_prefix="/api")

MAX_POSTS_PER_DAY = 48


class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@api.errorhandler(ApiError)
def _api_error(exc):
    return jsonify({"error": str(exc)}), exc.status


# ---------- helpers ----------

def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Expected a JSON object")
    return data


def text_field(data, name, required=True, max_len=None):
    value = data.get(name)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise ApiError(f"{name} is required")
        return None
    if not isinstance(value, str):
        raise ApiError(f"{name} must be text")
    value = value.strip()
    if max_len and len(value) > max_len:
        raise ApiError(f"{name} must be at most {max_len} characters")
    return value


def int_field(data, name, required=True, minimum=None, maximum=None):
    value = data.get(name)
    if value in (None, ""):
        if required:
            raise ApiError(f"{name} is required")
        return None
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ApiError(f"{name} must be a whole number") from None
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        raise ApiError(f"{name} must be between {minimum} and {maximum}")
    return value


def time_field(data, name):
    """ISO 8601 time from the browser -> naive UTC. Missing -> None."""
    value = data.get(name)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        raise ApiError(f"{name} must be an ISO date and time") from None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso(dt):
    return dt.isoformat() + "Z" if dt else None


def get_or_404(s, model, obj_id):
    obj = s.get(model, obj_id)
    if obj is None:
        raise ApiError(f"{model.__name__} {obj_id} not found", 404)
    return obj


# ---------- serializers (secrets are never returned) ----------

def niche_json(n):
    return {"id": n.id, "name": n.name, "description": n.description, "primary_statement": n.primary_statement,
            "hashtags": [{"id": h.id, "tag": h.tag} for h in n.hashtags], "created_at": iso(n.created_at)}


def account_json(a):
    return {"id": a.id, "platform": a.platform, "platform_label": PLATFORMS.get(a.platform, a.platform),
            "name": a.name, "author_urn": a.author_urn, "created_at": iso(a.created_at)}


def schedule_json(sc):
    return {"id": sc.id, "niche_id": sc.niche_id, "niche_name": sc.niche.name if sc.niche else None,
            "account_id": sc.account_id, "account_name": _account_label(sc.account),
            "posts_per_day": sc.posts_per_day, "needs_approval": bool(sc.needs_approval),
            "created_at": iso(sc.created_at)}


def post_json(p):
    platform = p.account.platform if p.account else None
    return {"id": p.id, "niche_id": p.niche_id, "niche_name": p.niche.name if p.niche else None,
            "account_id": p.account_id, "account_name": _account_label(p.account), "platform": platform,
            "content": p.content, "status": p.status, "scheduled_time": iso(p.scheduled_time),
            "posted_at": iso(p.posted_at), "attempts": p.attempts, "last_error": p.last_error,
            "url": post_url(platform, p.external_id), "max_length": max_length(platform) if platform in PLATFORMS else None,
            "created_at": iso(p.created_at)}


def _account_label(a):
    if a is None:
        return None
    return f"{PLATFORMS.get(a.platform, a.platform)}: {a.name or a.id}"


# ---------- stats & jobs ----------

@api.get("/stats")
def stats():
    with get_db().Session() as s:
        by_status = dict(s.execute(select(Post.status, func.count(Post.id)).group_by(Post.status)).all())
        result = {
            "niches": s.scalar(select(func.count(Niche.id))),
            "accounts": s.scalar(select(func.count(Account.id))),
            "schedules": s.scalar(select(func.count(Schedule.id))),
            "posts": {status: by_status.get(status, 0) for status in PostStatus.ALL},
        }
    result["scheduler"] = current_app.extensions["scheduler_status"]
    result["ai_configured"] = bool(current_app.config["AI_API_KEY"])
    return jsonify(result)


@api.post("/run/plan")
def run_plan():
    return jsonify(plan_day())


@api.post("/run/publish")
def run_publish():
    return jsonify(process_due_posts())


# ---------- niches & hashtags ----------

@api.get("/niches")
def list_niches():
    with get_db().Session() as s:
        niches = s.scalars(select(Niche).options(selectinload(Niche.hashtags)).order_by(Niche.id)).all()
        return jsonify([niche_json(n) for n in niches])


def _niche_fields(data):
    return {"name": text_field(data, "name", max_len=255),
            "description": text_field(data, "description", required=False),
            "primary_statement": text_field(data, "primary_statement", required=False)}


@api.post("/niches")
def create_niche():
    fields = _niche_fields(body())
    with get_db().Session.begin() as s:
        niche = Niche(**fields)
        s.add(niche)
        s.flush()
        return jsonify(niche_json(niche)), 201


@api.put("/niches/<int:niche_id>")
def update_niche(niche_id):
    fields = _niche_fields(body())
    with get_db().Session.begin() as s:
        niche = get_or_404(s, Niche, niche_id)
        for k, v in fields.items():
            setattr(niche, k, v)
        return jsonify(niche_json(niche))


@api.delete("/niches/<int:niche_id>")
def delete_niche(niche_id):
    with get_db().Session.begin() as s:
        niche = get_or_404(s, Niche, niche_id)
        if s.scalar(select(func.count(Post.id)).where(Post.niche_id == niche_id, Post.status == PostStatus.POSTING)):
            raise ApiError("A post for this niche is being published right now; try again in a minute", 409)
        for model in (Post, Schedule):
            for row in s.scalars(select(model).where(model.niche_id == niche_id)):
                s.delete(row)
        s.delete(niche)
    return "", 204


@api.post("/niches/<int:niche_id>/hashtags")
def add_hashtag(niche_id):
    tag = text_field(body(), "tag", max_len=100).lstrip("#")
    if not tag or not tag.replace("_", "").isalnum():
        raise ApiError("A hashtag can only contain letters, numbers and underscores")
    with get_db().Session.begin() as s:
        get_or_404(s, Niche, niche_id)
        hashtag = Hashtag(niche_id=niche_id, tag=tag)
        s.add(hashtag)
        s.flush()
        return jsonify({"id": hashtag.id, "tag": hashtag.tag}), 201


@api.delete("/hashtags/<int:hashtag_id>")
def delete_hashtag(hashtag_id):
    with get_db().Session.begin() as s:
        s.delete(get_or_404(s, Hashtag, hashtag_id))
    return "", 204


# ---------- accounts ----------

@api.get("/accounts")
def list_accounts():
    with get_db().Session() as s:
        return jsonify([account_json(a) for a in s.scalars(select(Account).order_by(Account.id))])


@api.get("/platforms")
def list_platforms():
    return jsonify([{"id": k, "label": v, "max_length": max_length(k)} for k, v in PLATFORMS.items()])


@api.post("/accounts")
def create_account():
    data = body()
    platform = text_field(data, "platform")
    if platform not in PLATFORMS:
        raise ApiError(f"platform must be one of: {', '.join(PLATFORMS)}")
    publisher = current_app.extensions["publishers"][platform]
    secrets = {field: text_field(data, field, required=field in publisher.required)
               for field in ("api_key", "api_secret", "access_token", "access_secret")}
    author_urn = text_field(data, "author_urn", required=False, max_len=255)
    if author_urn and not author_urn.startswith(("urn:li:person:", "urn:li:organization:")):
        raise ApiError("author_urn must look like urn:li:person:... or urn:li:organization:...")
    box = current_app.extensions["secrets"]
    with get_db().Session.begin() as s:
        account = Account(
            platform=platform,
            name=text_field(data, "name", required=False, max_len=255),
            author_urn=author_urn,
            **{k: box.encrypt(v) if v else None for k, v in secrets.items()},
        )
        s.add(account)
        s.flush()
        return jsonify(account_json(account)), 201


@api.post("/accounts/<int:account_id>/verify")
def verify_account(account_id):
    """Check the stored credentials with the platform (and fill in LinkedIn's author URN)."""
    with get_db().Session() as s:
        account = get_or_404(s, Account, account_id)
    publisher = current_app.extensions["publishers"].get(account.platform)
    if publisher is None:
        raise ApiError(f"Posting to {account.platform!r} isn't supported")
    try:
        display_name, updates = publisher.verify(account_credentials(account))
    except PublishError as exc:
        raise ApiError(str(exc), 422) from None
    with get_db().Session.begin() as s:
        account = s.get(Account, account_id)
        for k, v in updates.items():
            setattr(account, k, v)
        if not account.name:
            account.name = display_name
        return jsonify({"ok": True, "display_name": display_name, "account": account_json(account)})


@api.delete("/accounts/<int:account_id>")
def delete_account(account_id):
    with get_db().Session.begin() as s:
        account = get_or_404(s, Account, account_id)
        if s.scalar(select(func.count(Post.id)).where(Post.account_id == account_id,
                                                      Post.status == PostStatus.POSTING)):
            raise ApiError("A post for this account is being published right now; try again in a minute", 409)
        for post in s.scalars(select(Post).where(Post.account_id == account_id)):
            s.delete(post)
        for sched in s.scalars(select(Schedule).where(Schedule.account_id == account_id)):
            sched.account_id = None
        s.delete(account)
    return "", 204


# ---------- schedules ----------

@api.get("/schedules")
def list_schedules():
    with get_db().Session() as s:
        rows = s.scalars(select(Schedule).options(selectinload(Schedule.niche), selectinload(Schedule.account))
                         .order_by(Schedule.id)).all()
        return jsonify([schedule_json(r) for r in rows])


def _schedule_fields(s, data):
    niche_id = int_field(data, "niche_id")
    account_id = int_field(data, "account_id")
    get_or_404(s, Niche, niche_id)
    get_or_404(s, Account, account_id)
    return {"niche_id": niche_id, "account_id": account_id,
            "posts_per_day": int_field(data, "posts_per_day", minimum=1, maximum=MAX_POSTS_PER_DAY),
            "needs_approval": 1 if data.get("needs_approval", True) in (True, 1, "1", "true") else 0}


@api.post("/schedules")
def create_schedule():
    data = body()
    with get_db().Session.begin() as s:
        sched = Schedule(**_schedule_fields(s, data))
        s.add(sched)
        s.flush()
        s.refresh(sched)
        return jsonify(schedule_json(sched)), 201


@api.put("/schedules/<int:schedule_id>")
def update_schedule(schedule_id):
    data = body()
    with get_db().Session.begin() as s:
        sched = get_or_404(s, Schedule, schedule_id)
        for k, v in _schedule_fields(s, data).items():
            setattr(sched, k, v)
        s.flush()
        s.refresh(sched)
        return jsonify(schedule_json(sched))


@api.delete("/schedules/<int:schedule_id>")
def delete_schedule(schedule_id):
    with get_db().Session.begin() as s:
        s.delete(get_or_404(s, Schedule, schedule_id))
    return "", 204


# ---------- posts ----------

def _post_query():
    return select(Post).options(selectinload(Post.niche), selectinload(Post.account))


@api.get("/posts")
def list_posts():
    status = request.args.get("status")
    query = _post_query().order_by(Post.scheduled_time.desc().nulls_last(), Post.id.desc()).limit(500)
    if status:
        if status not in PostStatus.ALL:
            raise ApiError(f"status must be one of: {', '.join(PostStatus.ALL)}")
        query = query.where(Post.status == status)
    with get_db().Session() as s:
        return jsonify([post_json(p) for p in s.scalars(query)])


def _load_post(s, post_id):
    post = s.scalars(_post_query().where(Post.id == post_id)).first()
    if post is None:
        raise ApiError(f"Post {post_id} not found", 404)
    return post


def _check_length(content, account):
    limit = max_length(account.platform)
    if len(content) > limit:
        raise ApiError(f"Post is {len(content)} characters; {PLATFORMS[account.platform]} allows {limit}")


@api.post("/posts")
def create_post():
    """A hand-written post. It's scheduled straight away (no approval needed)."""
    data = body()
    content = text_field(data, "content")
    with get_db().Session.begin() as s:
        account = get_or_404(s, Account, int_field(data, "account_id"))
        niche_id = int_field(data, "niche_id", required=False)
        if niche_id is not None:
            get_or_404(s, Niche, niche_id)
        _check_length(content, account)
        post = Post(niche_id=niche_id, account_id=account.id, content=content,
                    scheduled_time=time_field(data, "scheduled_time") or utcnow(), status=PostStatus.SCHEDULED)
        s.add(post)
        s.flush()
        return jsonify(post_json(_load_post(s, post.id))), 201


EDITABLE = (PostStatus.PENDING_APPROVAL, PostStatus.SCHEDULED, PostStatus.FAILED)


@api.put("/posts/<int:post_id>")
def update_post(post_id):
    data = body()
    with get_db().Session.begin() as s:
        post = _load_post(s, post_id)
        if post.status not in EDITABLE:
            raise ApiError(f"A {post.status} post can't be edited", 409)
        if "content" in data:
            post.content = text_field(data, "content")
            if post.account:
                _check_length(post.content, post.account)
        if "scheduled_time" in data:
            post.scheduled_time = time_field(data, "scheduled_time")
        return jsonify(post_json(post))


def _transition(post_id, allowed_from, **changes):
    with get_db().Session.begin() as s:
        post = _load_post(s, post_id)
        if post.status not in allowed_from:
            raise ApiError(f"A {post.status} post can't do that", 409)
        for k, v in changes.items():
            setattr(post, k, v)
        if post.status == PostStatus.SCHEDULED and post.scheduled_time is None:
            post.scheduled_time = utcnow()
        return jsonify(post_json(post))


@api.post("/posts/<int:post_id>/approve")
def approve_post(post_id):
    return _transition(post_id, (PostStatus.PENDING_APPROVAL,), status=PostStatus.SCHEDULED)


@api.post("/posts/<int:post_id>/reject")
def reject_post(post_id):
    return _transition(post_id, (PostStatus.PENDING_APPROVAL, PostStatus.SCHEDULED), status=PostStatus.REJECTED)


@api.post("/posts/<int:post_id>/retry")
def retry_post(post_id):
    return _transition(post_id, (PostStatus.FAILED,), status=PostStatus.SCHEDULED, scheduled_time=utcnow(),
                       attempts=0, last_error=None)


@api.delete("/posts/<int:post_id>")
def delete_post(post_id):
    with get_db().Session.begin() as s:
        post = _load_post(s, post_id)
        if post.status == PostStatus.POSTING:
            raise ApiError("This post is being published right now", 409)
        s.delete(post)
    return "", 204
