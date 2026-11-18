"""Database connection, schema creation and upgrades of existing databases."""
import logging

from flask import current_app
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from autoposter.models import Account, Base

log = logging.getLogger(__name__)

# Bring a database created by the original schema.sql up to date. Every statement is
# safe to run repeatedly (PostgreSQL only; new databases get the full schema directly).
MIGRATIONS = [
    "ALTER TABLE platform_accounts ADD COLUMN IF NOT EXISTS name VARCHAR(255)",
    "ALTER TABLE platform_accounts ADD COLUMN IF NOT EXISTS author_urn VARCHAR(255)",
    "ALTER TABLE schedule ADD COLUMN IF NOT EXISTS account_id INTEGER "
    "REFERENCES platform_accounts(id) ON DELETE SET NULL",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS last_error TEXT",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS posted_at TIMESTAMP",
    "ALTER TABLE posts ADD COLUMN IF NOT EXISTS external_id VARCHAR(64)",
    # Old status names
    "UPDATE posts SET status = 'pending_approval' WHERE status IN ('draft', 'pending approval')",
    "UPDATE posts SET status = 'scheduled' WHERE status = 'approved'",
]

TOKEN_FIELDS = ("api_key", "api_secret", "access_token", "access_secret")


class Database:
    def __init__(self, url):
        kwargs = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(url, **kwargs)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init(self, secret_box):
        Base.metadata.create_all(self.engine)
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as conn:
                for statement in MIGRATIONS:
                    conn.execute(text(statement))
        self._encrypt_plaintext_tokens(secret_box)

    def _encrypt_plaintext_tokens(self, secret_box):
        """Tokens saved by the original version were stored in plain text."""
        with self.Session.begin() as s:
            count = 0
            for account in s.scalars(select(Account)):
                for field in TOKEN_FIELDS:
                    value = getattr(account, field)
                    if value and not secret_box.is_encrypted(value):
                        setattr(account, field, secret_box.encrypt(value))
                        count += 1
            if count:
                log.info("Encrypted %d stored tokens that were in plain text", count)


def get_db() -> Database:
    return current_app.extensions["db"]
