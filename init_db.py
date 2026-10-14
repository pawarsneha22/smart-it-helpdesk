"""
init_db.py
----------
Creates missing SQLite tables and seeds sample data only when the database
contains no users or tickets. Existing records are never deleted or replaced.

Usage:
    python init_db.py            # create missing tables; seed only a new database
    python init_db.py --no-seed  # create missing tables without sample data
"""

import sys
from datetime import timedelta

from app import app
from models import ActivityLog, Ticket, User, db, utcnow


def build_users():
    """Create engineers and employees with hashed passwords."""

    engineers = [
        ("Anita Rao", "anita@techcorp.com", "Engineer@123", "IT"),
        ("Vikram Nair", "vikram@techcorp.com", "Engineer@123", "IT"),
    ]
    employees = [
        ("Rahul Sharma", "rahul@techcorp.com", "Employee@123", "Finance", "EMP-FIN-1024"),
        ("Priya Patel", "priya@techcorp.com", "Employee@123", "HR", "EMP-HR-2087"),
        ("Aman Verma", "aman@techcorp.com", "Employee@123", "Sales", "EMP-SLS-3310"),
        ("Meera Iyer", "meera@techcorp.com", "Employee@123", "Marketing", "EMP-MKT-4102"),
    ]

    created = []
    for name, email, pwd, dept in engineers:
        user = User(name=name, email=email, department=dept, role="engineer", password=pwd)
        db.session.add(user)
        created.append(user)
    for name, email, pwd, dept, code in employees:
        user = User(name=name, email=email, department=dept,
                    role="employee", employee_code=code, password=pwd)
        db.session.add(user)
        created.append(user)
    db.session.flush()
    return created


