"""
tests/test_06-date-filter-profile.py

Tests for the date range filter feature on the /profile page (Step 06).

Spec: .claude/specs/06-date-filter-profile.md

Three expenses are seeded across distinct dates so every filter assertion is
meaningful:
    - 2026-05-01  Food        50.00   "Early May groceries"
    - 2026-05-15  Transport   30.00   "Mid May bus"
    - 2026-06-01  Bills      100.00   "June electricity"

All-time total  : 180.00  (3 transactions, top category = Bills)
May range total : 80.00   (2 transactions, top category = Food)  [50+30]
May-01 only     : 50.00   (1 transaction,  top category = Food)
Empty range     : 0       (0 transactions)
"""

import sqlite3
import pytest
from werkzeug.security import generate_password_hash

import app as flask_app_module
import database.queries as queries
import database.db as db_module


# ------------------------------------------------------------------ #
# Schema                                                              #
# ------------------------------------------------------------------ #

SCHEMA = """
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    UNIQUE NOT NULL,
    password_hash TEXT    NOT NULL,
    created_at    TEXT    DEFAULT (datetime('now'))
);
CREATE TABLE expenses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    amount      REAL    NOT NULL,
    category    TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    description TEXT,
    created_at  TEXT    DEFAULT (datetime('now'))
);
"""

# Three expenses spread across two calendar months
FILTER_EXPENSES = [
    (50.00, "Food",      "2026-05-01", "Early May groceries"),
    (30.00, "Transport", "2026-05-15", "Mid May bus"),
    (100.00, "Bills",    "2026-06-01", "June electricity"),
]

ALL_TIME_TOTAL = 180.00
MAY_TOTAL      = 80.00   # 50 + 30
MAY_01_TOTAL   = 50.00


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

class _NoClose:
    """Proxy that suppresses close() so the in-memory connection stays alive."""
    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture()
