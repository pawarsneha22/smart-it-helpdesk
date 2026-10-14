# Smart IT Helpdesk

A role-based Flask IT support portal for employees, IT engineers, and administrators. Employees submit and track requests, engineers manage the support queue, and administrators review system-wide activity and manage account roles.

## Features

- Employee and engineer dashboards with metrics derived from current ticket records.
- Admin dashboard, system reports, complete ticket visibility, and role management.
- Search, category/priority/status filters, scope filters for engineers, and sorting.
- Ticket assignment, status updates, troubleshooting notes, resolution details, close/reopen workflow, and an audit timeline.
- Responsive premium interface with mobile navigation, accessible forms, inline icons, keyboard support, and reduced-motion handling.
- Public registration always creates an employee account. Admin accounts are provisioned from a local command-line script.
- CSRF checking on every POST, server-side validation, password hashing, and role checks on protected routes.

## Roles and access

| Role | Access |
| --- | --- |
| Employee | Create tickets; list, search, filter, comment on, and view only tickets they reported; reopen their resolved/closed tickets. |
| IT Engineer | View all tickets, filter to assigned or unassigned work, assign tickets, update status, add troubleshooting and resolution notes, and close tickets. Can view the employee directory. |
| Admin | View all tickets and global dashboard metrics; access audit-based reports; view all users and change other users’ roles. Admins cannot change their own role, and the last-admin safeguard prevents removing the final admin. Admins may also perform engineer ticket actions. |

Public self-registration does not accept or use a submitted role. The first administrator must be created from the server console with `create_admin.py`.

## Technology

- Python 3.10+
- Flask 3 and Flask-SQLAlchemy
- SQLite by default
- Jinja templates, Bootstrap 5 utilities, custom CSS, and vanilla JavaScript
- Pytest

## Windows PowerShell setup

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python init_db.py
```

`init_db.py` creates missing tables and inserts its demo dataset only when the database contains no users or tickets. It does not drop tables or replace existing records. For an empty schema without sample records, run:

```powershell
python init_db.py --no-seed
```

Create an administrator interactively. The password is not echoed and must be at least 12 characters:

```powershell
python create_admin.py
```

Run the app:

```powershell
python app.py
```

Open <http://127.0.0.1:5000>. Debug mode is off by default. To explicitly enable it for local development only, set `FLASK_DEBUG=1` in the current PowerShell session before running the app.

## Configuration

- `SECRET_KEY`: set a long random secret for deployments and whenever sessions must survive application restarts. Local runs generate an ephemeral secret if omitted.
- `DATABASE_URL`: optional SQLAlchemy database URI. The default is `instance/helpdesk.db`.
- `FLASK_DEBUG`: debug is disabled unless explicitly set to `1`, `true`, or `yes`.

The user role is stored in the existing `ticket_user.role` column. Admin support does not require a database schema change. The updated initializer uses additive `create_all()` behavior; it does not migrate or reset existing data.

## Tests

```powershell
python -m pytest -v
```

The test suite uses an in-memory SQLite database and verifies employee ownership boundaries, engineer workflows, admin reports and role updates, registration role safety, CSRF enforcement, ticket lifecycle, search, and filters. It does not alter `instance/helpdesk.db`.

## Project structure

```text
app.py                 Flask routes, validation, and access control
models.py              User, Ticket, and ActivityLog models
config.py              Database and runtime settings
init_db.py             Non-destructive schema/sample-data setup
create_admin.py        Console-only administrator provisioning
templates/             Jinja pages and reusable icon/badge macros
static/css/style.css   Responsive design system
static/js/main.js      Mobile navigation and progressive enhancements
tests/                 In-memory workflow and authorization tests
instance/              Local SQLite database
```

## License and attribution

No `LICENSE` file or upstream repository attribution was present in this project copy during review. Confirm the original source and its license before redistributing this project or representing it as open source.
