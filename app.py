import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from database.db import get_db, init_db, seed_db

app = Flask(__name__)
# Required for `session` to sign cookies. Dev-only value; swap for a real
# secret (env var, config file) before any non-local deploy.
app.config["SECRET_KEY"] = "dev-secret-change-me"


# ------------------------------------------------------------------ #
# Database initialization (runs once on startup)                      #
# ------------------------------------------------------------------ #
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
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""

        # --- validation (single error, in priority order) -------------- #
        if not name:
            error = "Please enter your name."
        elif not email or "@" not in email:
            error = "Please enter a valid email address."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        else:
            error = None

        if error:
            return render_template("register.html", error=error)

        # --- insert ----------------------------------------------------- #
        conn = get_db()
        try:
            try:
                conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return render_template(
                    "register.html",
                    error="An account with that email already exists.",
                )
            user_id = conn.execute(
                "SELECT id FROM users WHERE email = ?", (email,)
            ).fetchone()["id"]
        finally:
            conn.close()

        session["user_id"] = user_id
        return redirect(url_for("dashboard"))

    # GET
    return render_template("register.html")


@app.route("/dashboard")
def dashboard():
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT name FROM users WHERE id = ?", (session["user_id"],)
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        # Defensive: session points at a deleted user. Clear and redirect.
        session.clear()
        return redirect(url_for("register"))

    return render_template("dashboard.html", name=row["name"])


@app.route("/login")
def login():
    return render_template("login.html")


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
    return "Logout — coming in Step 3"


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
