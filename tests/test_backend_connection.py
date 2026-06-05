import sqlite3
import pytest
from werkzeug.security import generate_password_hash

import app as flask_app
import database.queries as queries


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

SEED_EXPENSES = [
    (12.50, "Food",          "2026-05-01", "Grocery run"),
    (35.00, "Transport",     "2026-05-03", "Monthly bus pass"),
    (80.00, "Bills",         "2026-05-05", "Electricity bill"),
    (25.00, "Health",        "2026-05-07", "Pharmacy"),
    (15.00, "Entertainment", "2026-05-09", "Netflix subscription"),
    (60.00, "Shopping",      "2026-05-11", "New shoes"),
    (10.00, "Other",         "2026-05-13", "Miscellaneous"),
    ( 8.75, "Food",          "2026-05-14", "Coffee and snacks"),
]
SEED_TOTAL = sum(r[0] for r in SEED_EXPENSES)  # 246.25


@pytest.fixture()
def mem_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    uid = cur.lastrowid
    cur.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(uid, *row) for row in SEED_EXPENSES],
    )
    conn.commit()
    return conn, uid


class _NoClose:
    """Proxy that forwards all attribute access to the real connection but ignores close()."""
    def __init__(self, conn):
        self._conn = conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._conn, name)


@pytest.fixture(autouse=True)
def patch_get_db(mem_db, monkeypatch):
    conn, _ = mem_db
    monkeypatch.setattr(queries, "get_db", lambda: _NoClose(conn))


# ------------------------------------------------------------------ #
# Unit tests — get_user_by_id                                         #
# ------------------------------------------------------------------ #

def test_get_user_by_id_valid(mem_db):
    _, uid = mem_db
    user = queries.get_user_by_id(uid)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert "created_at" in user


def test_get_user_by_id_missing():
    assert queries.get_user_by_id(9999) is None


# ------------------------------------------------------------------ #
# Unit tests — get_summary_stats                                       #
# ------------------------------------------------------------------ #

def test_get_summary_stats_with_expenses(mem_db):
    _, uid = mem_db
    stats = queries.get_summary_stats(uid)
    assert stats["total_spent"] == pytest.approx(SEED_TOTAL)
    assert stats["transaction_count"] == 8
    assert stats["top_category"] == "Bills"


def test_get_summary_stats_no_expenses(mem_db):
    conn, _ = mem_db
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Empty User", "empty@spendly.com", generate_password_hash("x")),
    )
    conn.commit()
    new_uid = conn.execute("SELECT id FROM users WHERE email = ?", ("empty@spendly.com",)).fetchone()["id"]
    stats = queries.get_summary_stats(new_uid)
    assert stats["total_spent"] == 0
    assert stats["transaction_count"] == 0
    assert stats["top_category"] == "—"


# ------------------------------------------------------------------ #
# Unit tests — get_recent_transactions                                 #
# ------------------------------------------------------------------ #

def test_get_recent_transactions_with_expenses(mem_db):
    _, uid = mem_db
    txns = queries.get_recent_transactions(uid)
    assert len(txns) == 8
    dates = [t["date"] for t in txns]
    assert dates == sorted(dates, reverse=True)
    assert all({"date", "description", "category", "amount"} <= t.keys() for t in txns)


def test_get_recent_transactions_no_expenses(mem_db):
    conn, _ = mem_db
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Empty2", "empty2@spendly.com", generate_password_hash("x")),
    )
    conn.commit()
    new_uid = conn.execute("SELECT id FROM users WHERE email = ?", ("empty2@spendly.com",)).fetchone()["id"]
    assert queries.get_recent_transactions(new_uid) == []


def test_get_recent_transactions_limit(mem_db):
    _, uid = mem_db
    txns = queries.get_recent_transactions(uid, limit=3)
    assert len(txns) == 3


# ------------------------------------------------------------------ #
# Unit tests — get_category_breakdown                                  #
# ------------------------------------------------------------------ #

def test_get_category_breakdown_with_expenses(mem_db):
    _, uid = mem_db
    breakdown = queries.get_category_breakdown(uid)
    assert len(breakdown) == 7
    amounts = [amt for _, amt in breakdown]
    assert amounts == sorted(amounts, reverse=True)
    assert all(isinstance(cat, str) and isinstance(amt, float) for cat, amt in breakdown)


def test_get_category_breakdown_no_expenses(mem_db):
    conn, _ = mem_db
    conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Empty3", "empty3@spendly.com", generate_password_hash("x")),
    )
    conn.commit()
    new_uid = conn.execute("SELECT id FROM users WHERE email = ?", ("empty3@spendly.com",)).fetchone()["id"]
    assert queries.get_category_breakdown(new_uid) == []


# ------------------------------------------------------------------ #
# Route tests                                                          #
# ------------------------------------------------------------------ #

@pytest.fixture()
def client():
    flask_app.app.config["TESTING"] = True
    flask_app.app.config["SECRET_KEY"] = "test-secret"
    with flask_app.app.test_client() as c:
        yield c


def test_profile_unauthenticated(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated(client, mem_db):
    _, uid = mem_db
    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_name"] = "Demo User"

    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₹" in body
