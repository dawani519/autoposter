"""Settings, read from environment variables (a local .env file is supported).

See .env.example for every setting.
"""
import os

from dotenv import load_dotenv

load_dotenv()


def _bool(name, default):
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_url():
    url = os.getenv("DATABASE_URL", "sqlite:///autoposter.db")
    # Replit/Render/Heroku hand out postgres:// URLs, which SQLAlchemy 2 no longer accepts.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _ai_base_url():
    return (os.getenv("AI_BASE_URL") or os.getenv("OPENAI_URL") or "https://openrouter.ai/api/v1").rstrip("/")


def _ai_model(base_url):
    if os.getenv("AI_MODEL"):
        return os.getenv("AI_MODEL")
    # OpenRouter names models "provider/model"; OpenAI itself doesn't.
    return "gpt-4o-mini" if "api.openai.com" in base_url else "openai/gpt-4o-mini"


class Config:
    DATABASE_URL = _database_url()

    # Dashboard login (HTTP Basic auth). The app refuses to start without a password.
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

    # Key used to encrypt stored social media tokens. Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")

    # Any OpenAI-compatible chat completions API: OpenRouter (default) or OpenAI.
    AI_BASE_URL = _ai_base_url()
    AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
    AI_MODEL = _ai_model(AI_BASE_URL)

    # Posts are spread evenly across this daily window, in this timezone.
    TIMEZONE = os.getenv("TIMEZONE", "UTC")
    POSTING_WINDOW_START = os.getenv("POSTING_WINDOW_START", "07:00")
    POSTING_WINDOW_END = os.getenv("POSTING_WINDOW_END", "23:00")

    # LinkedIn API version (YYYYMM). LinkedIn retires each version about a year after release;
    # see https://learn.microsoft.com/linkedin/marketing/versioning
    LINKEDIN_API_VERSION = os.getenv("LINKEDIN_API_VERSION", "202609")

    # Publishing
    MAX_POST_ATTEMPTS = int(os.getenv("MAX_POST_ATTEMPTS", "3"))
    RATE_LIMIT_RETRY_MINUTES = int(os.getenv("RATE_LIMIT_RETRY_MINUTES", "15"))

    # Background jobs. Run them in the web process (simple, one process) or set this to
    # false and run `python worker.py` separately.
    RUN_SCHEDULER = _bool("RUN_SCHEDULER", True)
    PLAN_INTERVAL_MINUTES = int(os.getenv("PLAN_INTERVAL_MINUTES", "30"))

    PORT = int(os.getenv("PORT", "5000"))
