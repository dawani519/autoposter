"""Flask app factory."""
import hmac
import logging
import os

from flask import Flask, Response, jsonify, request, send_from_directory

from autoposter.ai import ContentGenerator
from autoposter.api import api
from autoposter.config import Config
from autoposter.crypto import SecretBox
from autoposter.db import Database
from autoposter.publishers import build_publishers

log = logging.getLogger(__name__)
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def create_app(overrides=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)

    if not app.config["ADMIN_PASSWORD"]:
        raise ValueError("ADMIN_PASSWORD is required: the dashboard controls your social media accounts")

    secrets = SecretBox(app.config["ENCRYPTION_KEY"])
    db = Database(app.config["DATABASE_URL"])
    db.init(secrets)
    app.extensions.update(
        db=db,
        secrets=secrets,
        generator=ContentGenerator(app.config),
        publishers=build_publishers(app.config),
        scheduler_status={"running": False},
    )
    if not app.config["AI_API_KEY"]:
        log.warning("AI_API_KEY is not set: scheduled posts can't be written until it is")

    @app.before_request
    def require_login():
        if request.path == "/health":
            return None
        auth = request.authorization
        if auth and auth.type == "basic":
            user_ok = hmac.compare_digest((auth.username or "").encode(), app.config["ADMIN_USERNAME"].encode())
            pass_ok = hmac.compare_digest((auth.password or "").encode(), app.config["ADMIN_PASSWORD"].encode())
            if user_ok and pass_ok:
                return None
        return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="AutoPoster"'})

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/")
    def index():
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/static/<path:filename>")
    def static_files(filename):
        return send_from_directory(STATIC_DIR, filename)

    app.register_blueprint(api)
    return app
