import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, flash, redirect, url_for, abort, session
from werkzeug.security import check_password_hash
from database.db import get_db, init_db, seed_db, create_user, get_user_by_email

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
    conn = get_db()
    try:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    finally:
        conn.close()

    expenses = [
        {"date": "2025-04-12", "description": "Groceries",            "category": "Food",          "amount": 850.00},
        {"date": "2025-04-11", "description": "Metro card recharge",  "category": "Transport",     "amount": 500.00},
        {"date": "2025-04-10", "description": "Electricity bill",     "category": "Bills",         "amount": 2200.00},
        {"date": "2025-04-09", "description": "Doctor visit",         "category": "Health",        "amount": 800.00},
        {"date": "2025-04-08", "description": "Netflix subscription", "category": "Entertainment", "amount": 649.00},
        {"date": "2025-04-07", "description": "Clothing haul",        "category": "Shopping",      "amount": 3200.00},
        {"date": "2025-04-06", "description": "Restaurant dinner",    "category": "Food",          "amount": 1450.00},
        {"date": "2025-04-05", "description": "Miscellaneous",        "category": "Other",         "amount": 2801.75},
    ]

    total = sum(e["amount"] for e in expenses)
    from collections import Counter, defaultdict
    counts = Counter(e["category"] for e in expenses)
    top_category = counts.most_common(1)[0][0]
    cat_sums = defaultdict(float)
    for e in expenses:
        cat_sums[e["category"]] += e["amount"]
    category_totals = sorted(cat_sums.items(), key=lambda x: x[1], reverse=True)

    return render_template(
        "profile.html",
        user=user,
        expenses=expenses,
        total=total,
        transaction_count=len(expenses),
        top_category=top_category,
        category_totals=category_totals,
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
