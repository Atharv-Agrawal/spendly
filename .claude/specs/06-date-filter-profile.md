# Spec: Date Filter for Profile Page

## Overview
Adds a date range filter to the profile page so users can narrow the transactions table, summary stats, and category breakdown to a chosen time window. The filter is submitted as a GET form with `from` and `to` query parameters. When no dates are provided the page behaves exactly as before (all-time view). This is the first interactive data-exploration feature on the profile page.

## Depends on
- Step 05 — Backend Routes for Profile Page (profile route, queries, stats)

## Routes
- `GET /profile?from=YYYY-MM-DD&to=YYYY-MM-DD` — filter profile data to date range — logged-in only

No new routes are added; the existing `/profile` route is extended to read optional query parameters.

## Database changes
No database changes.

## Templates
- **Modify:** `templates/profile.html`
  - Add a date-range filter form (two date inputs + submit button) above the stats row
  - Pass `from_date` and `to_date` back into the template so the inputs retain their values after submission

## Files to change
- `app.py` — read `from` and `to` query params in the `profile` route; pass them to each query helper and back to the template
- `database/queries.py` — update `get_recent_transactions`, `get_summary_stats`, and `get_category_breakdown` to accept optional `from_date` / `to_date` arguments and add `WHERE … AND date BETWEEN ? AND ?` clauses when they are provided
- `templates/profile.html` — add the filter form UI
- `static/css/style.css` — add styles for the filter form

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never interpolate dates into SQL strings
- Passwords hashed with werkzeug (no change needed here, just don't touch auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- When `from` or `to` params are absent or empty, fall back to querying all data (no date filter applied)
- Validate that `from_date <= to_date` in the route; if invalid, flash an error and reload without filtering
- The filter form must use `method="get"` so the URL is bookmarkable/shareable

## Definition of done
- [ ] Visiting `/profile` with no query params shows all transactions and stats (no regression)
- [ ] Submitting the filter form with a valid date range updates the transactions table to show only expenses within that range
- [ ] The summary stats (Total Spent, Transactions, Top Category) reflect the filtered date range, not all-time totals
- [ ] The category breakdown reflects the filtered date range
- [ ] The date inputs are pre-filled with the submitted values after filtering
- [ ] If `from` > `to`, a flash error message is shown and no filter is applied
- [ ] If no expenses match the date range, the empty-state message is shown in both the transactions table and the category breakdown
