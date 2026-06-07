"""
tests/test_07-add-expense.py

Tests for the "Add Expense" feature (Step 07).

Spec: .claude/specs/07-add-expense.md

Covers:
    - GET /expenses/add requires login
    - GET /expenses/add renders the form when logged in
    - POST /expenses/add with valid data inserts a row, flashes success,
      redirects to /profile
    - POST /expenses/add with invalid amount / category / date shows an
      error and does not insert
    - description is optional
    - newly added expense appears in profile's recent transactions and
      category breakdown
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

VALID_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]


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
    """Fresh in-memory SQLite DB seeded with a single user and no expenses."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Add Expense User", "addexpense@spendly.com", generate_password_hash("addpass")),
    )
    uid = cur.lastrowid
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
    flask_app_module.app.config["SECRET_KEY"] = "test-secret-add-expense"
    with flask_app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth_client(client, mem_db):
    """Test client with a valid session pre-set for the seeded user."""
    _, uid = mem_db
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_name"] = "Add Expense User"
    return client


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _expense_count(mem_db, uid):
    conn, _ = mem_db
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM expenses WHERE user_id = ?", (uid,)
    ).fetchone()
    return row["c"]


def _fetch_expenses(mem_db, uid):
    conn, _ = mem_db
    return conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id", (uid,)
    ).fetchall()


def _valid_payload(**overrides):
    payload = {
        "amount": "42.50",
        "category": "Food",
        "date": "2026-05-20",
        "description": "Weekly groceries",
    }
    payload.update(overrides)
    return payload


# ------------------------------------------------------------------ #
# 1. Auth guard on GET                                                #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    def test_get_add_expense_redirects_to_login_when_logged_out(self, client):
        resp = client.get("/expenses/add")
        assert resp.status_code == 302, "Expected redirect for unauthenticated user"
        assert "/login" in resp.headers["Location"], "Redirect target should be /login"

    def test_post_add_expense_redirects_to_login_when_logged_out(self, client):
        resp = client.post("/expenses/add", data=_valid_payload())
        assert resp.status_code == 302, "POST while logged out must also be guarded"
        assert "/login" in resp.headers["Location"], "Redirect target should be /login"

    def test_logged_out_post_does_not_insert_row(self, client, mem_db):
        conn, uid = mem_db
        client.post("/expenses/add", data=_valid_payload())
        assert _expense_count(mem_db, uid) == 0, \
            "No expense should be inserted for an unauthenticated request"


# ------------------------------------------------------------------ #
# 2. GET renders the form when logged in                             #
# ------------------------------------------------------------------ #

class TestGetFormRendersWhenLoggedIn:
    def test_get_returns_200(self, auth_client):
        resp = auth_client.get("/expenses/add")
        assert resp.status_code == 200, "Logged-in user should be able to load the add-expense form"

    def test_form_contains_amount_field(self, auth_client):
        resp = auth_client.get("/expenses/add")
        body = resp.data.decode().lower()
        assert 'name="amount"' in body, "Form should contain an amount field"

    def test_form_contains_category_field(self, auth_client):
        resp = auth_client.get("/expenses/add")
        body = resp.data.decode().lower()
        assert 'name="category"' in body, "Form should contain a category field"

    def test_form_contains_date_field(self, auth_client):
        resp = auth_client.get("/expenses/add")
        body = resp.data.decode().lower()
        assert 'name="date"' in body, "Form should contain a date field"

    def test_form_contains_description_field(self, auth_client):
        resp = auth_client.get("/expenses/add")
        body = resp.data.decode().lower()
        assert 'name="description"' in body, "Form should contain a description field"

    def test_form_lists_expected_categories(self, auth_client):
        resp = auth_client.get("/expenses/add")
        body = resp.data.decode()
        for category in VALID_CATEGORIES:
            assert category in body, f"Category option '{category}' should appear in the form"


