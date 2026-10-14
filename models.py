"""
models.py
---------
SQLAlchemy data models for the Helpdesk application.

Three tables:

  ticket_user   - employees who report issues and engineers who fix them
  ticket        - the support ticket with its full lifecycle
  activity_log  - an audit trail of every action performed on a ticket

The status / priority / category values are stored as plain strings to
keep the SQLite schema simple and readable. All allowed values are
declared as module-level constants so the rest of the application
(and the templates) can share a single source of truth.
"""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.security import check_password_hash, generate_password_hash

# Shared constants -----------------------------------------------------------
ROLES = ["employee", "engineer", "admin"]
DEPARTMENTS = ["IT", "HR", "Finance", "Sales", "Marketing", "Operations", "Admin"]

TICKET_CATEGORIES = [
    "Hardware",
    "Software",
    "Network",
    "Printer",
    "Account/Login",
    "Security",
    "Other",
]

TICKET_PRIORITIES = ["Low", "Medium", "High", "Critical"]

TICKET_STATUSES = ["Open", "Assigned", "In Progress", "Resolved", "Closed"]

# States that count as "still being worked on".
ACTIVE_STATUSES = ["Open", "Assigned", "In Progress"]

# Numeric weight of each priority so tickets can be sorted by importance.
PRIORITY_RANK = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}

db = SQLAlchemy()


def utcnow() -> datetime:
    """Return a timezone-naive UTC timestamp (clean for SQLite storage)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_string(value) -> str:
    """Safely render a database value as text."""
    return "" if value is None else str(value)


# Ticket ---------------------------------------------------------------------
class Ticket(db.Model):
    __tablename__ = "ticket"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False)

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)

    category = db.Column(db.String(20), nullable=False, default="Other")
    priority = db.Column(db.String(10), nullable=False, default="Medium")
    status = db.Column(db.String(12), nullable=False, default="Open")

    # People involved
    reported_by_id = db.Column(db.Integer, db.ForeignKey("ticket_user.id"), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("ticket_user.id"), nullable=True)

    reported_by = db.relationship("User", foreign_keys=[reported_by_id])
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])

    # Lifecycle timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    assigned_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    # Work notes written by the support engineer.
    troubleshooting = db.Column(db.Text, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)

    # One ticket -> many history entries.
    activity = db.relationship(
        "ActivityLog",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="ActivityLog.timestamp.asc()",
    )

    # --- Convenience helpers used by routes and templates -------------------
    def log(self, user_id, action, details=None):
        """Append an entry to this ticket's activity log."""
        entry = ActivityLog(ticket_id=self.id, user_id=user_id, action=action, details=details)
        db.session.add(entry)

    def response_time_seconds(self):
        """Time between creation and first engineer assignment/sign-off."""
        if self.assigned_at and self.created_at:
            return (self.assigned_at - self.created_at).total_seconds()
        return None

    def resolution_time_seconds(self):
        """Total time from creation to resolution."""
        if self.resolved_at and self.created_at:
            return (self.resolved_at - self.created_at).total_seconds()
        return None

    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @hybrid_property
    def priority_rank(self) -> int:
        """Queryable numeric weight used for 'triage' sorting."""
        return PRIORITY_RANK.get(self.priority, 0)

    @priority_rank.expression
    def priority_rank(cls):
        return case(PRIORITY_RANK, value=cls.priority, else_=0)

    def __repr__(self):
        return f"<Ticket {self.ticket_number} [{self.status}] {self.title!r}>"


# User -----------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "ticket_user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="employee")
    department = db.Column(db.String(30), nullable=False, default="IT")
    employee_code = db.Column(db.String(20), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    # Tickets this user reported. (Read-only convenience collection.)
    reported_tickets = db.relationship(
        "Ticket", foreign_keys=[Ticket.reported_by_id], overlaps="reported_by"
    )

    def __init__(self, **kwargs):
        # Store the raw password temporarily until set_password() runs.
        raw = kwargs.pop("password", None)
        super().__init__(**kwargs)
        if raw:
            self.set_password(raw)

    def set_password(self, raw_password: str) -> None:
        """Hash a plain password using PBKDF2 (via werkzeug)."""
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Verify a plain password against the stored hash."""
        return check_password_hash(self.password_hash, raw_password)

    def is_engineer(self) -> bool:
        return self.role == "engineer"

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_employee(self) -> bool:
        return self.role == "employee"

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


# Activity log ---------------------------------------------------------------
class ActivityLog(db.Model):
    __tablename__ = "activity_log"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("ticket.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("ticket_user.id"), nullable=False)
    action = db.Column(db.String(120), nullable=False)   # e.g. "Status changed to Resolved"
    details = db.Column(db.Text, nullable=True)          # optional note / description
    timestamp = db.Column(db.DateTime, nullable=False, default=utcnow)

    ticket = db.relationship("Ticket", back_populates="activity")
    user = db.relationship("User")

    def __repr__(self):
        return f"<ActivityLog #{self.id} {self.action} on ticket {self.ticket_id}>"
