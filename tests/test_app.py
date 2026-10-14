"""
test_app.py - automated tests for the Smart IT Helpdesk.

Covers: authentication, CSRF protection, employee and engineer
workflows, ticket lifecycle, validation, permissions, search/filter.
Run with:  python -m pytest tests -v
"""

from models import Ticket, User, db


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def test_login_page_loads(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Smart IT Helpdesk" in resp.data
    assert b'name="csrf_token"' in resp.data
    with client.session_transaction() as session:
        assert session.get("_csrf_token", "").encode() in resp.data


def test_anonymous_user_is_redirected_from_protected_page(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 302
    assert "/login?next=/dashboard" in resp.headers["Location"]


def test_login_success_redirects_to_dashboard(client, login):
    resp = login("anita@techcorp.com", "Engineer@123")
    assert resp.status_code == 200
    assert b"Engineer Command Center" in resp.data


def test_login_wrong_password_shows_error(client, login):
    resp = login("rahul@techcorp.com", "wrong-password")
    assert b"Invalid email or password" in resp.data


def test_admin_created_by_cli_can_authenticate_with_admin_role(
        client, csrf, app, monkeypatch, capsys):
    import create_admin

    answers = iter(["Sneha Pawar", "PAWARSNEHA@GMAIL.COM", "IT"])
    password = "Test-Only-Admin-Passphrase-123!"
    hidden_answers = iter([password, password])

    prompt_count = 0
    initial_output = []

    def fake_input(_prompt):
        nonlocal prompt_count
        prompt_count += 1
        if prompt_count == 1:
            initial_output.append(capsys.readouterr().out)
            assert "Database target: SQLite in-memory database" in initial_output[0]
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(create_admin, "getpass", lambda _prompt: next(hidden_answers))

    create_admin.main()
    final_output = capsys.readouterr().out
    assert "Database target confirmed: SQLite in-memory database" in final_output
    assert password not in initial_output[0] + final_output

    response = client.post("/login", data={
        "email": " pawarsneha@gmail.com ",
        "password": password,
        "csrf_token": csrf(),
    }, follow_redirects=True)
    assert response.status_code == 200

    with client.session_transaction() as session:
        admin_id = session.get("user_id")
        assert admin_id is not None
        assert session.get("user_role") == "admin"
    with app.app_context():
        admin = db.session.get(User, admin_id)
        assert admin is not None
        assert admin.email == "pawarsneha@gmail.com"
        assert admin.role == "admin"
        assert admin.check_password(password)


def test_login_rejects_protocol_relative_redirect(client, csrf):
    response = client.post("/login?next=//evil.example", data={
        "email": "rahul@techcorp.com", "password": "Employee@123",
        "csrf_token": csrf(),
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_csrf_token_required(client):
    """A POST without a valid CSRF token must be rejected."""
    resp = client.post("/login", data={"email": "rahul@techcorp.com",
                                       "password": "Employee@123"})
    assert resp.status_code == 400


def test_registration_creates_employee_account(client, csrf):
    resp = client.post("/register", data={
        "name": "New Jack", "email": "jack@techcorp.com",
        "department": "IT", "password": "Password@123",
        "confirm": "Password@123", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"Account created successfully" in resp.data
    with client.application.app_context():
        user = User.query.filter_by(email="jack@techcorp.com").first()
        assert user is not None
        assert user.role == "employee"


def test_registration_validates_password_mismatch(client, csrf):
    resp = client.post("/register", data={
        "name": "New Jack", "email": "jack@techcorp.com",
        "department": "IT", "password": "Password@123",
        "confirm": "Different@123", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"Passwords do not match" in resp.data


def test_logout_clears_session(client, login):
    login("rahul@techcorp.com", "Employee@123")
    resp = client.get("/logout", follow_redirects=True)
    assert b"Sign in to raise or resolve" in resp.data


# ---------------------------------------------------------------------------
# Employee workflow
# ---------------------------------------------------------------------------
def test_employee_sees_only_own_tickets(client, login):
    login("rahul@techcorp.com", "Employee@123")
    resp = client.get("/tickets")
    assert b"TKT-2026-0001" in resp.data
    assert b"TKT-2026-0002" not in resp.data


def test_employee_cannot_open_foreign_ticket(client, login):
    login("rahul@techcorp.com", "Employee@123")
    resp = client.get("/tickets/TKT-2026-0002")
    assert resp.status_code == 403


def test_employee_cannot_access_engineer_pages(client, login):
    login("rahul@techcorp.com", "Employee@123")
    assert client.get("/users").status_code == 403


def test_create_ticket_generates_number(client, login, csrf):
    login("rahul@techcorp.com", "Employee@123")
    resp = client.post("/tickets/new", data={
        "title": "Headset microphone not detected",
        "description": "The microphone is silent during Teams calls even "
                       "though Windows shows the device as connected.",
        "category": "Hardware", "priority": "Medium", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"created" in resp.data
    with client.application.app_context():
        ticket = Ticket.query.filter_by(title="Headset microphone not detected").first()
        assert ticket is not None
        assert ticket.ticket_number.startswith("TKT-")
        assert ticket.status == "Open"


def test_create_ticket_form_renders_with_csrf_and_new_fields(client, login):
    login("rahul@techcorp.com", "Employee@123")
    response = client.get("/tickets/new")
    assert response.status_code == 200
    assert b'name="csrf_token"' in response.data
    assert b'name="title"' in response.data
    assert b'name="description"' in response.data


def test_create_ticket_rejects_short_description(client, login, csrf):
    login("rahul@techcorp.com", "Employee@123")
    resp = client.post("/tickets/new", data={
        "title": "Broken keyboard",
        "description": "It broke",    # too short
        "category": "Hardware", "priority": "Low", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"at least 20 characters" in resp.data


def test_ticket_activity_logged_on_create(client, login, csrf):
    login("rahul@techcorp.com", "Employee@123")
    client.post("/tickets/new", data={
        "title": "Mouse not detected",
        "description": "The wireless mouse stops responding after sleep. ",
        "category": "Hardware", "priority": "Low", "csrf_token": csrf(),
    })
    with client.application.app_context():
        ticket = Ticket.query.filter_by(title="Mouse not detected").first()
        assert any(log.action == "Ticket created" for log in ticket.activity)


# ---------------------------------------------------------------------------
# Engineer workflow
# ---------------------------------------------------------------------------
def test_engineer_assigns_ticket(client, login, csrf, ids):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.post("/tickets/TKT-2026-0001/assign", data={
        "engineer_id": ids["vikram"], "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"assigned to Vikram Nair" in resp.data
    with client.application.app_context():
        ticket = Ticket.query.filter_by(ticket_number="TKT-2026-0001").first()
        assert ticket.assigned_to_id == ids["vikram"]
        assert ticket.status == "Assigned"
        assert any("Assigned to" in log.action for log in ticket.activity)


def test_engineer_changes_status(client, login, csrf):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.post("/tickets/TKT-2026-0002/status", data={
        "status": "In Progress", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"In Progress" in resp.data
    with client.application.app_context():
        ticket = Ticket.query.filter_by(ticket_number="TKT-2026-0002").first()
        assert ticket.status == "In Progress"


def test_engineer_resolves_ticket_with_notes(client, login, csrf):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.post("/tickets/TKT-2026-0003/resolve", data={
        "resolution_notes": "Replaced the defective roller assembly.",
        "troubleshooting": "Checked feeds, cleaned rollers, swapped unit.",
        "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"marked as resolved" in resp.data
    with client.application.app_context():
        ticket = Ticket.query.filter_by(ticket_number="TKT-2026-0003").first()
        assert ticket.status == "Resolved"
        assert ticket.resolved_at is not None
        assert ticket.resolution_notes is not None


def test_resolution_requires_minimum_note_length(client, login, csrf):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.post("/tickets/TKT-2026-0002/resolve", data={
        "resolution_notes": "Fixed.", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"at least 10 characters" in resp.data


def test_engineer_can_close_and_employee_can_reopen(client, login, csrf):
    login("anita@techcorp.com", "Engineer@123")
    client.post("/tickets/TKT-2026-0002/status", data={
        "status": "Resolved", "csrf_token": csrf(),
    })
    client.post("/tickets/TKT-2026-0002/close", data={"csrf_token": csrf()})

    with client.application.app_context():
        ticket = Ticket.query.filter_by(ticket_number="TKT-2026-0002").first()
        assert ticket.status == "Closed"

    # Owner can re-open it.
    login("priya@techcorp.com", "Employee@123")
    resp = client.post("/tickets/TKT-2026-0002/reopen", data={"csrf_token": csrf()},
                       follow_redirects=True)
    with client.application.app_context():
        ticket = Ticket.query.filter_by(ticket_number="TKT-2026-0002").first()
        assert ticket.status == "Assigned"   # still assigned to Anita


def test_engineer_adds_troubleshooting_notes_and_comment(client, login, csrf):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.post("/tickets/TKT-2026-0002/notes", data={
        "troubleshooting": "Rebooted access point and checked controller logs.",
        "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"Troubleshooting notes saved" in resp.data


# ---------------------------------------------------------------------------
# Search / filter / dashboard
# ---------------------------------------------------------------------------
def test_search_filters_tickets(client, login):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.get("/tickets?q=Wi-Fi")
    assert b"TKT-2026-0002" in resp.data
    assert b"TKT-2026-0001" not in resp.data


def test_filter_by_priority(client, login):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.get("/tickets?priority=Critical")
    assert b"TKT-2026-0003" in resp.data
    assert b"TKT-2026-0001" not in resp.data


def test_filter_by_category(client, login):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.get("/tickets?category=Network")
    assert b"TKT-2026-0002" in resp.data


def test_unassigned_scope(client, login):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.get("/tickets?scope=unassigned")
    assert b"TKT-2026-0001" in resp.data
    assert b"TKT-2026-0003" in resp.data
    assert b"TKT-2026-0002" not in resp.data


def test_engineer_dashboard_counts(client, login):
    login("anita@techcorp.com", "Engineer@123")
    resp = client.get("/dashboard")
    assert b"Engineer Command Center" in resp.data
    # One unassigned Open ticket plus one Critical Open ticket.
    assert b"1" in resp.data


def test_employee_dashboard_shows_own_tickets(client, login):
    login("rahul@techcorp.com", "Employee@123")
    resp = client.get("/dashboard")
    assert b"TKT-2026-0001" in resp.data


def test_404_for_unknown_ticket(client, login):
    login("anita@techcorp.com", "Engineer@123")
    assert client.get("/tickets/TKT-9999-9999").status_code == 404


# ---------------------------------------------------------------------------
# Administrator permissions and system reports
# ---------------------------------------------------------------------------
def test_admin_dashboard_and_all_ticket_access(client, login):
    login("nina@techcorp.com", "AdminPassword@123")
    dashboard = client.get("/dashboard")
    tickets = client.get("/tickets")
    assert dashboard.status_code == 200
    assert b"ADMINISTRATOR OVERVIEW" in dashboard.data
    assert b"Recent activity" in dashboard.data
    assert b"TKT-2026-0001" in tickets.data
    assert b"TKT-2026-0002" in tickets.data
    assert client.get("/tickets/TKT-2026-0002").status_code == 200


def test_admin_and_engineer_directory_visibility(client, login):
    login("nina@techcorp.com", "AdminPassword@123")
    admin_directory = client.get("/users")
    assert admin_directory.status_code == 200
    assert b"User management" in admin_directory.data
    assert b"nina@techcorp.com" in admin_directory.data

    login("anita@techcorp.com", "Engineer@123")
    engineer_directory = client.get("/users")
    assert engineer_directory.status_code == 200
    assert b"priya@techcorp.com" in engineer_directory.data
    assert b"anita@techcorp.com" not in engineer_directory.data


def test_admin_reports_and_engineer_is_denied(client, login):
    login("nina@techcorp.com", "AdminPassword@123")
    report = client.get("/reports")
    assert report.status_code == 200
    assert b"Tickets by status" in report.data
    assert b"Tickets by category" in report.data

    login("anita@techcorp.com", "Engineer@123")
    assert client.get("/reports").status_code == 403


def test_employee_and_engineer_cannot_change_roles(client, login, csrf, ids):
    login("rahul@techcorp.com", "Employee@123")
    assert client.get("/users").status_code == 403
    assert client.post(f"/users/{ids['vikram']}/role", data={
        "role": "admin", "csrf_token": csrf(),
    }).status_code == 403

    login("anita@techcorp.com", "Engineer@123")
    assert client.get("/users").status_code == 200
    assert client.post(f"/users/{ids['rahul']}/role", data={
        "role": "engineer", "csrf_token": csrf(),
    }).status_code == 403


def test_admin_can_promote_user_but_cannot_change_own_role(client, login, csrf, ids, app):
    login("nina@techcorp.com", "AdminPassword@123")
    response = client.post(f"/users/{ids['rahul']}/role", data={
        "role": "engineer", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"role changed" in response.data
    with app.app_context():
        assert db.session.get(User, ids["rahul"]).role == "engineer"

    response = client.post(f"/users/{ids['admin']}/role", data={
        "role": "employee", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"cannot change your own administrator role" in response.data
    with app.app_context():
        assert db.session.get(User, ids["admin"]).role == "admin"


def test_admin_cannot_demote_engineer_with_active_assigned_tickets(client, login, csrf, ids, app):
    login("nina@techcorp.com", "AdminPassword@123")
    response = client.post(f"/users/{ids['anita']}/role", data={
        "role": "employee", "csrf_token": csrf(),
    }, follow_redirects=True)
    assert b"active tickets before changing their role" in response.data
    with app.app_context():
        assert db.session.get(User, ids["anita"]).role == "engineer"


def test_public_registration_cannot_self_assign_privileged_role(client, csrf, app):
    client.post("/register", data={
        "name": "New Admin", "email": "newadmin@techcorp.com",
        "department": "IT", "role": "admin", "password": "Password@123",
        "confirm": "Password@123", "csrf_token": csrf(),
    }, follow_redirects=True)
    with app.app_context():
        user = User.query.filter_by(email="newadmin@techcorp.com").first()
        assert user is not None
        assert user.role == "employee"


def test_initialization_preserves_existing_ticket_records(app, monkeypatch):
    import sys
    from init_db import main as initialize_database

    monkeypatch.setattr(sys, "argv", ["init_db.py"])
    with app.app_context():
        before = Ticket.query.count()
        initialize_database()
        assert Ticket.query.count() == before
        assert Ticket.query.filter_by(ticket_number="TKT-2026-0001").first() is not None


def test_latest_ui_assets_are_served(client):
    page = client.get("/login")
    css = client.get("/static/css/style.css?v=premium-3")
    js = client.get("/static/js/main.js?v=premium-2")
    assert b"style.css?v=premium-3" in page.data
    assert b"main.js?v=premium-2" in page.data
    assert css.status_code == 200 and b".app-sidebar" in css.data
    assert js.status_code == 200 and b"data-nav-toggle" in js.data
