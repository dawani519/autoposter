"""Publishing posts that are due."""
import logging
from datetime import timedelta

from flask import current_app
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from autoposter.ai import max_length
from autoposter.db import get_db
from autoposter.models import Post, PostStatus, utcnow

log = logging.getLogger(__name__)

BATCH_SIZE = 50
CRED_FIELDS = ("api_key", "api_secret", "access_token", "access_secret")


def account_credentials(account):
    box = current_app.extensions["secrets"]
    creds = {field: box.decrypt(getattr(account, field)) for field in CRED_FIELDS}
    creds["author_urn"] = account.author_urn
    return creds


def _claim(post_id):
    """Atomically take a scheduled post, so two workers can never publish it twice."""
    with get_db().Session.begin() as s:
        result = s.execute(
            update(Post).where(Post.id == post_id, Post.status == PostStatus.SCHEDULED)
            .values(status=PostStatus.POSTING)
        )
        return result.rowcount == 1


def _finish(post_id, **values):
    with get_db().Session.begin() as s:
        s.execute(update(Post).where(Post.id == post_id).values(**values))


def process_due_posts(now=None):
    """Publish every scheduled post whose time has come. Returns a summary dict."""
    cfg = current_app.config
    publishers = current_app.extensions["publishers"]
    now = now or utcnow()
    summary = {"posted": 0, "failed": 0, "retrying": 0}

    with get_db().Session() as s:
        due_ids = s.scalars(
            select(Post.id).where(Post.status == PostStatus.SCHEDULED, Post.scheduled_time <= now)
            .order_by(Post.scheduled_time).limit(BATCH_SIZE)
        ).all()

    for post_id in due_ids:
        if not _claim(post_id):
            continue
        with get_db().Session() as s:
            post = s.scalars(select(Post).options(selectinload(Post.account)).where(Post.id == post_id)).one()

        error = _check(post)
        if error:
            _finish(post_id, status=PostStatus.FAILED, last_error=error, attempts=post.attempts + 1)
            summary["failed"] += 1
            continue

        publisher = publishers[post.account.platform]
        try:
            external_id = publisher.publish(account_credentials(post.account), post.content)
        except Exception as exc:  # PublishError, or a bug: never leave a post stuck in "posting"
            attempts = post.attempts + 1
            retryable = getattr(exc, "retryable", False)
            if retryable and attempts < cfg["MAX_POST_ATTEMPTS"]:
                retry_at = now + timedelta(minutes=cfg["RATE_LIMIT_RETRY_MINUTES"])
                _finish(post_id, status=PostStatus.SCHEDULED, scheduled_time=retry_at,
                        attempts=attempts, last_error=str(exc))
                log.warning("Post %s: %s; retrying at %s", post_id, exc, retry_at)
                summary["retrying"] += 1
            else:
                if not hasattr(exc, "retryable"):
                    log.exception("Unexpected error publishing post %s", post_id)
                _finish(post_id, status=PostStatus.FAILED, attempts=attempts, last_error=str(exc))
                log.warning("Post %s failed: %s", post_id, exc)
                summary["failed"] += 1
            continue

        _finish(post_id, status=PostStatus.POSTED, posted_at=utcnow(), external_id=external_id,
                attempts=post.attempts + 1, last_error=None)
        log.info("Post %s published to %s (%s)", post_id, post.account.platform, external_id)
        summary["posted"] += 1
    return summary


def _check(post):
    if post.account is None:
        return "The post's account was deleted"
    if post.account.platform not in current_app.extensions["publishers"]:
        return f"Posting to {post.account.platform!r} isn't supported"
    limit = max_length(post.account.platform)
    if len(post.content) > limit:
        return f"Post is {len(post.content)} characters; {post.account.platform} allows {limit}"
    if not post.content.strip():
        return "Post is empty"
    return None
