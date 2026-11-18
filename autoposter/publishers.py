"""Publishing to social platforms.

Each publisher implements:
  publish(creds, text) -> external post id
  verify(creds) -> (display name, extra fields to save on the account)

and raises PublishError. `retryable` means the post definitely wasn't published and
can be tried again later (e.g. rate limits). Anything else is final.
"""
import logging
import re
from urllib.parse import quote

import requests
import tweepy

log = logging.getLogger(__name__)


class PublishError(Exception):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


# ---------- X (Twitter) ----------

class XPublisher:
    platform = "x"
    required = ("api_key", "api_secret", "access_token", "access_secret")

    def __init__(self, cfg, client_factory=None):
        self.client_factory = client_factory or (
            lambda c: tweepy.Client(
                consumer_key=c["api_key"],
                consumer_secret=c["api_secret"],
                access_token=c["access_token"],
                access_token_secret=c["access_secret"],
            )
        )

    def publish(self, creds, text):
        try:
            response = self.client_factory(creds).create_tweet(text=text)
            return str(response.data["id"])
        except tweepy.TooManyRequests as exc:
            raise PublishError(f"X rate limit: {exc}", retryable=True) from exc
        except tweepy.Unauthorized as exc:
            raise PublishError(f"X rejected the account's keys: {exc}") from exc
        except tweepy.Forbidden as exc:
            # Includes duplicate posts and apps without write permission.
            raise PublishError(f"X refused the post: {exc}") from exc
        except tweepy.TweepyException as exc:
            raise PublishError(f"X error: {exc}") from exc
        except requests.RequestException as exc:
            raise PublishError(f"Couldn't reach X (the post may or may not have gone out): {exc}") from exc

    def verify(self, creds):
        try:
            me = self.client_factory(creds).get_me()
        except (tweepy.TweepyException, requests.RequestException) as exc:
            raise PublishError(f"X rejected the account's keys: {exc}") from exc
        return f"@{me.data.username}", {}


# ---------- LinkedIn ----------

# Characters LinkedIn's "little" text format reserves; they must be backslash-escaped.
_LITTLE_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_HASHTAG = re.compile(r"(?<![\w#])#(\w+)")


def escape_little_text(text):
    """Escape LinkedIn commentary so it's published exactly as written, keeping #hashtags clickable."""
    out, last = [], 0
    for match in _HASHTAG.finditer(text):
        out.append(_LITTLE_RESERVED.sub(r"\\\1", text[last:match.start()]))
        out.append("#" + match.group(1))
        last = match.end()
    out.append(_LITTLE_RESERVED.sub(r"\\\1", text[last:]))
    return "".join(out)


class LinkedInPublisher:
    platform = "linkedin"
    required = ("access_token",)
    API = "https://api.linkedin.com"

    def __init__(self, cfg, http=None):
        self.version = cfg["LINKEDIN_API_VERSION"]
        self.http = http or requests.Session()

    def _headers(self, token):
        return {
            "Authorization": f"Bearer {token}",
            "Linkedin-Version": self.version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }

    def publish(self, creds, text):
        if not creds.get("author_urn"):
            raise PublishError("LinkedIn account has no author URN; click Verify on the account")
        body = {
            "author": creds["author_urn"],
            "commentary": escape_little_text(text),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        try:
            resp = self.http.post(f"{self.API}/rest/posts", headers=self._headers(creds["access_token"]),
                                  json=body, timeout=30)
        except requests.RequestException as exc:
            raise PublishError(f"Couldn't reach LinkedIn (the post may or may not have gone out): {exc}") from exc

        if resp.status_code == 201:
            return resp.headers.get("x-restli-id", "")
        message = _linkedin_error(resp)
        if resp.status_code == 429:
            raise PublishError(f"LinkedIn rate limit: {message}", retryable=True)
        if resp.status_code == 401:
            raise PublishError("LinkedIn access token is invalid or expired (they last 60 days); "
                               "paste a new one into the account")
        if resp.status_code == 403:
            raise PublishError("LinkedIn refused the post: the token needs the w_member_social permission "
                               "(or w_organization_social for a company page) and must belong to the author. "
                               f"{message}")
        if resp.status_code == 426:
            raise PublishError(f"LinkedIn API version {self.version} has been retired; "
                               "update LINKEDIN_API_VERSION")
        raise PublishError(f"LinkedIn error {resp.status_code}: {message}")

    def verify(self, creds):
        """Checks the token and finds the member's author URN (needs the openid + profile scopes)."""
        try:
            resp = self.http.get(f"{self.API}/v2/userinfo",
                                 headers={"Authorization": f"Bearer {creds['access_token']}"}, timeout=30)
        except requests.RequestException as exc:
            raise PublishError(f"Couldn't reach LinkedIn: {exc}") from exc
        if resp.status_code != 200:
            if creds.get("author_urn"):
                # Tokens without the openid scope can't call userinfo but can still post.
                return creds["author_urn"], {}
            raise PublishError(
                "LinkedIn didn't accept the token for profile lookup. Either generate it with the "
                "openid and profile scopes, or enter the author URN yourself. "
                f"({resp.status_code}: {_linkedin_error(resp)})"
            )
        info = resp.json()
        urn = creds.get("author_urn") or f"urn:li:person:{info['sub']}"
        return info.get("name") or urn, {"author_urn": urn}


def _linkedin_error(resp):
    try:
        body = resp.json()
        return body.get("message") or body.get("error_description") or str(body)
    except ValueError:
        return resp.text[:300]


PLATFORMS = {"x": "X (Twitter)", "linkedin": "LinkedIn"}


def build_publishers(cfg):
    return {"x": XPublisher(cfg), "linkedin": LinkedInPublisher(cfg)}


def post_url(platform, external_id):
    if not external_id:
        return None
    if platform == "x":
        return f"https://x.com/i/web/status/{external_id}"
    if platform == "linkedin":
        return f"https://www.linkedin.com/feed/update/{quote(external_id, safe=':')}/"
    return None
