# Spec: Add Expense

## Overview
This feature replaces the `/expenses/add` placeholder with a real form-based flow that lets a logged-in user record a new expense (amount, category, date, description). It is the first of the expense-CRUD steps (add, edit, delete) and builds directly on the database schema and query patterns already established for the profile page.

## Depends on
- 01-database-setup (expenses table)
- 03-login-and-logout (session-based auth)
- 05-backend-routes-for-profile-page (query/route conventions, redirect patterns)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in
- `POST /expenses/add` — validate and insert a new expense, then redirect to profile — logged-in

## Database changes
No database changes. The existing `expenses` table (`database/db.py`) already has the required columns: `user_id`, `amount`, `category`, `date`, `description`.

## Templates
- **Create:** `templates/expense_form.html` — form with fields for amount, category (select), date, description; extends `base.html`; reuses existing form/input styling conventions from `register.html`/`login.html`
- **Modify:** none

## Files to change
- `app.py` — replace the `add_expense` stub with full GET/POST handler (validation, flash messages, redirect)
- `database/queries.py` — add a `create_expense(user_id, amount, category, date, description)` function using a parameterised INSERT

## Files to create
- `templates/expense_form.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (n/a here, but keep existing auth code untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate: amount must be a positive number, category must be one of the existing categories (Food, Transport, Bills, Health, Entertainment, Shopping, Other), date must match `YYYY-MM-DD`, description is optional
- Reject the request with a flashed error and re-rendered form on invalid input (mirror the pattern used in `register`/`login`)
- Require `session.get("user_id")`; redirect to `login` if absent (mirror `profile`)

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows a form with amount, category, date, and description fields
- [ ] Submitting the form with valid data inserts a row into `expenses` for the current user and redirects to `/profile` with a success flash message
- [ ] Submitting with a missing/invalid amount, invalid category, or malformed date shows an error flash and redisplays the form without inserting a row
- [ ] The newly added expense appears in the profile page's recent transactions and category breakdown
