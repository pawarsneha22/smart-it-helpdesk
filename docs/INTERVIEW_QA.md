# Smart IT Helpdesk — Interview Q&A

Questions a campus interviewer is most likely to ask about this project,
with concise, confident answers. Say these aloud a few times before the
interview so they feel natural, then adapt the details to your own words.

---

## 1. Why did you build this project?
> As a final-year IT student I wanted one portfolio piece that shows the
> *actual job* of an IT Support Engineer — not just a CRUD demo. So I built a
> ticket-management system with a realistic workflow: employees report issues,
> engineers triage, assign, troubleshoot, resolve and document them. It
> exercises databases, authentication, full-stack web development, validation
> and audit logging, which maps 1:1 to day-to-day helpdesk tools like Zendesk
> or ServiceNow.

## 2. Walk me through the architecture.
> Three layers. **Presentation**: Jinja2 templates + Bootstrap 5 + a bit of
> vanilla JS for client-side validation. **Application**: Flask routes in
> `app.py` that hold authentication, business rules (lifecycle, SLA, timing)
> and validation. **Data**: SQLAlchemy ORM over SQLite with three normalized
> tables — `ticket_user`, `ticket`, `activity_log`. A request flows:
> browser → route → ORM query → template → rendered HTML.

## 3. How do users authenticate and how do you protect passwords?
> Sessions. On login I store `user_id` in the Flask session and use
> `@login_required` / `@engineer_required` decorators to gate routes.
> Passwords are never stored — Werkzeug's `generate_password_hash()` stores a
> PBKDF2-SHA256 hash, and `check_password_hash()` verifies on login.

## 4. What stops an employee from seeing someone else's tickets?
> Two layers. First, in `list_tickets` an employee's query is always filtered
> by `reported_by_id == current_user.id`. Second, the detail route re-checks
> ownership and otherwise returns **403**. Even if someone guesses a URL like
> `/tickets/TKT-2026-0005`, they get denied. Engineers see a `scope` filter
> (all / mine / unassigned) instead.

## 5. How did you implement the activity/audit log?
> Every mutation writes a row to `activity_log` with the ticket_id, the user
> who acted, an action string (e.g. "Status changed: Assigned -> In Progress")
> and a timestamp. I used a helper `ticket.log(...)` so every route records
> history consistently. The detail page renders these rows newest-first as a
> timeline. That mirrors how enterprise tools keep an immutable audit trail.

## 6. How does the ticket number get generated?
> `generate_ticket_number()` reads the highest existing ticket id plus one and
> formats it as `TKT-<year>-0001`. Human-readable, unique, and sortable. In a
> production system you'd use a database sequence or an ID office instead.

## 7. How do you track response and resolution time?
> The ticket stores `created_at`, `assigned_at` and `resolved_at`. Response
> time = `assigned_at − created_at` (first assignment = first response), and
> resolution time = `resolved_at − created_at`. A Jinja filter converts seconds
> to "3h 25m". I also show an SLA hint per priority (Critical = 1h, High = 4h,
> Medium = 8h, Low = 24h) so engineers can see at a glance if a ticket is at risk.

## 8. How do search, filter and sort work?
> Single `/tickets` route reads query-string params. I build the query with
> SQLAlchemy: `ilike` for the search term, `==` equality for category/priority/
> status, and a dynamic `order_by` using a lookup table of column
> expressions. All filters persist in the form so the user can tweak them.
> `priority_rank`, a `hybrid_property` backed by a SQL `CASE` expression,
> lets me sort genuinely by importance in the database, not in Python.

## 9. What validation did you add — server-side and client-side?
> Server side: required fields, title ≥ 5 chars, description ≥ 20 chars,
> resolution notes ≥ 10 chars, category/priority must come from the allowed
> list, email must match a basic regex, password ≥ 8 chars, confirm-password
> match, duplicate-email check. Client side: JavaScript runs the same core
> checks before submitting so users get instant feedback. Both are needed
> because client-side checks can be bypassed.

## 10. What security concerns did you handle?
> Password hashing, CSRF tokens on every POST (checked in `before_request`),
> role-based access control on every sensitive route, employee/engineer data
> scoping, restricted `next` redirects, and safe rendering via Jinja which
> auto-escapes all user content (no XSS). Sensitive config like the secret key
> is overridable through environment variables.

## 11. Why SQLAlchemy instead of raw SQL?
> Raw SQL is fine, but the ORM gives me portability between databases, a
> readable schema, relationship loading, and the hybrid property for computed
> sort/status logic. SQLite keeps the demo zero-config; swapping to PostgreSQL
> would just change `config.py`.

## 12. Why a separate activity_log table instead of storing history in the ticket?
> Because history is *multi-valued* — a ticket has many events. Storing them
> in one row would mean denormalizing (JSON blobs, repeated columns). A
> separate table keeps the data normalized, makes the timeline trivial to
> query, and gives a natural path to reporting ("average time to first
> response last month").

## 13. How would you add a feature like email notification on assignment?
> I'd add a notification job that reads new `activity_log` rows or a
> `notified_at` column on the ticket, and send an SMTP email to the assignee.
> For a campus-scale implementation I'd use Flask-Mail with a background
> worker (or just a task queue) so requests don't block on the mail server.

## 14. How would you scale this beyond a demo?
> Move the DB to PostgreSQL and add migration tooling (Alembic). Use a proper
> API layer (Flask-RESTful) so the UI is a frontend for the same API. Add
> pagination to the ticket list, full-text search (PostgreSQL FTS / SQLite
> FTS5), and role-based dashboards with real reporting. Cache static reads.
> Move the secret key to environment variables.

## 15. What was the hardest part?
> (Personalize — source of truth.) *Example:* "Making sure status/timestamp
> consistency was right — e.g. assigning a ticket that is *In Progress* must
> not overwrite the original `assigned_at`, and re-opening must clear
> `resolved_at`. I handled it with targeted, clearly-named routes and covered
> it in tests so a future change can't silently break the workflow."

## 16. What did you learn that you'll use as an IT Support Engineer?
> Submitting an issue as an employee taught me how good ticket descriptions
> make troubleshooting dramatically faster. Building the engineer side taught
> me triage thinking: prioritize by impact, document every step, and resolve
> with a reproducible fix rather than a one-time workaround.