# ------------------------------------------------------------------ #
# 3. POST with valid data                                            #
# ------------------------------------------------------------------ #

class TestValidSubmission:
    def test_valid_submission_redirects_to_profile(self, auth_client):
        resp = auth_client.post("/expenses/add", data=_valid_payload())
        assert resp.status_code == 302, "Valid submission should redirect"
        assert "/profile" in resp.headers["Location"], "Should redirect to /profile on success"

    def test_valid_submission_flashes_success(self, auth_client):
        resp = auth_client.post("/expenses/add", data=_valid_payload(), follow_redirects=True)
        body = resp.data.decode().lower()
        assert "success" in body or "added" in body or "expense" in body, \
            "A success flash message should be shown after adding an expense"

    def test_valid_submission_inserts_row_for_current_user(self, auth_client, mem_db):
        conn, uid = mem_db
        auth_client.post("/expenses/add", data=_valid_payload())
        rows = _fetch_expenses(mem_db, uid)
        assert len(rows) == 1, "Exactly one expense row should be inserted"
        row = rows[0]
        assert row["user_id"] == uid, "Inserted expense must belong to the logged-in user"
        assert row["amount"] == 42.50, "Amount should be stored as submitted"
        assert row["category"] == "Food", "Category should be stored as submitted"
        assert row["date"] == "2026-05-20", "Date should be stored as submitted"
        assert row["description"] == "Weekly groceries", "Description should be stored as submitted"

    def test_valid_submission_increments_count_by_one(self, auth_client, mem_db):
        conn, uid = mem_db
        before = _expense_count(mem_db, uid)
        auth_client.post("/expenses/add", data=_valid_payload())
        after = _expense_count(mem_db, uid)
        assert after == before + 1, "Expense count should increase by exactly one"


# ------------------------------------------------------------------ #
# 4. Invalid amount                                                  #
# ------------------------------------------------------------------ #

class TestInvalidAmount:
    @pytest.mark.parametrize("bad_amount", ["", "0", "-5", "-0.01", "abc", "12.34.56", "$10"])
    def test_invalid_amount_does_not_insert(self, auth_client, mem_db, bad_amount):
        conn, uid = mem_db
        auth_client.post("/expenses/add", data=_valid_payload(amount=bad_amount))
        assert _expense_count(mem_db, uid) == 0, \
            f"Amount {bad_amount!r} should be rejected and not inserted"

    @pytest.mark.parametrize("bad_amount", ["", "0", "-5", "abc"])
    def test_invalid_amount_shows_error_and_redisplays_form(self, auth_client, bad_amount):
        resp = auth_client.post("/expenses/add", data=_valid_payload(amount=bad_amount), follow_redirects=True)
        body = resp.data.decode().lower()
        assert resp.status_code == 200, "Form should be redisplayed (200) on validation error"
        assert "error" in body or "invalid" in body or "amount" in body, \
            f"An error message referencing amount should be shown for {bad_amount!r}"

    def test_missing_amount_field_does_not_insert(self, auth_client, mem_db):
        conn, uid = mem_db
        payload = _valid_payload()
        del payload["amount"]
        auth_client.post("/expenses/add", data=payload)
        assert _expense_count(mem_db, uid) == 0, \
            "Submission with no amount field at all must not insert a row"


# ------------------------------------------------------------------ #
# 5. Invalid category                                                #
# ------------------------------------------------------------------ #

class TestInvalidCategory:
    @pytest.mark.parametrize("bad_category", ["", "Groceries", "FOOD", "food ", "<script>"])
    def test_invalid_category_does_not_insert(self, auth_client, mem_db, bad_category):
        conn, uid = mem_db
        auth_client.post("/expenses/add", data=_valid_payload(category=bad_category))
        assert _expense_count(mem_db, uid) == 0, \
            f"Category {bad_category!r} should be rejected and not inserted"

    def test_invalid_category_shows_error_and_redisplays_form(self, auth_client):
        resp = auth_client.post("/expenses/add", data=_valid_payload(category="NotACategory"), follow_redirects=True)
        body = resp.data.decode().lower()
        assert resp.status_code == 200, "Form should be redisplayed (200) on validation error"
        assert "error" in body or "invalid" in body or "category" in body, \
            "An error message referencing category should be shown"


