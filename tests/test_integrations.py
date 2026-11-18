"""The real AI client and platform publishers, against fake HTTP (no network)."""
from types import SimpleNamespace

import pytest
import requests
import tweepy

from autoposter.ai import ContentGenerator, GenerationError
from autoposter.publishers import LinkedInPublisher, PublishError, XPublisher, escape_little_text, post_url


class FakeResp:
    def __init__(self, status_code=200, body=None, headers=None, reason="OK"):
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        self.reason = reason
        self.text = str(body)

    def json(self):
        if self._body is None:
            raise requests.JSONDecodeError("no json", "", 0)
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeHttp:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def post(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self._next("GET", url, **kwargs)


def niche(**kw):
    defaults = dict(name="Personal finance", description="Money tips for students",
                    primary_statement="Small savings add up", hashtags=[SimpleNamespace(tag="money")])
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def completion(text):
    return FakeResp(200, {"choices": [{"message": {"content": text}}]})


AI_CFG = {"AI_BASE_URL": "https://openrouter.test/api/v1", "AI_API_KEY": "sk-test", "AI_MODEL": "openai/gpt-4o-mini"}


# ---------- AI ----------

def test_ai_prompt_uses_niche_details_and_platform():
    http = FakeHttp(completion('"Save 10% of every allowance. #money"'))
    text = ContentGenerator(AI_CFG, http=http).generate(niche(), "x", ["Old post"])
    assert text == "Save 10% of every allowance. #money"  # surrounding quotes removed
    call = http.calls[0]
    assert call["url"] == "https://openrouter.test/api/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-test"
    assert call["json"]["model"] == "openai/gpt-4o-mini"
    system, user = call["json"]["messages"]
    assert "X (Twitter)" in system["content"]
    for expected in ("Personal finance", "Money tips for students", "Small savings add up", "#money", "Old post"):
        assert expected in user["content"]


def test_ai_linkedin_style():
    http = FakeHttp(completion("A longer LinkedIn post."))
    ContentGenerator(AI_CFG, http=http).generate(niche(), "linkedin")
    assert "LinkedIn" in http.calls[0]["json"]["messages"][0]["content"]


def test_ai_too_long_retries_then_gives_up():
    http = FakeHttp(completion("a" * 300), completion("short enough"))
    assert ContentGenerator(AI_CFG, http=http).generate(niche(), "x") == "short enough"
    assert "too long" in http.calls[1]["json"]["messages"][1]["content"]

    http = FakeHttp(completion("a" * 300), completion("b" * 300))
    with pytest.raises(GenerationError, match="longer than 280"):
        ContentGenerator(AI_CFG, http=http).generate(niche(), "x")


def test_ai_errors():
    with pytest.raises(GenerationError, match="AI_API_KEY"):
        ContentGenerator({**AI_CFG, "AI_API_KEY": ""}, http=FakeHttp()).generate(niche(), "x")
    with pytest.raises(GenerationError, match="AI request failed"):
        ContentGenerator(AI_CFG, http=FakeHttp(FakeResp(500, {}))).generate(niche(), "x")
    with pytest.raises(GenerationError):
        ContentGenerator(AI_CFG, http=FakeHttp(requests.ConnectionError("down"))).generate(niche(), "x")
    with pytest.raises(GenerationError):
        ContentGenerator(AI_CFG, http=FakeHttp(FakeResp(200, {"choices": []}))).generate(niche(), "x")


# ---------- X ----------

X_CREDS = {"api_key": "k", "api_secret": "ks", "access_token": "t", "access_secret": "ts", "author_urn": None}


def tweepy_error(cls, status):
    return cls(FakeResp(status, {"detail": "nope"}, reason="Err"))


def x_publisher(client):
    return XPublisher({}, client_factory=lambda creds: client)


def test_x_publish():
    client = SimpleNamespace(create_tweet=lambda text: SimpleNamespace(data={"id": "123", "text": text}))
    assert x_publisher(client).publish(X_CREDS, "hi") == "123"


@pytest.mark.parametrize("error,retryable", [
    (tweepy_error(tweepy.TooManyRequests, 429), True),
    (tweepy_error(tweepy.Unauthorized, 401), False),
    (tweepy_error(tweepy.Forbidden, 403), False),
    (requests.ConnectionError("down"), False),
])
def test_x_errors(error, retryable):
    def create_tweet(text):
        raise error

    with pytest.raises(PublishError) as info:
        x_publisher(SimpleNamespace(create_tweet=create_tweet)).publish(X_CREDS, "hi")
    assert info.value.retryable is retryable


def test_x_verify():
    client = SimpleNamespace(get_me=lambda: SimpleNamespace(data=SimpleNamespace(username="autoposter")))
    assert x_publisher(client).verify(X_CREDS) == ("@autoposter", {})


# ---------- LinkedIn ----------

LI_CFG = {"LINKEDIN_API_VERSION": "202609"}
LI_CREDS = {"access_token": "li-token", "author_urn": "urn:li:person:abc123"}


@pytest.mark.parametrize("text,expected", [
    ("Plain text", "Plain text"),
    ("Growth (30%) & more!", r"Growth \(30%\) & more!"),
    ("Email me @ work_place", r"Email me \@ work\_place"),
    ("Keep #hashtags clickable #AI2026", "Keep #hashtags clickable #AI2026"),
    ("C# and F# are languages", r"C\# and F\# are languages"),
    ("* bullet\n~strike~ <tag> {x} [y] a|b back\\slash",
     r"\* bullet" "\n" r"\~strike\~ \<tag\> \{x\} \[y\] a\|b back\\slash"),
])
def test_little_text_escaping(text, expected):
    assert escape_little_text(text) == expected


def test_linkedin_publish():
    http = FakeHttp(FakeResp(201, None, headers={"x-restli-id": "urn:li:share:999"}))
    post_id = LinkedInPublisher(LI_CFG, http=http).publish(LI_CREDS, "Hello (world) #news")
    assert post_id == "urn:li:share:999"
    call = http.calls[0]
    assert call["url"] == "https://api.linkedin.com/rest/posts"
    assert call["headers"]["Linkedin-Version"] == "202609"
    assert call["headers"]["X-Restli-Protocol-Version"] == "2.0.0"
    assert call["headers"]["Authorization"] == "Bearer li-token"
    assert call["json"]["author"] == "urn:li:person:abc123"
    assert call["json"]["commentary"] == r"Hello \(world\) #news"
    assert call["json"]["lifecycleState"] == "PUBLISHED" and call["json"]["visibility"] == "PUBLIC"
    assert call["json"]["distribution"]["feedDistribution"] == "MAIN_FEED"


@pytest.mark.parametrize("status,retryable,message", [
    (429, True, "rate limit"),
    (401, False, "expired"),
    (403, False, "w_member_social"),
    (426, False, "LINKEDIN_API_VERSION"),
    (422, False, "422"),
])
def test_linkedin_errors(status, retryable, message):
    http = FakeHttp(FakeResp(status, {"message": "details"}))
    with pytest.raises(PublishError) as info:
        LinkedInPublisher(LI_CFG, http=http).publish(LI_CREDS, "hi")
    assert info.value.retryable is retryable and message in str(info.value)


def test_linkedin_needs_author():
    with pytest.raises(PublishError, match="author URN"):
        LinkedInPublisher(LI_CFG, http=FakeHttp()).publish({"access_token": "t", "author_urn": None}, "hi")


def test_linkedin_verify_finds_person_urn():
    http = FakeHttp(FakeResp(200, {"sub": "xyz789", "name": "Ada Lovelace"}))
    name, updates = LinkedInPublisher(LI_CFG, http=http).verify({"access_token": "t", "author_urn": None})
    assert name == "Ada Lovelace" and updates == {"author_urn": "urn:li:person:xyz789"}
    assert http.calls[0]["url"] == "https://api.linkedin.com/v2/userinfo"


def test_linkedin_verify_keeps_organization_urn():
    http = FakeHttp(FakeResp(200, {"sub": "xyz789", "name": "Ada"}))
    _, updates = LinkedInPublisher(LI_CFG, http=http).verify(
        {"access_token": "t", "author_urn": "urn:li:organization:42"})
    assert updates == {"author_urn": "urn:li:organization:42"}


def test_linkedin_verify_without_openid_scope():
    http = FakeHttp(FakeResp(403, {"message": "no"}))
    with pytest.raises(PublishError, match="openid"):
        LinkedInPublisher(LI_CFG, http=http).verify({"access_token": "t", "author_urn": None})
    http = FakeHttp(FakeResp(403, {"message": "no"}))
    assert LinkedInPublisher(LI_CFG, http=http).verify(LI_CREDS) == ("urn:li:person:abc123", {})


def test_post_urls():
    assert post_url("x", "123") == "https://x.com/i/web/status/123"
    assert post_url("linkedin", "urn:li:share:9") == "https://www.linkedin.com/feed/update/urn:li:share:9/"
    assert post_url("x", None) is None
