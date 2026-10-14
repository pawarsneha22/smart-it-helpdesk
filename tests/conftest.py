"""
Pytest fixtures and helpers for the Helpdesk test suite.

The suite runs against an in-memory SQLite database that is recreated
for every test, so tests never touch the development data.
"""

import pytest
import os

# SQLAlchemy Flask engines are created during db.init_app(app), before the
# per-test fixture can override the URI. Select an in-memory DB before app.py
# is imported so tests can never point drop_all() at the developer database.
_original_database_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from app import app as flask_app
from models import ActivityLog, Ticket, User, db
if _original_database_url is None:
    os.environ.pop("DATABASE_URL", None)
else:
    os.environ["DATABASE_URL"] = _original_database_url


def _seed():
    """Insert a small, deterministic data set for the tests."""
    anita = User(name="Anita Rao", email="anita@techcorp.com",
                 department="IT", role="engineer", password="Engineer@123")
    vikram = User(name="Vikram Nair", email="vikram@techcorp.com",
                  department="IT", role="engineer", password="Engineer@123")
    rahul = User(name="Rahul Sharma", email="rahul@techcorp.com",
                 department="Finance", role="employee",
                 employee_code="EMP-FIN-1024", password="Employee@123")
    priya = User(name="Priya Patel", email="priya@techcorp.com",
                 department="HR", role="employee",
                 employee_code="EMP-HR-2087", password="Employee@123")
    admin = User(name="Nina Admin", email="nina@techcorp.com",
                 department="IT", role="admin", password="AdminPassword@123")
    db.session.add_all([anita, vikram, rahul, priya, admin])
    db.session.flush()

    t1 = Ticket(ticket_number="TKT-2026-0001", title="Laptop will not boot after update",
                description="Black screen after the latest Windows update. " * 2,
                category="Hardware", priority="High", status="Open",
                reported_by_id=rahul.id)
    t2 = Ticket(ticket_number="TKT-2026-0002", title="Guest Wi-Fi keeps dropping",
                description="The guest network drops every few minutes in Block C. " * 2,
                category="Network", priority="Medium", status="Assigned",
                reported_by_id=priya.id, assigned_to_id=anita.id)
    t3 = Ticket(ticket_number="TKT-2026-0003", title="Printer paper jam error",
                description="The HR printer reports a jam with an empty tray. " * 2,
                category="Printer", priority="Critical", status="Open",
                reported_by_id=priya.id)
    db.session.add_all([t1, t2, t3])
    db.session.flush()

    db.session.add(ActivityLog(ticket_id=t1.id, user_id=rahul.id,
                               action="Ticket created"))
    db.session.add(ActivityLog(ticket_id=t2.id, user_id=anita.id,
                               action="Assigned to Anita Rao"))
    db.session.commit()


@pytest.fixture
def app():
    flask_app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        _seed()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf(client):
    """Return (and if needed create) the CSRF token stored in the session."""

    def _get():
        with client.session_transaction() as sess:
            if not sess.get("_csrf_token"):
                sess["_csrf_token"] = "test-csrf-token"
            return sess["_csrf_token"]

    return _get


@pytest.fixture
def login(client, csrf):
    """Log in through the real /login route with a valid CSRF token."""

    def _login(email, password):
        # Test helpers may switch roles within one test; clear only auth state
        # while retaining the CSRF token for the real login form.
        with client.session_transaction() as sess:
            sess.pop("user_id", None)
            sess.pop("user_role", None)
            sess.pop("user_name", None)
        return client.post(
            "/login",
            data={"email": email, "password": password, "csrf_token": csrf()},
            follow_redirects=True,
        )

    return _login


@pytest.fixture
def ids(app):
    """Map of well-known email -> database id for use in POST bodies."""
    with app.app_context():
        return {
            "anita": User.query.filter_by(email="anita@techcorp.com").first().id,
            "vikram": User.query.filter_by(email="vikram@techcorp.com").first().id,
            "rahul": User.query.filter_by(email="rahul@techcorp.com").first().id,
            "priya": User.query.filter_by(email="priya@techcorp.com").first().id,
            "admin": User.query.filter_by(email="nina@techcorp.com").first().id,
        }
