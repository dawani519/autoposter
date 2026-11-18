from cryptography.fernet import Fernet
import pytest
from sqlalchemy import select

from autoposter.app import create_app
from autoposter.models import Account, Post, PostStatus


def db_session(app):
    return app.extensions["db"].Session()


# ---------- security ----------

def test_dashboard_requires_login(app):
    anon = app.test_client()
    for path in ("/", "/api/stats", "/api/accounts", "/static/app.js"):
        resp = anon.get(path)
        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"].startswith("Basic")
    assert anon.get("/health").status_code == 200


def test_wrong_password_rejected(app):
    import base64
    bad = base64.b64encode(b"admin:nope").decode()
    assert app.test_client().get("/api/stats", headers={"Authorization": f"Basic {bad}"}).status_code == 401


def test_dashboard_served(client):
    resp = client.get("/")
    assert resp.status_code == 200 and b"AutoPoster" in resp.data
    assert client.get("/static/app.js").status_code == 200


@pytest.mark.parametrize("missing", ["ADMIN_PASSWORD", "ENCRYPTION_KEY"])
def test_startup_requires_secrets(tmp_path, missing):
    cfg = {"DATABASE_URL": f"sqlite:///{tmp_path}/x.db", "ADMIN_PASSWORD": "p",
           "ENCRYPTION_KEY": Fernet.generate_key().decode()}
    cfg[missing] = ""
    with pytest.raises(ValueError, match=missing):
        create_app(cfg)


def test_invalid_encryption_key(tmp_path):
    with pytest.raises(ValueError, match="not a valid key"):
        create_app({"DATABASE_URL": f"sqlite:///{tmp_path}/x.db", "ADMIN_PASSWORD": "p", "ENCRYPTION_KEY": "short"})


# ---------- accounts ----------

def test_account_secrets_encrypted_and_never_returned(app, client, make):
    created = make.account("x", api_key="my-key", access_secret="my-secret")
    listed = client.get("/api/accounts").json
    for payload in (created, listed[0]):
        assert "api_key" not in payload and "access_secret" not in payload
        assert "my-key" not in str(payload)
    with db_session(app) as s:
        row = s.scalars(select(Account)).one()
        assert row.api_key.startswith("enc:") and "my-key" not in row.api_key
        assert app.extensions["secrets"].decrypt(row.api_key) == "my-key"


def test_plaintext_tokens_from_old_version_get_encrypted(tmp_path):
    key = Fernet.generate_key().decode()
    cfg = {"DATABASE_URL": f"sqlite:///{tmp_path}/old.db", "ADMIN_PASSWORD": "p", "ENCRYPTION_KEY": key}
    app = create_app(cfg)
    with app.extensions["db"].Session.begin() as s:
        s.add(Account(platform="x", api_key="plain-key", api_secret="plain-secret",
                      access_token="plain-token", access_secret="plain-access"))
    app2 = create_app(cfg)  # restart
    with app2.extensions["db"].Session() as s:
        row = s.scalars(select(Account)).one()
        assert row.api_key.startswith("enc:")
        assert app2.extensions["secrets"].decrypt(row.access_secret) == "plain-access"


def test_x_account_needs_all_keys(client):
    resp = client.post("/api/accounts", json={"platform": "x", "api_key": "k"})
    assert resp.status_code == 400 and "api_secret" in resp.json["error"]


def test_linkedin_account_needs_only_token(client, make):
    account = make.account("linkedin", author_urn=None)
    assert account["platform"] == "linkedin" and account["platform_label"] == "LinkedIn"
    resp = client.post("/api/accounts", json={"platform": "linkedin"})
    assert resp.status_code == 400 and "access_token" in resp.json["error"]


def test_linkedin_author_urn_validated(client):
    resp = client.post("/api/accounts", json={"platform": "linkedin", "access_token": "t", "author_urn": "me"})
    assert resp.status_code == 400 and "urn:li:person" in resp.json["error"]


def test_unknown_platform_rejected(client):
    resp = client.post("/api/accounts", json={"platform": "facebook", "access_token": "t"})
    assert resp.status_code == 400 and "x, linkedin" in resp.json["error"]


def test_verify_account_fills_name(client, make):
    account = make.account("x", name="")
    resp = client.post(f"/api/accounts/{account['id']}/verify")
    assert resp.status_code == 200 and resp.json["account"]["name"] == "Verified Name"


def test_verify_account_reports_errors(app, client, make):
    from tests.conftest import fake_publish_error

    account = make.account("x")
    app.extensions["publishers"]["x"].verify = lambda creds: (_ for _ in ()).throw(fake_publish_error("bad keys"))
    resp = client.post(f"/api/accounts/{account['id']}/verify")
    assert resp.status_code == 422 and "bad keys" in resp.json["error"]


def test_delete_account_detaches_schedules(client, make):
    account, niche = make.account(), make.niche()
    sched = make.schedule(niche["id"], account["id"])
    assert client.delete(f"/api/accounts/{account['id']}").status_code == 204
    [row] = client.get("/api/schedules").json
    assert row["id"] == sched["id"] and row["account_id"] is None


# ---------- niches ----------

