from database.db import get_db


def _date_filter(from_date, to_date):
    if from_date and to_date:
        return "AND date BETWEEN ? AND ?", (from_date, to_date)
    return "", ()


def create_expense(user_id, amount, category, date, description):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_recent_transactions(user_id, limit=10, from_date=None, to_date=None):
    clause, params = _date_filter(from_date, to_date)
    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT date, description, category, amount FROM expenses "
            f"WHERE user_id = ? {clause} ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *params, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_summary_stats(user_id, from_date=None, to_date=None):
    clause, params = _date_filter(from_date, to_date)
    conn = get_db()
    try:
        row = conn.execute(
            f"SELECT COALESCE(SUM(amount), 0) AS total_spent, COUNT(*) AS transaction_count, "
            f"(SELECT category FROM expenses WHERE user_id = ? {clause} "
            f"GROUP BY category ORDER BY SUM(amount) DESC LIMIT 1) AS top_category "
            f"FROM expenses WHERE user_id = ? {clause}",
            (user_id, *params, user_id, *params),
        ).fetchone()
        return {
            "total_spent": row["total_spent"],
            "transaction_count": row["transaction_count"],
            "top_category": row["top_category"] or "—",
        }
    finally:
        conn.close()


def get_category_breakdown(user_id, from_date=None, to_date=None):
    clause, params = _date_filter(from_date, to_date)
    conn = get_db()
    try:
        rows = conn.execute(
            f"SELECT category, SUM(amount) AS total FROM expenses "
            f"WHERE user_id = ? {clause} GROUP BY category ORDER BY total DESC",
            (user_id, *params),
        ).fetchall()
        return [(r["category"], r["total"]) for r in rows]
    finally:
        conn.close()
