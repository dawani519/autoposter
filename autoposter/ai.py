"""AI post writing through any OpenAI-compatible chat completions API (OpenRouter, OpenAI...)."""
import logging

import requests

log = logging.getLogger(__name__)

# What a good post looks like on each platform. max_chars is a hard limit we enforce.
PLATFORM_STYLE = {
    "x": {
        "label": "X (Twitter)",
        "max_chars": 280,
        "target": "at most 250 characters",
        "tone": "punchy and conversational, one idea, at most 2 hashtags",
    },
    "linkedin": {
        "label": "LinkedIn",
        "max_chars": 3000,
        "target": "between 400 and 1200 characters",
        "tone": (
            "professional but human: a strong opening line, short paragraphs, a concrete insight "
            "or takeaway, and 3 to 5 hashtags at the end"
        ),
    },
}


class GenerationError(Exception):
    pass


def max_length(platform):
    return PLATFORM_STYLE[platform]["max_chars"]


class ContentGenerator:
    def __init__(self, cfg, http=None):
        self.base_url = cfg["AI_BASE_URL"]
        self.api_key = cfg["AI_API_KEY"]
        self.model = cfg["AI_MODEL"]
        self.http = http or requests.Session()

    def build_messages(self, niche, platform, recent_posts=(), shorter=False):
        style = PLATFORM_STYLE[platform]
        system = (
            f"You write social media posts for {style['label']}. Reply with the post text only: "
            "no quotation marks around it, no preamble, no explanation. "
            f"Length: {style['target']}. Style: {style['tone']}."
        )
        lines = [f"Topic: {niche.name}"]
        if niche.description:
            lines.append(f"About this topic: {niche.description}")
        if niche.primary_statement:
            lines.append(f"Key message to support: {niche.primary_statement}")
        tags = [h.tag if h.tag.startswith("#") else f"#{h.tag}" for h in niche.hashtags]
        if tags:
            lines.append(f"Hashtags to use where they fit: {' '.join(tags)}")
        if recent_posts:
            lines.append("Recent posts. Don't repeat their ideas or wording:")
            lines.extend(f"- {p}" for p in recent_posts)
        lines.append("Write one new post.")
        if shorter:
            lines.append(f"Your last attempt was too long. Keep it well under {style['max_chars']} characters.")
        return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(lines)}]

    def generate(self, niche, platform, recent_posts=()):
        """Returns post text that fits the platform's limit, or raises GenerationError."""
        if not self.api_key:
            raise GenerationError("AI_API_KEY is not set")
        limit = max_length(platform)
        for attempt in range(2):
            text = self._complete(self.build_messages(niche, platform, recent_posts, shorter=attempt > 0))
            if text and len(text) <= limit:
                return text
            log.info("AI post was %d characters (limit %d); retrying", len(text), limit)
        raise GenerationError(f"AI kept writing posts longer than {limit} characters")

    def _complete(self, messages):
        try:
            resp = self.http.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "X-Title": "AutoPoster",  # shown in the OpenRouter dashboard; ignored by OpenAI
                },
                json={"model": self.model, "messages": messages},
                timeout=60,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            raise GenerationError(f"AI request failed: {exc}") from exc
        return _clean(text)


def _clean(text):
    text = (text or "").strip()
    # Models sometimes wrap the whole post in quotes despite instructions.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'“”":
        text = text[1:-1].strip()
    if len(text) >= 2 and text[0] == "“" and text[-1] == "”":
        text = text[1:-1].strip()
    return text
