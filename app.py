import re
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for, abort, session
from werkzeug.security import check_password_hash
from database.db import init_db, seed_db, create_user, get_user_by_email
from database.queries import get_user_by_id, get_summary_stats, get_recent_transactions, get_category_breakdown, create_expense, get_expense_by_id, update_expense

VALID_CATEGORIES = {"Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"}

app = Flask(__name__)
app.secret_key = "dev-secret-key"


@app.template_filter("fmt_date")
def fmt_date(value):
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception:
        return value


@app.template_filter("initials")
def initials(name):
    return "".join(w[0] for w in name.split() if w).upper()


@app.template_filter("inr")
def inr(value):
    return "{:,.2f}".format(value)


@app.template_filter("member_since")
def member_since(value):
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%B %Y")
    except Exception:
        return value


with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "GET":
        return render_template("register.html")

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not all([name, email, password, confirm_password]):
            flash("All fields are required.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            flash("An account with that email already exists.", "error")
            return render_template("register.html")

        flash("Account created! Please sign in.", "success")
        return redirect(url_for("login"))

    abort(405)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "GET":
        return render_template("login.html")

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("All fields are required.", "error")
            return render_template("login.html")

        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        flash(f"Welcome back, {user['name']}!", "success")
        return redirect(url_for("profile"))

    abort(405)


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    uid = session["user_id"]

    _date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    from_date = request.args.get("from", "").strip()
    to_date = request.args.get("to", "").strip()
    preset = request.args.get("preset", "").strip()

    if from_date and not _date_re.match(from_date):
        from_date = ""
    if to_date and not _date_re.match(to_date):
        to_date = ""
    if preset not in {"month", "3months", "6months"}:
        preset = ""

    if from_date and to_date and from_date > to_date:
        flash("'From' date must be on or before 'To' date.", "error")
        from_date = to_date = ""

    user = get_user_by_id(uid)
    stats = get_summary_stats(uid, from_date=from_date or None, to_date=to_date or None)
    expenses = get_recent_transactions(uid, from_date=from_date or None, to_date=to_date or None)
    category_totals = get_category_breakdown(uid, from_date=from_date or None, to_date=to_date or None)
    return render_template(
        "profile.html",
        user=user,
        expenses=expenses,
        total=stats["total_spent"],
        transaction_count=stats["transaction_count"],
        top_category=stats["top_category"],
        category_totals=category_totals,
        from_date=from_date,
        preset=preset,
        to_date=to_date,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


def _render_expense_form(expense=None, action=None):
    return render_template("expense_form.html", categories=sorted(VALID_CATEGORIES), expense=expense, action=action)


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    uid = session["user_id"]

    if request.method == "GET":
        return _render_expense_form()

    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    try:
        amount = float(amount_raw)
    except ValueError:
        amount = None

    if amount is None or amount <= 0:
        flash("Enter a valid amount greater than zero.", "error")
        return _render_expense_form()

    if category not in VALID_CATEGORIES:
        flash("Select a valid category.", "error")
        return _render_expense_form()

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        flash("Enter a valid date.", "error")
        return _render_expense_form()

    create_expense(uid, amount, category, date, description or None)
    flash("Expense added!", "success")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
    uid = session["user_id"]

    expense = get_expense_by_id(id, uid)
    if expense is None:
        abort(404)

    action = url_for("edit_expense", id=id)

    if request.method == "GET":
        return _render_expense_form(expense=expense, action=action)

    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    submitted = {"amount": amount_raw, "category": category, "date": date, "description": description}

    try:
        amount = float(amount_raw)
    except ValueError:
        amount = None

    if amount is None or amount <= 0:
        flash("Enter a valid amount greater than zero.", "error")
        return _render_expense_form(expense=submitted, action=action)

    if category not in VALID_CATEGORIES:
        flash("Select a valid category.", "error")
        return _render_expense_form(expense=submitted, action=action)

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        flash("Enter a valid date.", "error")
        return _render_expense_form(expense=submitted, action=action)

    update_expense(id, uid, amount, category, date, description or None)
    flash("Expense updated!", "success")
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