def seed_tickets(users):
    """Insert a realistic spread of tickets across categories, priorities
    and lifecycle stages, each with a matching activity history."""

    now = utcnow()
    who = {u.email: u for u in users}

    def ts(days=0, hours=0, minutes=0):
        return now - timedelta(days=days, hours=hours, minutes=minutes)

    def make(number, reporter_email, title, description, category, priority,
             status, assigned_email=None,
             created=None, assigned_at=None, resolved_at=None, closed_at=None,
             troubleshooting="", resolution="", events=None):
        """Create one ticket plus an ordered list of ActivityLog entries."""

        reporter = who[reporter_email]
        assigned = who[assigned_email] if assigned_email else None

        ticket = Ticket(
            ticket_number=number,
            title=title,
            description=description,
            category=category,
            priority=priority,
            status=status,
            reported_by_id=reporter.id,
            assigned_to_id=assigned.id if assigned else None,
            created_at=created or ts(hours=2),
            assigned_at=assigned_at,
            resolved_at=resolved_at,
            closed_at=closed_at,
            troubleshooting=troubleshooting or None,
            resolution_notes=resolution or None,
        )
        db.session.add(ticket)
        db.session.flush()

        events = events or []
        for when, actor_email, action, details in events:
            db.session.add(ActivityLog(
                ticket_id=ticket.id,
                user_id=who[actor_email].id,
                action=action,
                details=details,
                timestamp=when,
            ))
        return ticket

    # ------------------------------- 1. Resolved: laptop boot failure ------
    make(
        "TKT-2026-0001", "rahul@techcorp.com",
        "Laptop freezes with black screen after Windows update",
        "After installing the KB5034xxx cumulative update last night my laptop "
        "powers on but stays on a black screen. The keyboard backlight turns on "
        "and the fan spins, but the display never lights up. This blocks my "
        "daily work, especially month-end closing in Finance.",
        "Hardware", "High", "Resolved", "anita@techcorp.com",
        created=ts(days=2, hours=7), assigned_at=ts(days=2, hours=7, minutes=50),
        resolved_at=ts(days=2, hours=9),
        troubleshooting="Booted into Safe Mode via Windows Recovery (WinRE). "
                        "Uninstalled the recent cumulative update using "
                        "wusa /uninstall /kb:5034xxx. Rebooted normally.",
        resolution="Display driver conflict caused by the update. The update was "
                   "rolled back and deferred for 30 days. Display now boots "
                   "normally; recommended automatic quality updates only.",
        events=[
            (ts(days=2, hours=7), "rahul@techcorp.com", "Ticket created",
             "Reporter prioritised as High due to month-end work."),
            (ts(days=2, hours=7, minutes=50), "anita@techcorp.com",
             "Assigned to Anita Rao", "Previous assignee: None"),
            (ts(days=2, hours=8, minutes=20), "anita@techcorp.com",
             "Status changed: Assigned -> In Progress", None),
            (ts(days=2, hours=8, minutes=20), "anita@techcorp.com",
             "Troubleshooting notes updated",
             "Booted into Safe Mode via Windows Recovery (WinRE). Uninstalled "
             "the recent cumulative update."),
            (ts(days=2, hours=9), "anita@techcorp.com", "Ticket resolved",
             "Update rolled back; display boots normally."),
        ],
    )

    # ------------------------------- 2. In Progress: Wi-Fi ----------------
    make(
        "TKT-2026-0002", "priya@techcorp.com",
        "Cannot connect to the guest Wi-Fi in Block C",
        "Every device in our conference room keeps dropping the 'TechCorp-Guest' "
        "network. Connecting reports 'Cannot join network' even though the "
        "password is correct. Same issue on two laptops and one phone.",
        "Network", "Medium", "In Progress", "anita@techcorp.com",
        created=ts(days=1, hours=4), assigned_at=ts(days=1, hours=2),
        troubleshooting="Checked AP controller logs; Block C access point "
                        "rebooted remotely, client isolation re-enabled. "
                        "Waiting on user retest.",
        events=[
            (ts(days=1, hours=4), "priya@techcorp.com", "Ticket created", None),
            (ts(days=1, hours=2), "anita@techcorp.com", "Assigned to Anita Rao",
             "Previous assignee: None"),
            (ts(days=1, hours=1), "anita@techcorp.com",
             "Status changed: Assigned -> In Progress", None),
            (ts(days=1, hours=1), "anita@techcorp.com",
             "Troubleshooting notes updated",
             "Checked AP controller logs; Block C AP rebooted."),
            (ts(hours=3), "anita@techcorp.com", "Engineer comment added",
             "Could you retry now and confirm if the network holds for 10 minutes?"),
        ],
    )

    # ------------------------------- 3. Open, unassigned: Adobe license ----
    make(
        "TKT-2026-0003", "aman@techcorp.com",
        "Adobe Acrobat Pro shows 'License has expired' error",
        "When opening any PDF, Acrobat Pro pops up a dialog saying the product "
        "license has expired with error 20. The software was working yesterday "
        "and I have not changed anything. I need to fill and e-sign sales "
        "contracts daily.",
        "Software", "Low", "Open", None,
        created=ts(hours=6),
        events=[
            (ts(hours=6), "aman@techcorp.com", "Ticket created",
             "Low priority, another PDF viewer works meanwhile."),
        ],
    )

    # ------------------------------- 4. Assigned: HR printer --------------
    make(
        "TKT-2026-0004", "priya@techcorp.com",
        "HR department printer shows paper jam although tray is empty",
        "The Ricoh MPC3504 in the HR corridor reports 'Paper jam inside' "
        "continuously. I have opened and checked the left and rear panels - "
        "there is no paper stuck. Tried power cycling twice.",
        "Printer", "Medium", "Assigned", "vikram@techcorp.com",
        created=ts(hours=26), assigned_at=ts(hours=20),
        events=[
            (ts(hours=26), "priya@techcorp.com", "Ticket created", None),
            (ts(hours=20), "vikram@techcorp.com", "Assigned to Vikram Nair",
             "Previous assignee: None"),
        ],
    )

    # ------------------------------- 5. Assigned: Outlook locked ----------
    make(
        "TKT-2026-0005", "meera@techcorp.com",
        "Outlook account locked after repeated failed password attempts",
        "Outlook on my desktop now refuses to send and receive with the error "
        "'Sign in again to connect to your account'. The IT single-sign-on page "
        "says my account is temporarily locked. I am on a deadline to circulate "
        "the campaign reports.",
        "Account/Login", "Critical", "Assigned", "anita@techcorp.com",
        created=ts(hours=5), assigned_at=ts(hours=4),
        events=[
            (ts(hours=5), "meera@techcorp.com", "Ticket created",
             "Critical: account locked, blocks all campaign reporting."),
            (ts(hours=4), "anita@techcorp.com", "Assigned to Anita Rao",
             "Previous assignee: None"),
            (ts(hours=3), "anita@techcorp.com", "Engineer comment added",
             "Unlocked the account in Azure AD and sent a password-reset link.")
        ],
    )

    # ------------------------------- 6. In Progress: phishing -------------
    make(
        "TKT-2026-0006", "rahul@techcorp.com",
        "Suspicious phishing email impersonating the IT Helpdesk",
        "Received an email from 'TechCorp IT Helpdesk <support-techcorp@outlook.com>' "
        "asking me to verify my password by 5 PM 'or your mailbox will be "
        "disabled'. The button links to a non-TechCorp URL. I did NOT click it.",
        "Security", "Critical", "In Progress", "vikram@techcorp.com",
        created=ts(hours=9), assigned_at=ts(hours=8),
        troubleshooting="Analysed headers with Microsoft Defender; added sender "
                        "domain to blocked list. Quarantined duplicate campaign "
                        "from same template. Advising colleagues to report any "
                        "similar mail via Report Message add-in.",
        events=[
            (ts(hours=9), "rahul@techcorp.com", "Ticket created",
             "Possible phishing reported by user."),
            (ts(hours=8), "vikram@techcorp.com", "Assigned to Vikram Nair",
             "Previous assignee: None"),
            (ts(hours=8), "vikram@techcorp.com",
             "Status changed: Assigned -> In Progress", None),
            (ts(hours=6), "vikram@techcorp.com", "Troubleshooting notes updated",
             "Sender blocked and campaign quarantined."),
            (ts(hours=2), "vikram@techcorp.com", "Engineer comment added",
             "Good catch - no compromise detected on your mailbox. Blocking "
             "the sender domain now."),
        ],
    )

    # ------------------------------- 7. Resolved: shared drive save -------
    make(
        "TKT-2026-0007", "aman@techcorp.com",
        "Excel fails to save to the shared Sales drive",
        "Excel shows 'A file with the name you supplied already exists' when "
        "saving to \\\\fs1\\sales\\quotations. The file does not exist yet and "
        "is not open anywhere else. Happens for every new workbook.",
        "Software", "Medium", "Resolved", "anita@techcorp.com",
        created=ts(days=4, hours=3), assigned_at=ts(days=4, hours=2),
        resolved_at=ts(days=3, hours=21),
        troubleshooting="Reproduced with a blank workbook. Cleared Excel "
                        "unhide/author cache and reset the Office activation "
                        "state. Verified folder permissions on the share.",
        resolution="Corrupt Excel personal.xlsx cache prevented reliable "
                   "saving. Removed the cache files; Save now works and Excel "
                   "was rebuilt once via Office repair.",
        events=[
            (ts(days=4, hours=3), "aman@techcorp.com", "Ticket created", None),
            (ts(days=4, hours=2), "anita@techcorp.com", "Assigned to Anita Rao",
             "Previous assignee: None"),
            (ts(days=4, hours=1), "anita@techcorp.com",
             "Status changed: Assigned -> In Progress", None),
            (ts(days=3, hours=23), "anita@techcorp.com",
             "Troubleshooting notes updated",
             "Reproduced with a blank workbook. Cleared Excel cache."),
            (ts(days=3, hours=21), "anita@techcorp.com", "Ticket resolved",
             "Cleared corrupt personal.xlsx cache, Office repair run."),
        ],
    )

    # ------------------------------- 8. Open, unassigned: VPN -------------
    make(
        "TKT-2026-0008", "meera@techcorp.com",
        "New joiner cannot access VPN after password reset",
        "Our new graphic designer set up the FortiClient VPN but gets "
        "'Authentication failed' on connect. The password was reset last night "
        "because of the new-hire onboarding checklist.",
        "Account/Login", "Low", "Open", None,
        created=ts(hours=14),
        events=[
            (ts(hours=14), "meera@techcorp.com", "Ticket created",
             "Colleague not productive until VPN works."),
        ],
    )

    # ------------------------------- 9. Closed: mouse double click --------
    make(
        "TKT-2026-0009", "rahul@techcorp.com",
        "Logitech mouse double-clicks when I click once",
        "The finance team's Logitech B100 mouse double clicks on single clicks. "
        "Selecting text and dragging files is nearly impossible. Two users have "
        "reported the same on their mice.",
        "Hardware", "Low", "Closed", "vikram@techcorp.com",
        created=ts(days=12), assigned_at=ts(days=12, hours=1),
        resolved_at=ts(days=11, hours=20), closed_at=ts(days=10),
        troubleshooting="Swap-tested the mouse on another machine; fault "
                        "reproduces, confirming hardware failure.",
        resolution="Three mice replaced from stock under warranty. "
                   "Replacement log updated.",
        events=[
            (ts(days=12), "rahul@techcorp.com", "Ticket created", None),
            (ts(days=12, hours=1), "vikram@techcorp.com", "Assigned to Vikram Nair",
             "Previous assignee: None"),
            (ts(days=11, hours=23), "vikram@techcorp.com",
             "Status changed: Assigned -> In Progress", None),
            (ts(days=11, hours=20), "vikram@techcorp.com", "Ticket resolved",
             "Mice replaced under warranty."),
            (ts(days=10), "vikram@techcorp.com", "Ticket closed", None),
        ],
    )

    # ------------------------------- 10. Open: Slack notifications --------
    make(
        "TKT-2026-0010", "priya@techcorp.com",
        "Slack notifications stop arriving on mobile after lunch",
        "Every day after about 2 PM the Slack app on my iPhone stops sending "
        "push notifications. Notifications resume only after I open the app. "
        "All my DMs and channels matter for event coordination.",
        "Software", "Medium", "Open", None,
        created=ts(hours=7),
        events=[
            (ts(hours=7), "priya@techcorp.com", "Ticket created",
             "Investigate app-level or network-level cause."),
        ],
    )

    # ------------------------------- 11. In Progress: slow boot -----------
    make(
        "TKT-2026-0011", "rahul@techcorp.com",
        "Finance reporting laptop extremely slow to boot and open Excel",
        "Boot up takes 6-8 minutes and opening any workbook takes another "
        "minute. Task Manager shows CPU at 100% with 'Antimalware Service "
        "Executable' and 200+ Excel tracker files. Machine is 4 years old.",
        "Hardware", "High", "In Progress", "vikram@techcorp.com",
        created=ts(days=1, hours=9), assigned_at=ts(days=1, hours=7),
        troubleshooting="Running full malware scan. Reviewing startup "
                        "programs and RAM usage (only 8 GB installed). "
                        "Considering SSD upgrade recommendation.",
        events=[
            (ts(days=1, hours=9), "rahul@techcorp.com", "Ticket created", None),
            (ts(days=1, hours=7), "vikram@techcorp.com", "Assigned to Vikram Nair",
             "Previous assignee: None"),
            (ts(days=1, hours=5), "vikram@techcorp.com",
             "Status changed: Assigned -> In Progress", None),
            (ts(days=1, hours=5), "vikram@techcorp.com",
             "Troubleshooting notes updated",
             "Full scan running; RAM usage review in progress."),
        ],
    )

    # ------------------------------- 12. Resolved: MFA reset -------------
    make(
        "TKT-2026-0012", "aman@techcorp.com",
        "Need MFA reset - authenticator app lost after phone replacement",
        "Changed phones over the weekend and the Microsoft Authenticator app "
        "did not restore. I cannot approve sign-in prompts and I am locked out "
        "of my own machine. Sales pipeline dashboard is blocked.",
        "Account/Login", "High", "Resolved", "anita@techcorp.com",
        created=ts(days=6, hours=5), assigned_at=ts(days=6, hours=4),
        resolved_at=ts(days=6, hours=3),
        troubleshooting="Verified identity via employee ID and manager "
                        "approval. Temporarily disabled MFA, re-registered "
                        "the new device, re-enabled MFA.",
        resolution="MFA re-registered to the new phone. User verified a test "
                   "sign-in successfully. Reminded to back up authenticator "
                   "via cloud backup next time.",
        events=[
            (ts(days=6, hours=5), "aman@techcorp.com", "Ticket created", None),
            (ts(days=6, hours=4), "anita@techcorp.com", "Assigned to Anita Rao",
             "Previous assignee: None"),
            (ts(days=6, hours=4), "anita@techcorp.com",
             "Status changed: Assigned -> In Progress", None),
            (ts(days=6, hours=3), "anita@techcorp.com", "Ticket resolved",
             "MFA re-registered to new phone."),
        ],
    )


def main():
    seed = "--no-seed" not in sys.argv

    with app.app_context():
        db.create_all()

        if not seed:
            print("Database schema created (no sample data).")
            return

        if User.query.first() or Ticket.query.first():
            print("Existing users or tickets found; database records were preserved.")
            print("Sample data was not inserted.")
            return

        users = build_users()
        seed_tickets(users)
        db.session.commit()

        engineers = User.query.filter_by(role="engineer").count()
        employees = User.query.filter_by(role="employee").count()
        tickets = Ticket.query.count()
        activities = ActivityLog.query.count()

        print("Database initialised successfully.")
        print(f"  Users      : {engineers} engineers + {employees} employees")
        print(f"  Tickets    : {tickets}")
        print(f"  Activities : {activities}")
        print()
        print("Demo logins:")
        print("  Engineer : anita@techcorp.com  / Engineer@123")
        print("  Employee : rahul@techcorp.com / Employee@123")


if __name__ == "__main__":
    main()