# ------------------------------------------------------------------ #
# 6. Malformed date                                                  #
# ------------------------------------------------------------------ #

class TestInvalidDate:
    @pytest.mark.parametrize("bad_date", ["", "20-05-2026", "2026/05/20", "May 20 2026", "2026-13-01", "2026-05-32", "not-a-date"])
    def test_malformed_date_does_not_insert(self, auth_client, mem_db, bad_date):
        conn, uid = mem_db
        auth_client.post("/expenses/add", data=_valid_payload(date=bad_date))
        assert _expense_count(mem_db, uid) == 0, \
            f"Date {bad_date!r} should be rejected and not inserted"

    def test_malformed_date_shows_error_and_redisplays_form(self, auth_client):
        resp = auth_client.post("/expenses/add", data=_valid_payload(date="20-05-2026"), follow_redirects=True)
        body = resp.data.decode().lower()
        assert resp.status_code == 200, "Form should be redisplayed (200) on validation error"
        assert "error" in body or "invalid" in body or "date" in body, \
            "An error message referencing date should be shown"


# ------------------------------------------------------------------ #
# 7. Description is optional                                         #
# ------------------------------------------------------------------ #

class TestDescriptionOptional:
    def test_submission_without_description_field_succeeds(self, auth_client, mem_db):
        conn, uid = mem_db
        payload = _valid_payload()
        del payload["description"]
        resp = auth_client.post("/expenses/add", data=payload)
        assert resp.status_code == 302, "Omitting description should still allow a successful submission"
        assert _expense_count(mem_db, uid) == 1, "Expense should be inserted even without a description"

    def test_submission_with_empty_description_succeeds(self, auth_client, mem_db):
        conn, uid = mem_db
        resp = auth_client.post("/expenses/add", data=_valid_payload(description=""))
        assert resp.status_code == 302, "Empty description should still allow a successful submission"
        rows = _fetch_expenses(mem_db, uid)
        assert len(rows) == 1
        assert rows[0]["description"] in ("", None), \
            "Empty description should be stored as empty string or NULL"


# ------------------------------------------------------------------ #
# 8. New expense appears on the profile page                         #
# ------------------------------------------------------------------ #

class TestExpenseAppearsOnProfile:
    def test_new_expense_appears_in_recent_transactions(self, auth_client):
        auth_client.post("/expenses/add", data=_valid_payload(description="Unique Marker Description XYZ"))
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert "Unique Marker Description XYZ" in body, \
            "Newly added expense should appear in the profile's recent transactions"

    def test_new_expense_amount_appears_on_profile(self, auth_client):
        auth_client.post("/expenses/add", data=_valid_payload(amount="77.25", description="Marker For Amount"))
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert "77.25" in body or "77" in body, \
            "Newly added expense's amount should be reflected on the profile page"

    def test_new_expense_category_appears_in_breakdown(self, auth_client):
        # "Health" is not seeded in this fixture, so its appearance proves the new
        # expense is reflected in the category breakdown.
        auth_client.post("/expenses/add", data=_valid_payload(category="Health", description="Doctor visit"))
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert "Health" in body, \
            "Category of newly added expense should appear in the profile's category breakdown"

    def test_failed_submission_does_not_appear_on_profile(self, auth_client):
        auth_client.post("/expenses/add", data=_valid_payload(amount="-5", description="Should Not Appear Anywhere"))
        resp = auth_client.get("/profile")
        body = resp.data.decode()
        assert "Should Not Appear Anywhere" not in body, \
            "A rejected (invalid) submission must not show up on the profile page"