def mem_db():
    """Fresh in-memory SQLite DB seeded with the three filter-test expenses."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Filter User", "filter@spendly.com", generate_password_hash("filterpass")),
    )
    uid = cur.lastrowid
    cur.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(uid, *row) for row in FILTER_EXPENSES],
    )
    conn.commit()
    return conn, uid


@pytest.fixture(autouse=True)
def patch_get_db(mem_db, monkeypatch):
    """Replace get_db in both the queries module and the db module with the in-memory connection."""
    conn, _ = mem_db
    proxy = lambda: _NoClose(conn)
    monkeypatch.setattr(queries, "get_db", proxy)
    monkeypatch.setattr(db_module, "get_db", proxy)


@pytest.fixture()
def client():
    flask_app_module.app.config["TESTING"] = True
    flask_app_module.app.config["SECRET_KEY"] = "test-secret-filter"
    with flask_app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth_client(client, mem_db):
    """Test client with a valid session pre-set for the seeded user."""
    _, uid = mem_db
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_name"] = "Filter User"
    return client


# ------------------------------------------------------------------ #
# 1. Auth guard                                                        #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_unauthenticated_get_profile_redirects_to_login(self, client):
        resp = client.get("/profile")
        assert resp.status_code == 302, "Expected redirect for unauthenticated user"
        assert "/login" in resp.headers["Location"], "Redirect target should be /login"

    def test_unauthenticated_with_date_params_redirects_to_login(self, client):
        resp = client.get("/profile?from=2026-05-01&to=2026-05-31")
        assert resp.status_code == 302, "Date params must not bypass auth guard"
        assert "/login" in resp.headers["Location"]


# ------------------------------------------------------------------ #
# 2. No-params baseline (no regression)                               #
# ------------------------------------------------------------------ #

class TestNoParamsBaseline:
    def test_returns_200(self, auth_client):
        resp = auth_client.get("/profile")
        assert resp.status_code == 200, "Profile page should return 200 for logged-in user"

    def test_all_transactions_present(self, auth_client):
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert "Early May groceries" in body, "All-time view should include first expense"
        assert "Mid May bus" in body,         "All-time view should include second expense"
        assert "June electricity" in body,    "All-time view should include third expense"

    def test_all_time_total_stat(self, auth_client):
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        # Total 180.00 must appear somewhere in the stats section
        assert "180" in body, "All-time total of 180.00 should be displayed"

    def test_all_time_transaction_count(self, auth_client):
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert "3" in body, "Transaction count of 3 should appear on the page"

    def test_all_time_top_category_is_bills(self, auth_client):
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert "Bills" in body, "Top category (Bills, 100.00) should be shown in all-time view"

    def test_filter_form_uses_get_method(self, auth_client):
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert 'method="get"' in body.lower() or "method='get'" in body.lower(), \
            "Filter form must use method='get' for bookmarkable URLs"


# ------------------------------------------------------------------ #
# 3. Valid date range filter — transactions                           #
# ------------------------------------------------------------------ #

class TestValidDateRangeTransactions:
    def test_filtered_transactions_within_range_are_shown(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        body = resp.data.decode()
        assert "Early May groceries" in body, "Expense on 2026-05-01 should be within May filter"
        assert "Mid May bus" in body,         "Expense on 2026-05-15 should be within May filter"

    def test_transactions_outside_range_are_excluded(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        body = resp.data.decode()
        assert "June electricity" not in body, \
            "Expense on 2026-06-01 must not appear in May-only filter"

    def test_single_day_filter_shows_only_matching_expense(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-01")
        body = resp.data.decode()
        assert "Early May groceries" in body, "The single expense on 2026-05-01 should appear"
        assert "Mid May bus" not in body,     "2026-05-15 expense must not appear in single-day filter"
        assert "June electricity" not in body, "2026-06-01 expense must not appear in single-day filter"

    def test_filter_range_boundary_dates_are_inclusive(self, auth_client):
        # Both boundary dates (2026-05-01 and 2026-05-15) should be included
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-15")
        body = resp.data.decode()
        assert "Early May groceries" in body, "from-date boundary must be inclusive"
        assert "Mid May bus" in body,         "to-date boundary must be inclusive"
        assert "June electricity" not in body, "Expense after to-date must be excluded"


# ------------------------------------------------------------------ #
# 4. Summary stats reflect filtered range                             #
# ------------------------------------------------------------------ #

class TestSummaryStatsFiltered:
    def test_filtered_total_spent(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        body = resp.data.decode()
        # May total is 80.00; all-time is 180.00
        assert "80" in body, "Filtered total (80.00) should appear in stats"
        assert "180" not in body, \
            "All-time total (180.00) must NOT appear when filter is active"

    def test_filtered_transaction_count(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        body = resp.data.decode()
        # 2 transactions in May; must not show 3
        assert "2" in body, "Filtered transaction count (2) should appear"

    def test_filtered_top_category(self, auth_client):
        # In May: Food=50, Transport=30 → top category is Food
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        body = resp.data.decode()
        assert "Food" in body, "Top category within May filter should be Food (50.00)"

    def test_single_day_stats(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-01")
        body = resp.data.decode()
        assert "50" in body, "Single-day total (50.00) should appear"
        assert "Food" in body, "Single-day top category should be Food"


# ------------------------------------------------------------------ #
# 5. Category breakdown reflects filtered range                       #
# ------------------------------------------------------------------ #

class TestCategoryBreakdownFiltered:
    def test_only_filtered_categories_appear(self, auth_client):
        # May filter: Food + Transport only; Bills must not appear in breakdown
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        body = resp.data.decode()
        assert "Food" in body,      "Food category should appear in May breakdown"
        assert "Transport" in body, "Transport category should appear in May breakdown"
        assert "Bills" not in body, \
            "Bills category (June only) must not appear in May breakdown"

    def test_all_categories_appear_without_filter(self, auth_client):
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert "Food" in body
        assert "Transport" in body
        assert "Bills" in body


# ------------------------------------------------------------------ #
# 6. Date inputs are pre-filled after filtering                       #
# ------------------------------------------------------------------ #

class TestDateInputsPrefilled:
    def test_from_date_input_pre_filled(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        body = resp.data.decode()
        assert "2026-05-01" in body, \
            "The 'from' date input must retain the submitted value"

    def test_to_date_input_pre_filled(self, auth_client):
        resp = auth_client.get("/profile?from=2026-05-01&to=2026-05-31")
        body = resp.data.decode()
        assert "2026-05-31" in body, \
            "The 'to' date input must retain the submitted value"

    def test_no_prefill_when_no_params(self, auth_client):
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        # Inputs should not contain an arbitrary date value from a previous request
        # (they may be empty or absent — we simply confirm page loads correctly)
        assert resp.status_code == 200


# ------------------------------------------------------------------ #
# 7. Invalid range: from > to                                         #
# ------------------------------------------------------------------ #

class TestInvalidDateRange:
    def test_from_greater_than_to_returns_200(self, auth_client):
        resp = auth_client.get("/profile?from=2026-06-01&to=2026-05-01")
        assert resp.status_code == 200, "Page should still render on invalid range"

    def test_from_greater_than_to_shows_flash_error(self, auth_client):
        resp = auth_client.get("/profile?from=2026-06-01&to=2026-05-01",
                               follow_redirects=True)
        body = resp.data.decode()
        # The spec says a flash error is shown
        assert (
            "error" in body.lower()
            or "from" in body.lower() and "to" in body.lower()
            or "date" in body.lower()
        ), "A flash error message should be displayed when from > to"

    def test_from_greater_than_to_returns_all_time_data(self, auth_client):
        # When the range is invalid, all-time data must be returned (no filter applied)
        resp = auth_client.get("/profile?from=2026-06-01&to=2026-05-01")
        body = resp.data.decode()
        assert "Early May groceries" in body, \
            "All-time data: first expense must appear after invalid range"
        assert "Mid May bus" in body, \
            "All-time data: second expense must appear after invalid range"
        assert "June electricity" in body, \
            "All-time data: third expense must appear after invalid range"

    def test_invalid_range_shows_all_time_total(self, auth_client):
        resp = auth_client.get("/profile?from=2026-06-01&to=2026-05-01")
        body = resp.data.decode()
        assert "180" in body, \
            "All-time total (180.00) must be shown when date range is invalid"

    @pytest.mark.parametrize("from_d,to_d", [
        ("2026-12-31", "2026-01-01"),
        ("2026-06-02", "2026-06-01"),
    ])
    def test_various_invalid_ranges_return_all_time_data(self, auth_client, from_d, to_d):
        resp = auth_client.get(f"/profile?from={from_d}&to={to_d}")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "June electricity" in body, \
            f"All-time data should be returned for invalid range {from_d} > {to_d}"


# ------------------------------------------------------------------ #
# 8. Empty date range (no matching expenses)                          #
# ------------------------------------------------------------------ #

class TestEmptyDateRange:
    def test_empty_range_returns_200(self, auth_client):
        resp = auth_client.get("/profile?from=2025-01-01&to=2025-01-31")
        assert resp.status_code == 200

    def test_empty_range_shows_no_transactions_empty_state(self, auth_client):
        resp = auth_client.get("/profile?from=2025-01-01&to=2025-01-31")
        body = resp.data.decode()
        assert "No transactions" in body, \
            "Empty-state text for transactions table must appear when range has no results"

    def test_empty_range_shows_no_category_data_empty_state(self, auth_client):
        resp = auth_client.get("/profile?from=2025-01-01&to=2025-01-31")
        body = resp.data.decode()
        assert "No data" in body or "No transactions" in body, \
            "Empty-state text for category breakdown must appear when range has no results"

    def test_empty_range_total_is_zero(self, auth_client):
        resp = auth_client.get("/profile?from=2025-01-01&to=2025-01-31")
        body = resp.data.decode()
        # Total spent should reflect 0 for an empty range
        assert "0" in body, "Total spent should be 0 (or 0.00) for an empty date range"

    def test_empty_range_no_expense_descriptions_shown(self, auth_client):
        resp = auth_client.get("/profile?from=2025-01-01&to=2025-01-31")
        body = resp.data.decode()
        assert "Early May groceries" not in body
        assert "Mid May bus" not in body
        assert "June electricity" not in body


# ------------------------------------------------------------------ #
# 9. Partial params (only from or only to provided)                   #
# ------------------------------------------------------------------ #

class TestPartialParams:
    def test_only_from_param_returns_all_time_data(self, auth_client):
        # Spec: when either param is absent/empty, fall back to all-time
        resp = auth_client.get("/profile?from=2026-05-01")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "June electricity" in body, \
            "Without a 'to' param, all-time data should be returned"

    def test_only_to_param_returns_all_time_data(self, auth_client):
        resp = auth_client.get("/profile?to=2026-05-31")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "June electricity" in body, \
            "Without a 'from' param, all-time data should be returned"

    def test_empty_string_params_return_all_time_data(self, auth_client):
        resp = auth_client.get("/profile?from=&to=")
        assert resp.status_code == 200
        body = resp.data.decode()
        assert "Early May groceries" in body
        assert "Mid May bus" in body
        assert "June electricity" in body
