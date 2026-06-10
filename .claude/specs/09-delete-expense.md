# Spec: Delete Expense

## Overview
This feature replaces the `/expenses/<id>/delete` placeholder with a real action that lets a logged-in user permanently remove an expense they own. It is the third and final step of the expense-CRUD trio (add, edit, delete) and reuses the ownership-check and query conventions established in the add/edit expense features.

## Depends on
- 01-database-setup (expenses table)
- 03-login-and-logout (session-based auth)
- 07-add-expense (query conventions)
- 08-edit-expense (ownership-check pattern via `get_expense_by_id`)

## Routes
- `POST /expenses/<id>/delete` — delete the expense if it belongs to the current user, then redirect to profile — logged-in, owner-only

The existing placeholder route accepts `GET` only; it will be replaced with a `POST`-only route so deletion cannot be triggered by a simple link or page prefetch.

## Database changes
No database changes. The existing `expenses` table (`database/db.py`) is sufficient.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — add a small "Delete" form/button next to the existing "Edit" link in the transactions table's Actions column. The form posts to `/expenses/<id>/delete` and uses a JS confirmation dialog before submitting.

## Files to change
- `app.py` — replace the `delete_expense` stub with a `POST`-only handler: require login, look up the expense scoped to `user_id` via `get_expense_by_id` (404 if missing/not owned), call `delete_expense`, flash a success message, redirect to `profile`
- `database/queries.py` — add `delete_expense(expense_id, user_id)` (parameterised DELETE scoped to the owning user)
- `templates/profile.html` — add the delete form/button in the Actions column
- `static/js/main.js` — add a small confirm-before-submit handler for delete forms (or inline `onsubmit` confirm — implementer's choice, but must prevent accidental deletion)

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
- Require `session.get("user_id")`; redirect to `login` if absent (mirror `add_expense`/`edit_expense`)
- Look up the expense scoped to the current user's `user_id` before deleting; if it does not exist or belongs to another user, return a 404 (use `abort(404)`) — never reveal another user's data
- Always delete the expense filtered by both `id` and `user_id` to enforce ownership at the database layer, not just in application logic
- The delete action must require `POST` (not `GET`), and the UI must ask for confirmation before submitting

## Definition of done
- [ ] Visiting/posting to `/expenses/<id>/delete` while logged out redirects to `/login`
- [ ] A `GET` request to `/expenses/<id>/delete` is rejected (405) — only `POST` is allowed
- [ ] Posting to `/expenses/<id>/delete` for an expense that doesn't exist, or belongs to another user, returns a 404 and does not delete any row
- [ ] Posting to `/expenses/<id>/delete` for your own expense removes the row from `expenses` and redirects to `/profile` with a success flash message
- [ ] After deletion, the expense no longer appears in the profile page's recent transactions, and the summary stats and category breakdown update accordingly
- [ ] Clicking "Delete" in the UI shows a confirmation dialog before the request is sent
