import base64
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from autoposter.ai import GenerationError
from autoposter.app import create_app
from autoposter.publishers import PublishError

PASSWORD = "test-password"


class FakeGenerator:
    """Writes predictable posts; can be told to fail."""

    def __init__(self):
        self.calls = []
        self.fail = None

    def generate(self, niche, platform, recent_posts=()):
        self.calls.append({"niche": niche.name, "platform": platform, "recent": list(recent_posts)})
        if self.fail:
            raise GenerationError(self.fail)
        return f"{platform} post #{len(self.calls)} about {niche.name}"


class FakePublisher:
    def __init__(self, platform, required):
        self.platform = platform
        self.required = required
        self.published = []
        self.error = None  # PublishError or other exception to raise

    def publish(self, creds, text):
        if self.error:
            raise self.error
        self.published.append({"creds": creds, "text": text})
        return f"{self.platform}-{len(self.published)}"

    def verify(self, creds):
        return "Verified Name", {}


@pytest.fixture
def app(tmp_path):
    app = create_app({
        "DATABASE_URL": f"sqlite:///{tmp_path}/test.db",
        "ADMIN_USERNAME": "admin",
        "ADMIN_PASSWORD": PASSWORD,
        "ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "AI_API_KEY": "test-ai-key",
        "TIMEZONE": "Africa/Lagos",
        "POSTING_WINDOW_START": "07:00",
        "POSTING_WINDOW_END": "23:00",
        "MAX_POST_ATTEMPTS": 3,
        "RATE_LIMIT_RETRY_MINUTES": 15,
        "RUN_SCHEDULER": False,
    })
    app.extensions["generator"] = FakeGenerator()
    app.extensions["publishers"] = {
        "x": FakePublisher("x", ("api_key", "api_secret", "access_token", "access_secret")),
        "linkedin": FakePublisher("linkedin", ("access_token",)),
    }
    return app


@pytest.fixture
def client(app):
    token = base64.b64encode(f"admin:{PASSWORD}".encode()).decode()
    c = app.test_client()
    c.environ_base["HTTP_AUTHORIZATION"] = f"Basic {token}"
    return c


@pytest.fixture
def make(client):
    """Helpers that create records through the API."""

    def account(platform="x", **extra):
        payload = {"platform": platform, "name": f"{platform} account"}
        if platform == "x":
            payload.update(api_key="k", api_secret="ks", access_token="t", access_secret="ts")
        else:
            payload.update(access_token="li-token", author_urn="urn:li:person:abc123")
        payload.update(extra)
        resp = client.post("/api/accounts", json=payload)
        assert resp.status_code == 201, resp.json
        return resp.json

    def niche(name="Tech", **extra):
        resp = client.post("/api/niches", json={"name": name, "description": "Gadgets", "primary_statement": "Tech helps",
                                                **extra})
        assert resp.status_code == 201, resp.json
        return resp.json

    def schedule(niche_id, account_id, posts_per_day=4, needs_approval=False):
        resp = client.post("/api/schedules", json={"niche_id": niche_id, "account_id": account_id,
                                                   "posts_per_day": posts_per_day, "needs_approval": needs_approval})
        assert resp.status_code == 201, resp.json
        return resp.json

    return SimpleNamespace(account=account, niche=niche, schedule=schedule)


def fake_publish_error(message, retryable=False):
    return PublishError(message, retryable=retryable)
