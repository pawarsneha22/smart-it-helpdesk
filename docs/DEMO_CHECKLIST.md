# Demo & Screenshot Checklist

Use this walkthrough to produce a clean, professional demo video or a set of
screenshots for your README / GitHub page. Number the captures in the order
below so the story flows: *an employee reports a problem → an engineer fixes it → it gets closed.*

---

## Phase 0 — Preparation
- [ ] Run `python init_db.py` to reset sample data to a known state.
- [ ] Run `python app.py` and open `http://127.0.0.1:5000`.

## Phase 1 — Authentication (Employee)
1. **Login page** — capture the clean card layout with demo credentials listed.
2. **Register page** — create a brand-new employee account (explains self-service).
3. **Employee dashboard** — capture the stat cards (Active / Resolved / Closed /
   Total / Critical) and the "My recent tickets" table.
4. **Invalid login** — show the "Invalid email or password" flash message
   (demonstrates error handling).

## Phase 2 — Raising a ticket (Employee)
5. **Report a Problem form** — capture the form with categories, priorities and the
   description guidance.
6. **Validation in action** — submit an empty/short description and capture the
   error flash message.
7. **Ticket created** — capture the success message with the auto-generated ID,
   e.g. `TKT-2026-0013`.
8. **Ticket detail (employee view)** — description, activity timeline start.

## Phase 3 — Engineering workflow (Engineer)
9. **Engineer login** (anita@techcorp.com / Engineer@123).
10. **Engineer dashboard** — capture: unassigned triage queue, cards (Open,
    Assigned to me, Resolved by me, Critical, Total active) and the priority
    bar chart.
11. **Ticket list with filters** — capture search + category/priority/status
    dropdowns and a filtered result set (e.g. category = Network).
12. **Ticket detail (engineer view)** — capture the "Engineer actions" panel:
    assign select, status select, resolve form.
13. **Assign the ticket** — show the flash "assigned to …", the status moving to *Assigned*,
    and the activity-log entry.
14. **Add troubleshooting notes** — show notes saved to the timeline.
15. **Mark as resolved** — show resolution notes + `Resolved` badge + resolution
    time in the right column.
16. **Close the ticket** — show the *Closed* badge.

## Phase 4 — Nice extras
17. **Activity timeline** — a fully built-out ticket (e.g. `TKT-2026-0006`
    phishing) showing every action chronologically.
18. **403 page** — try to open someone else's ticket as an employee.
19. **Search** — search for `VPN`, `printer` or a ticket number.
20. **Sort by priority (Critical first)** — capture the re-ordered list.
21. **Mobile view** — narrow the browser window to show responsiveness.

---

## Suggested screenshot filenames (for README)

```
docs/screenshots/01-login.png
docs/screenshots/02-employee-dashboard.png
docs/screenshots/03-create-ticket.png
docs/screenshots/04-ticket-detail-employee.png
docs/screenshots/05-engineer-dashboard.png
docs/screenshots/06-ticket-list-filters.png
docs/screenshots/07-engineer-actions.png
docs/screenshots/08-activity-timeline.png
docs/screenshots/09-resolved-ticket.png
```

Add a **Screenshots** section to the README:

```markdown
## Screenshots
| | |
|:---:|:---:|
| ![](docs/screenshots/02-employee-dashboard.png) | ![](docs/screenshots/05-engineer-dashboard.png) |
| Engineer dashboard | Employee dashboard |
```

---

## Live demo script (60–90 seconds)

1. Log in as **Rahul Sharma** (employee).
2. Raise a *Printer* ticket with Medium priority.
3. Log out, log in as **Anita Rao** (engineer).
4. Point out the new ticket in the **unassigned triage queue**.
5. Assign it to yourself → status becomes *Assigned*.
6. Add troubleshooting notes → status *In Progress*.
7. Mark resolved with resolution notes → show timeline + resolution time.
8. Close it, then show the **search** and the **priority bar chart** as the finale.