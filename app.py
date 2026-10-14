"""
app.py
------
Smart IT Helpdesk & Support Ticket Management System
====================================================

A Flask application that lets employees report IT problems and support
engineers receive, prioritise, troubleshoot, update and resolve them.

Highlights:
  * Role-based access (employee vs. engineer) implemented with a
    lightweight session-based auth layer + decorators.
  * Full ticket lifecycle: Open -> Assigned -> In Progress -> Resolved -> Closed.
  * Activity log (audit trail) for every state change.
  * Search / filter / sort on the ticket list.
  * Response & resolution time tracking with a simple SLA indicator.
  * CSRF protection and server-side input validation.
"""

import secrets

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from sqlalchemy import or_

from config import DevelopmentConfig
from models import (ACTIVE_STATUSES, ROLES, TICKET_CATEGORIES, TICKET_PRIORITIES,
                    TICKET_STATUSES, ActivityLog, Ticket, User, db, utcnow)

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)
db.init_app(app)


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
def _csrftoken() -> str:
    """Create (and remember) a per-session CSRF token for POST forms."""
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_hex(32)
        session["_csrf_token"] = token
    return token


app.jinja_env.globals["csrf_token"] = _csrftoken


def _nice_duration(total_seconds) -> str:
    """Convert seconds into a human readable duration such as '2h 15m'."""
    if total_seconds is None or total_seconds < 0:
        return "—"
    seconds = int(total_seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


app.jinja_env.filters["duration"] = _nice_duration


def _datetime_str(value) -> str:
    if not value:
        return "—"
    return value.strftime("%d %b %Y, %H:%M")


app.jinja_env.filters["dt"] = _datetime_str


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------
def current_user():
    """Return the logged-in User model instance or None."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return db.session.get(User, user_id)


app.jinja_env.globals["current_user"] = current_user


def login_required(view):
    """Decorator: redirect anonymous visitors to the login page."""

    def wrapper(*args, **kwargs):
        if session.get("user_id") is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        user = current_user()
        if user is None:
            session.clear()
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        kwargs["_user"] = user
        return view(*args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


def engineer_required(view):
    """Allow engineers and administrators to use support-team routes."""

    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        if not user.is_engineer() and not user.is_admin():
            abort(403)
        kwargs["_user"] = user
        return view(*args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


def admin_required(view):
    """Only administrators may manage accounts or view global reports."""
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        if not user.is_admin():
            abort(403)
        kwargs["_user"] = user
        return view(*args, **kwargs)

    wrapper.__name__ = view.__name__
    return wrapper


@app.before_request
def csrf_protect():
    """Reject POST requests that do not carry a valid CSRF token."""
    if request.method == "POST":
        token = session.get("_csrf_token")
        incoming = request.form.get("csrf_token")
        if not token or not incoming or not secrets.compare_digest(token, incoming):
            abort(400, description="Invalid or missing CSRF token.")


# ---------------------------------------------------------------------------
# Finding a ticket by its human-readable number
# ---------------------------------------------------------------------------
def get_ticket_or_404(ticket_number):
    """Return a ticket by number or abort with 404."""
    ticket = Ticket.query.filter_by(ticket_number=ticket_number).first()
    if ticket is None:
        abort(404)
    return ticket


def generate_ticket_number() -> str:
    """Produce a unique, human-friendly ID such as TKT-2026-0042."""
    last = db.session.query(db.func.max(Ticket.id)).scalar() or 0
    return f"TKT-{utcnow().year}-{last + 1:04d}"


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def validate_email(email: str) -> bool:
    """Very-lightweight structural check: user@host.tld."""
    import re

    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email.strip()))


def valid_choice(value, choices) -> bool:
    return value in choices


# ---------------------------------------------------------------------------
# Routes — authentication
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Landing page: bounce signed-in users to their dashboard."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    """Self-service registration. New accounts always join as employees."""
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        department = request.form.get("department", "").strip()
        employee_code = request.form.get("employee_code", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        # Server-side validation ------------------------------------------
        if not name or not email or not department or not password:
            flash("All fields are required.", "danger")
        elif len(name) < 3:
            flash("Name must be at least 3 characters long.", "danger")
        elif not validate_email(email):
            flash("Please enter a valid email address.", "danger")
        elif department not in (
            "IT", "HR", "Finance", "Sales", "Marketing", "Operations", "Admin"
        ):
            flash("Please select a valid department.", "danger")
        elif len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
        elif password != confirm:
            flash("Passwords do not match.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("An account with this email already exists.", "danger")
        else:
            user = User(
                name=name,
                email=email,
                department=department,
                employee_code=employee_code or None,
                role="employee",
                password=password,
            )
            db.session.add(user)
            db.session.commit()
            flash("Account created successfully. Please sign in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html", departments=[
        "IT", "HR", "Finance", "Sales", "Marketing", "Operations", "Admin"])


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "danger")
        else:
            session.clear()  # drop any stale data, then start a fresh session
            session["user_id"] = user.id
            session["user_role"] = user.role
            session["user_name"] = user.name
            flash(f"Welcome back, {user.name}!", "success")
            next_page = request.args.get("next")
            # Only honour relative paths to avoid open-redirect abuse.
            if (next_page and (not next_page.startswith("/")
                               or next_page.startswith("//")
                               or "\\" in next_page)):
                next_page = None
            return redirect(next_page or url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes — dashboard
# ---------------------------------------------------------------------------
@app.route("/dashboard")
@login_required
def dashboard(_user):
    """Role-aware overview of ticket statistics and recent activity."""

    if _user.is_admin():
        stats = {
            "total": Ticket.query.count(),
            "open": Ticket.query.filter_by(status="Open").count(),
            "in_progress": Ticket.query.filter_by(status="In Progress").count(),
            "resolved": Ticket.query.filter_by(status="Resolved").count(),
            "critical": Ticket.query.filter(
                Ticket.status.in_(ACTIVE_STATUSES), Ticket.priority == "Critical"
            ).count(),
            "engineers": User.query.filter_by(role="engineer").count(),
            "employees": User.query.filter_by(role="employee").count(),
        }
        recent = Ticket.query.order_by(Ticket.created_at.desc()).limit(8).all()
        recent_activity = ActivityLog.query.order_by(
            ActivityLog.timestamp.desc()
        ).limit(8).all()
        status_rows = db.session.query(
            Ticket.status, db.func.count(Ticket.id)
        ).group_by(Ticket.status).all()
        return render_template(
            "dashboard.html", stats=stats, recent=recent,
            recent_activity=recent_activity,
            tickets_by_status={status: count for status, count in status_rows},
        )

    if _user.is_engineer():
        # Statistics -------------------------------------------------------
        stats = {
            "open_unassigned": Ticket.query.filter_by(status="Open").count(),
            "assigned_to_me": Ticket.query.filter(
                Ticket.assigned_to_id == _user.id,
                Ticket.status.in_(["Assigned", "In Progress"]),
            ).count(),
            "my_resolved": Ticket.query.filter(
                Ticket.assigned_to_id == _user.id, Ticket.status == "Resolved"
            ).count(),
            "critical_open": Ticket.query.filter(
                Ticket.status.in_(ACTIVE_STATUSES), Ticket.priority == "Critical"
            ).count(),
            "total_open": Ticket.query.filter(Ticket.status.in_(ACTIVE_STATUSES)).count(),
        }

        # Queues -----------------------------------------------------------
        unassigned = (
            Ticket.query.filter_by(status="Open")
            .order_by(Ticket.priority_rank.asc(), Ticket.created_at.asc())
            .limit(6)
            .all()
        )
        my_tickets = (
            Ticket.query.filter(
                Ticket.assigned_to_id == _user.id,
                Ticket.status.in_(["Assigned", "In Progress"]),
            )
            .order_by(Ticket.priority_rank.asc(), Ticket.created_at.asc())
            .limit(6)
            .all()
        )
        recent = Ticket.query.order_by(Ticket.created_at.desc()).limit(5).all()

        # Active tickets grouped by priority, for the bar chart.
        rows = (
            db.session.query(Ticket.priority, db.func.count(Ticket.id))
            .filter(Ticket.status.in_(ACTIVE_STATUSES))
            .group_by(Ticket.priority)
            .all()
        )
        tickets_by_priority = {p: n for p, n in rows}

        return render_template(
            "dashboard.html", stats=stats, unassigned=unassigned,
            my_tickets=my_tickets, recent=recent,
            tickets_by_priority=tickets_by_priority,
        )

    # ---------------- Employee view ----------------
    my_tickets = (
        Ticket.query.filter_by(reported_by_id=_user.id)
        .order_by(Ticket.created_at.desc())
        .all()
    )
    stats = {
        "my_active": sum(1 for t in my_tickets if t.is_active()),
        "my_open": sum(1 for t in my_tickets if t.status == "Open"),
        "my_in_progress": sum(1 for t in my_tickets if t.status == "In Progress"),
        "my_resolved": sum(1 for t in my_tickets if t.status == "Resolved"),
        "my_closed": sum(1 for t in my_tickets if t.status == "Closed"),
        "my_total": len(my_tickets),
        "my_critical": sum(
            1 for t in my_tickets if t.is_active() and t.priority == "Critical"
        ),
    }
    return render_template(
        "dashboard.html", stats=stats, my_tickets=my_tickets[:5]
    )


# ---------------------------------------------------------------------------
# Routes — tickets (list + create)
# ---------------------------------------------------------------------------
SORT_COLUMNS = {
    "created": Ticket.created_at,
    "priority": Ticket.priority_rank,
    "title": Ticket.title,
    "status": Ticket.status,
}


@app.route("/tickets")
@login_required
def list_tickets(_user):
    """Searchable, filterable, sortable ticket list.

    Employees only ever see their own tickets; engineers see everything
    but can restrict the view with the 'scope' filter.
    """

    query = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    priority = request.args.get("priority", "")
    status = request.args.get("status", "")
    scope = request.args.get("scope", "all")  # engineers only
    sort = request.args.get("sort", "created")
    order = request.args.get("order", "desc")

    tickets = Ticket.query

    if _user.is_employee():
        tickets = tickets.filter(Ticket.reported_by_id == _user.id)
    elif scope == "mine":
        tickets = tickets.filter(Ticket.assigned_to_id == _user.id)
    elif scope == "unassigned":
        tickets = tickets.filter(Ticket.status == "Open")

    if query:
        like = f"%{query}%"
        tickets = tickets.filter(
            or_(
                Ticket.title.ilike(like),
                Ticket.description.ilike(like),
                Ticket.ticket_number.ilike(like),
            )
        )
    if category:
        tickets = tickets.filter(Ticket.category == category)
    if priority:
        tickets = tickets.filter(Ticket.priority == priority)
    if status:
        tickets = tickets.filter(Ticket.status == status)

    column = SORT_COLUMNS.get(sort, Ticket.created_at)
    column = column.desc() if order == "desc" else column.asc()
    tickets = tickets.order_by(column)

    return render_template(
        "tickets.html",
        tickets=tickets.all(),
        categories=TICKET_CATEGORIES,
        priorities=TICKET_PRIORITIES,
        statuses=TICKET_STATUSES,
        filters={
            "q": query, "category": category, "priority": priority,
            "status": status, "scope": scope, "sort": sort, "order": order,
        },
    )


@app.route("/tickets/new", methods=["GET", "POST"])
@login_required
def new_ticket(_user):
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "")
        priority = request.form.get("priority", "")

        if not title:
            flash("Please provide a short subject line for the ticket.", "danger")
        elif len(title) < 5:
            flash("Subject must be at least 5 characters long.", "danger")
        elif not description:
            flash("Please describe the problem in detail.", "danger")
        elif len(description) < 20:
            flash("Description must be at least 20 characters long.", "danger")
        elif not valid_choice(category, TICKET_CATEGORIES):
            flash("Please select a valid category.", "danger")
        elif not valid_choice(priority, TICKET_PRIORITIES):
            flash("Please select a valid priority.", "danger")
        else:
            ticket = Ticket(
                ticket_number=generate_ticket_number(),
                title=title,
                description=description,
                category=category,
                priority=priority,
                status="Open",
                reported_by_id=_user.id,
            )
            db.session.add(ticket)
            db.session.flush()  # assign the ticket.id before logging
            ticket.log(user_id=_user.id, action="Ticket created")
            db.session.commit()
            flash(
                f"Ticket {ticket.ticket_number} created. Our IT team has been notified.",
                "success",
            )
            return redirect(url_for("ticket_detail", ticket_number=ticket.ticket_number))

    return render_template("ticket_form.html",
                           categories=TICKET_CATEGORIES, priorities=TICKET_PRIORITIES)


# ---------------------------------------------------------------------------
# Routes — single ticket + engineer actions
# ---------------------------------------------------------------------------
@app.route("/tickets/<ticket_number>")
@login_required
def ticket_detail(ticket_number, _user):
    ticket = get_ticket_or_404(ticket_number)

    # Employees can only view their own tickets.
    if _user.is_employee() and ticket.reported_by_id != _user.id:
        abort(403)

    engineers = (
        User.query.filter_by(role="engineer").order_by(User.name.asc()).all()
        if _user.is_engineer() or _user.is_admin() else []
    )
    return render_template(
        "ticket_detail.html", ticket=ticket, engineers=engineers,
        statuses=TICKET_STATUSES,
    )


@app.route("/tickets/<ticket_number>/assign", methods=["POST"])
@engineer_required
def assign_ticket(ticket_number, _user):
    ticket = get_ticket_or_404(ticket_number)
    engineer_id = request.form.get("engineer_id", type=int)

    assignee = db.session.get(User, engineer_id) if engineer_id is not None else None
    if assignee is None or assignee.role != "engineer":
        flash("Please select a valid engineer to assign this ticket to.", "danger")
        return redirect(url_for("ticket_detail", ticket_number=ticket_number))

    previous = ticket.assigned_to
    ticket.assigned_to_id = engineer_id
    ticket.assigned_at = ticket.assigned_at or utcnow()

    if ticket.status == "Open":
        ticket.status = "Assigned"

    name = assignee.name
    ticket.log(
        user_id=_user.id,
        action=f"Assigned to {name}",
        details=f"Previous assignee: {previous.name if previous else 'None'}",
    )
    db.session.commit()
    flash(f"Ticket assigned to {name}.", "success")
    return redirect(url_for("ticket_detail", ticket_number=ticket_number))


@app.route("/tickets/<ticket_number>/status", methods=["POST"])
@engineer_required
def update_status(ticket_number, _user):
    ticket = get_ticket_or_404(ticket_number)
    new_status = request.form.get("status", "")

    if not valid_choice(new_status, TICKET_STATUSES):
        flash("Invalid status selected.", "danger")
        return redirect(url_for("ticket_detail", ticket_number=ticket_number))

    old_status = ticket.status
    ticket.status = new_status

    if new_status == "In Progress" and not ticket.assigned_at:
        ticket.assigned_at = utcnow()

    if new_status == "Resolved" and old_status != "Resolved":
        ticket.resolved_at = utcnow()
    if new_status == "Closed" and old_status != "Closed":
        ticket.closed_at = utcnow()
    if new_status == "Open":
        ticket.assigned_at = None
        ticket.closed_at = None

    ticket.log(user_id=_user.id, action=f"Status changed: {old_status} -> {new_status}")
    db.session.commit()
    flash(f"Ticket status updated to '{new_status}'.", "success")
    return redirect(url_for("ticket_detail", ticket_number=ticket_number))


@app.route("/tickets/<ticket_number>/notes", methods=["POST"])
@engineer_required
def add_notes(ticket_number, _user):
    """Engineer troubleshooting notes that do not change the status."""
    ticket = get_ticket_or_404(ticket_number)
    notes = request.form.get("troubleshooting", "").strip()

    if len(notes) < 5:
        flash("Troubleshooting notes must be at least 5 characters long.", "danger")
        return redirect(url_for("ticket_detail", ticket_number=ticket_number))

    ticket.troubleshooting = notes
    ticket.log(
        user_id=_user.id, action="Troubleshooting notes updated", details=notes
    )
    db.session.commit()
    flash("Troubleshooting notes saved.", "success")
    return redirect(url_for("ticket_detail", ticket_number=ticket_number))


@app.route("/tickets/<ticket_number>/resolve", methods=["POST"])
@engineer_required
def resolve_ticket(ticket_number, _user):
    ticket = get_ticket_or_404(ticket_number)
    resolution = request.form.get("resolution_notes", "").strip()
    troubleshooting = request.form.get("troubleshooting", "").strip()

    if len(resolution) < 10:
        flash("Resolution notes must be at least 10 characters long.", "danger")
        return redirect(url_for("ticket_detail", ticket_number=ticket_number))

    ticket.resolution_notes = resolution
    if troubleshooting:
        ticket.troubleshooting = troubleshooting
    ticket.status = "Resolved"
    ticket.resolved_at = utcnow()
    ticket.log(user_id=_user.id, action="Ticket resolved", details=resolution)
    db.session.commit()
    flash("Ticket marked as resolved. Thank you for the fix!", "success")
    return redirect(url_for("ticket_detail", ticket_number=ticket_number))


@app.route("/tickets/<ticket_number>/close", methods=["POST"])
@engineer_required
def close_ticket(ticket_number, _user):
    ticket = get_ticket_or_404(ticket_number)
    ticket.status = "Closed"
    ticket.closed_at = utcnow()
    ticket.log(user_id=_user.id, action="Ticket closed")
    db.session.commit()
    flash("Ticket closed. It is now archived.", "info")
    return redirect(url_for("ticket_detail", ticket_number=ticket_number))


@app.route("/tickets/<ticket_number>/reopen", methods=["POST"])
@login_required
def reopen_ticket(ticket_number, _user):
    """Re-open a resolved/closed ticket. Owner or engineer may initiate."""
    ticket = get_ticket_or_404(ticket_number)
    if _user.is_employee() and ticket.reported_by_id != _user.id:
        abort(403)
    if ticket.status not in ("Resolved", "Closed"):
        flash("Only resolved or closed tickets can be re-opened.", "warning")
        return redirect(url_for("ticket_detail", ticket_number=ticket_number))

    ticket.status = "Assigned" if ticket.assigned_to_id else "Open"
    ticket.resolved_at = None
    ticket.closed_at = None
    ticket.log(user_id=_user.id, action="Ticket re-opened",
               details="Please review, the issue may still persist.")
    db.session.commit()
    flash("Ticket re-opened and moved back to the active queue.", "warning")
    return redirect(url_for("ticket_detail", ticket_number=ticket_number))


@app.route("/tickets/<ticket_number>/comment", methods=["POST"])
@login_required
def add_comment(ticket_number, _user):
    ticket = get_ticket_or_404(ticket_number)
    if _user.is_employee() and ticket.reported_by_id != _user.id:
        abort(403)

    comment = request.form.get("comment", "").strip()
    if len(comment) < 5:
        flash("Comment must be at least 5 characters long.", "danger")
        return redirect(url_for("ticket_detail", ticket_number=ticket_number))

    role_label = "Employee" if _user.is_employee() else (
        "Admin" if _user.is_admin() else "Engineer"
    )
    ticket.log(user_id=_user.id, action=f"{role_label} comment added", details=comment)
    db.session.commit()
    flash("Comment added to the ticket timeline.", "success")
    return redirect(url_for("ticket_detail", ticket_number=ticket_number))


# ---------------------------------------------------------------------------
# Routes — people directory and administrator functions
# ---------------------------------------------------------------------------
@app.route("/users")
@engineer_required
def users_directory(_user):
    """Employee directory for engineers; complete role directory for admins."""
    users = (User.query.order_by(User.name.asc()).all() if _user.is_admin()
             else User.query.filter_by(role="employee").order_by(User.name.asc()).all())
    return render_template("users.html", employees=users, is_admin=_user.is_admin(),
                           roles=ROLES)


@app.route("/users/<int:user_id>/role", methods=["POST"])
@admin_required
def update_user_role(user_id, _user):
    target = db.session.get(User, user_id)
    if target is None:
        abort(404)
    new_role = request.form.get("role", "")
    if new_role not in ROLES:
        flash("Please select a valid role.", "danger")
    elif target.id == _user.id:
        flash("You cannot change your own administrator role.", "danger")
    elif target.is_admin() and new_role != "admin" and User.query.filter_by(role="admin").count() <= 1:
        flash("The last administrator account cannot be demoted.", "danger")
    elif (target.is_engineer() and new_role != "engineer"
          and Ticket.query.filter(
              Ticket.assigned_to_id == target.id,
              Ticket.status.in_(ACTIVE_STATUSES),
          ).count()):
        flash("Reassign this engineer's active tickets before changing their role.", "danger")
    else:
        old_role = target.role
        target.role = new_role
        db.session.commit()
        flash(f"{target.name}'s role changed from {old_role} to {new_role}.", "success")
    return redirect(url_for("users_directory"))


@app.route("/reports")
@admin_required
def reports(_user):
    """System-wide ticket and workforce metrics calculated from stored data."""
    total = Ticket.query.count()
    active_critical = Ticket.query.filter(
        Ticket.status.in_(ACTIVE_STATUSES), Ticket.priority == "Critical"
    ).count()
    status_rows = db.session.query(Ticket.status, db.func.count(Ticket.id)).group_by(Ticket.status).all()
    priority_rows = db.session.query(Ticket.priority, db.func.count(Ticket.id)).group_by(Ticket.priority).all()
    category_rows = db.session.query(Ticket.category, db.func.count(Ticket.id)).group_by(Ticket.category).order_by(db.func.count(Ticket.id).desc()).all()
    recent_activity = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(12).all()
    return render_template(
        "reports.html", total=total,
        tickets_by_status={status: count for status, count in status_rows},
        tickets_by_priority={priority: count for priority, count in priority_rows},
        tickets_by_category=category_rows, recent_activity=recent_activity,
        active_critical=active_critical,
        engineers=User.query.filter_by(role="engineer").count(),
        employees=User.query.filter_by(role="employee").count(),
    )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, title="Access denied",
                           message="You do not have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, title="Page not found",
                           message="The page you are looking for does not exist."), 404


@app.errorhandler(400)
def bad_request(_e):
    return render_template("error.html", code=400, title="Bad request",
                           message="The request could not be processed. Please go back and try again."), 400


@app.errorhandler(500)
def server_error(_e):
    db.session.rollback()
    return render_template("error.html", code=500, title="Server error",
                           message="Something went wrong on our side. Please try again later."), 500


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="127.0.0.1", port=5000, debug=False)
