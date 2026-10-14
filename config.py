"""
config.py
---------
Application configuration for the Smart IT Helpdesk.

Kept in a separate module so that credentials, database location and
behaviour toggles are easy to find and change. Values can also be
overridden via environment variables, which is what you would do when
deploying to a real server.
"""

import os
import secrets

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)


def _load_or_create_local_secret(instance_dir=INSTANCE_DIR):
    """Keep locally signed Flask sessions valid across application restarts."""
    os.makedirs(instance_dir, exist_ok=True)
    secret_path = os.path.join(instance_dir, ".flask_secret")
    try:
        with open(secret_path, "x", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_hex(32))
    except FileExistsError:
        pass

    with open(secret_path, "r", encoding="utf-8") as secret_file:
        secret = secret_file.read().strip()
    if not secret:
        secret = secrets.token_hex(32)
        with open(secret_path, "w", encoding="utf-8") as secret_file:
            secret_file.write(secret)
    return secret


class Config:
    """Base configuration shared by all environments."""

    # --- Security ----------------------------------------------------------
    # In production this MUST be overridden with a long random value,
    # for example:  python -c "import secrets; print(secrets.token_hex(32))"
    # A deployment should provide a stable secret through the environment.
    # Deployments should set SECRET_KEY. Local runs keep a random key in the
    # ignored instance directory so sessions and CSRF tokens survive restarts.
    SECRET_KEY = os.environ.get("SECRET_KEY") or _load_or_create_local_secret()

    # --- Database ----------------------------------------------------------
    # SQLite file lives inside the instance/ folder, which is git-ignored.
    INSTANCE_DIR = INSTANCE_DIR

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(INSTANCE_DIR, "helpdesk.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- Business rules -----------------------------------------------------
    # Maximum hours allowed between ticket creation and first response,
    # used for the SLA (service-level agreement) indicator on the UI.
    SLA_HOURS = {
        "Low": 24,
        "Medium": 8,
        "High": 4,
        "Critical": 1,
    }


class TestConfig(Config):
    """Configuration used by the automated test suite."""

    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret-key"


class DevelopmentConfig(Config):
    # Debug is opt-in so normal local runs do not expose the interactive debugger.
    DEBUG = os.environ.get("FLASK_DEBUG", "0").strip().lower() in {"1", "true", "yes"}