def test_niche_crud_and_hashtags(client, make):
    niche = make.niche("Fitness")
    assert client.put(f"/api/niches/{niche['id']}", json={"name": "Fitness tips"}).json["name"] == "Fitness tips"
    tag = client.post(f"/api/niches/{niche['id']}/hashtags", json={"tag": "#gym"})
    assert tag.status_code == 201 and tag.json["tag"] == "gym"
    assert client.post(f"/api/niches/{niche['id']}/hashtags", json={"tag": "two words"}).status_code == 400
    [listed] = client.get("/api/niches").json
    assert listed["hashtags"] == [{"id": tag.json["id"], "tag": "gym"}]
    assert client.delete(f"/api/hashtags/{tag.json['id']}").status_code == 204
    assert client.delete(f"/api/niches/{niche['id']}").status_code == 204
    assert client.get("/api/niches").json == []


def test_niche_name_required(client):
    assert client.post("/api/niches", json={"name": "  "}).status_code == 400


def test_missing_records_404(client):
    assert client.put("/api/niches/999", json={"name": "x"}).status_code == 404
    assert client.post("/api/posts/999/approve").status_code == 404


# ---------- schedules ----------

def test_schedule_validation(client, make):
    account, niche = make.account(), make.niche()
    bad = [
        {"niche_id": niche["id"], "posts_per_day": 3},  # no account
        {"niche_id": niche["id"], "account_id": account["id"], "posts_per_day": 0},
        {"niche_id": niche["id"], "account_id": account["id"], "posts_per_day": 100},
        {"niche_id": 999, "account_id": account["id"], "posts_per_day": 3},
    ]
    for payload in bad:
        assert client.post("/api/schedules", json=payload).status_code in (400, 404), payload
    sched = make.schedule(niche["id"], account["id"], posts_per_day=5, needs_approval=True)
    assert sched["needs_approval"] is True and sched["niche_name"] == "Tech"


# ---------- posts ----------

def test_manual_post_is_scheduled(client, make):
    account = make.account()
    resp = client.post("/api/posts", json={"account_id": account["id"], "content": "Hello world"})
    assert resp.status_code == 201
    assert resp.json["status"] == "scheduled" and resp.json["scheduled_time"] is not None
    assert resp.json["max_length"] == 280


def test_post_length_checked_per_platform(client, make):
    x, li = make.account("x"), make.account("linkedin")
    long_text = "a" * 1000
    assert client.post("/api/posts", json={"account_id": x["id"], "content": long_text}).status_code == 400
    assert client.post("/api/posts", json={"account_id": li["id"], "content": long_text}).status_code == 201
    assert client.post("/api/posts", json={"account_id": li["id"], "content": "a" * 3001}).status_code == 400


def test_scheduled_time_parsed_as_utc(client, make):
    account = make.account()
    resp = client.post("/api/posts", json={"account_id": account["id"], "content": "Hi",
                                           "scheduled_time": "2030-01-01T09:00:00+01:00"})
    assert resp.json["scheduled_time"] == "2030-01-01T08:00:00Z"
    bad = client.post("/api/posts", json={"account_id": account["id"], "content": "Hi", "scheduled_time": "soon"})
    assert bad.status_code == 400


def _pending_post(app, account_id):
    with app.extensions["db"].Session.begin() as s:
        post = Post(account_id=account_id, content="Draft", status=PostStatus.PENDING_APPROVAL, scheduled_time=None)
        s.add(post)
        s.flush()
        return post.id


def test_approve_reject_retry(app, client, make):
    account = make.account()
    post_id = _pending_post(app, account["id"])

    approved = client.post(f"/api/posts/{post_id}/approve").json
    assert approved["status"] == "scheduled" and approved["scheduled_time"]  # no time -> now
    assert client.post(f"/api/posts/{post_id}/approve").status_code == 409  # already approved
    assert client.post(f"/api/posts/{post_id}/retry").status_code == 409  # not failed

    assert client.post(f"/api/posts/{post_id}/reject").json["status"] == "rejected"
    assert client.put(f"/api/posts/{post_id}", json={"content": "x"}).status_code == 409

    with app.extensions["db"].Session.begin() as s:
        s.get(Post, post_id).status = PostStatus.FAILED
        s.get(Post, post_id).last_error = "boom"
    retried = client.post(f"/api/posts/{post_id}/retry").json
    assert retried["status"] == "scheduled" and retried["last_error"] is None and retried["attempts"] == 0


def test_edit_pending_post(app, client, make):
    account = make.account()
    post_id = _pending_post(app, account["id"])
    edited = client.put(f"/api/posts/{post_id}", json={"content": "Better words"}).json
    assert edited["content"] == "Better words" and edited["status"] == "pending_approval"
    assert client.put(f"/api/posts/{post_id}", json={"content": "a" * 281}).status_code == 400


def test_filter_posts_by_status(app, client, make):
    account = make.account()
    _pending_post(app, account["id"])
    client.post("/api/posts", json={"account_id": account["id"], "content": "Now"})
    assert len(client.get("/api/posts").json) == 2
    assert [p["status"] for p in client.get("/api/posts?status=pending_approval").json] == ["pending_approval"]
    assert client.get("/api/posts?status=nope").status_code == 400


def test_stats(client, make):
    account = make.account()
    client.post("/api/posts", json={"account_id": account["id"], "content": "Now"})
    stats = client.get("/api/stats").json
    assert stats["accounts"] == 1 and stats["posts"]["scheduled"] == 1
    assert stats["scheduler"]["running"] is False and stats["ai_configured"] is True
