# Spec: Edit Expense

## Overview
This feature replaces the `/expenses/<id>/edit` placeholder with a real form-based flow that lets a logged-in user update an existing expense they own (amount, category, date, description). It is the second of the expense-CRUD steps (add, edit, delete) and reuses the form template, validation rules, and query conventions established in the add-expense feature.

## Depends on
- 01-database-setup (expenses table)
- 03-login-and-logout (session-based auth)
- 07-add-expense (expense form template, validation pattern, query conventions)

## Routes
- `GET /expenses/<id>/edit` — render the edit-expense form pre-filled with the existing expense's values — logged-in, owner-only
- `POST /expenses/<id>/edit` — validate and update the expense, then redirect to profile — logged-in, owner-only

## Database changes
No database changes. The existing `expenses` table (`database/db.py`) already has the required columns: `user_id`, `amount`, `category`, `date`, `description`.

## Templates
- **Create:** none
- **Modify:** `templates/expense_form.html` — support an "edit" mode: accept an optional `expense` value to pre-fill field values, change the heading/subtitle/submit button text, and post to the edit route when editing

## Files to change
- `app.py` — replace the `edit_expense` stub with a full GET/POST handler (ownership check, pre-filled form, validation, flash messages, redirect); update `_render_expense_form` to support passing through an existing expense and the correct form action
- `database/queries.py` — add `get_expense_by_id(expense_id, user_id)` (parameterised SELECT scoped to the owning user) and `update_expense(expense_id, user_id, amount, category, date, description)` (parameterised UPDATE scoped to the owning user)

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (n/a here, but keep existing auth code untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate: amount must be a positive number, category must be one of the existing categories (Food, Transport, Bills, Health, Entertainment, Shopping, Other), date must match `YYYY-MM-DD`, description is optional
- Reject the request with a flashed error and re-rendered form on invalid input (mirror the pattern used in `add_expense`)
- Require `session.get("user_id")`; redirect to `login` if absent (mirror `add_expense`)
- Look up the expense scoped to the current user's `user_id`; if it does not exist or belongs to another user, return a 404 (use `abort(404)`) — never reveal another user's data
- Always query and update the expense filtered by both `id` and `user_id` to enforce ownership at the database layer, not just in application logic

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense that doesn't exist, or belongs to another user, returns a 404
- [ ] Visiting `/expenses/<id>/edit` for your own expense shows a form pre-filled with its current amount, category, date, and description
- [ ] Submitting the form with valid data updates the row in `expenses` and redirects to `/profile` with a success flash message
- [ ] Submitting with a missing/invalid amount, invalid category, or malformed date shows an error flash and redisplays the form (with the entered values) without updating the row
- [ ] The updated expense's new values appear in the profile page's recent transactions and category breakdown
