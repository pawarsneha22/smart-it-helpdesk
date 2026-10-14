"""Create an administrator without exposing privileged registration publicly.

Run from the project directory with ``python create_admin.py``. Existing
tables and records are preserved; an account with the supplied email is never
silently promoted or overwritten.
"""

from getpass import getpass
from pathlib import Path

from app import app, validate_email
from models import DEPARTMENTS, User, db


def _database_target():
    """Describe the configured database without exposing URI credentials."""
    url = db.engine.url
    if url.get_backend_name() == "sqlite":
        if not url.database or url.database == ":memory:":
            return "SQLite in-memory database"
        return f"SQLite file {Path(url.database).resolve()}"
    target = f"{url.get_backend_name()} database {url.database!r}"
    if url.host:
        target += f" on {url.host}"
    return target


def main():
    with app.app_context():
        print(f"Database target: {_database_target()}", flush=True)

    name = input("Administrator full name: ").strip()
    email = input("Administrator work email: ").strip().lower()
    department = input("Department (IT): ").strip() or "IT"

    if len(name) < 3:
        raise SystemExit("Name must be at least 3 characters long.")
    if not validate_email(email):
        raise SystemExit("Enter a valid email address.")
    if department not in DEPARTMENTS:
        raise SystemExit("Choose a valid department.")

    password = getpass("Password (minimum 12 characters): ")
    confirm = getpass("Confirm password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters long.")
    if password != confirm:
        raise SystemExit("Passwords do not match.")

    with app.app_context():
        db.create_all()
        if User.query.filter_by(email=email).first():
            raise SystemExit("An account with that email already exists; no changes were made.")
        admin = User(name=name, email=email, department=department,
                     role="admin", password=password)
        db.session.add(admin)
        db.session.commit()
        print(f"Administrator account created for {email} in {_database_target()}.")
        print(f"Database target confirmed: {_database_target()}")


if __name__ == "__main__":
    main()
