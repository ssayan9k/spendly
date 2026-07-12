import sqlite3

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, get_user_by_email, init_db, seed_db

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


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        # Do NOT strip the password — leading/trailing spaces are meaningful
        # and a real user may intentionally have one.
        password = request.form.get("password") or ""

        # --- validation (single error, in priority order) -------------- #
        if not email:
            error = "Please enter your email and password."
        elif not password:
            error = "Please enter your email and password."
        else:
            error = None

        if error:
            return render_template("login.html", error=error)

        # --- look up + verify ------------------------------------------- #
        # Same generic error for "no such user" and "wrong password" so the
        # response does not leak which accounts exist (anti-enumeration).
        user = get_user_by_email(email)
        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template(
                "login.html",
                error="Invalid email or password.",
            )

        session["user_id"] = user["id"]
        return redirect(url_for("dashboard"))

    # GET — if the user is already signed in, send them straight to the
    # dashboard rather than re-rendering the sign-in form. /logout stays
    # accessible at all times because the navbar and dashboard's "Log out"
    # actions both link to it.
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

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
    # Safe to hit while logged out: session.clear() on an empty session is
    # a no-op, so this never raises.
    session.clear()
    return redirect(url_for("landing"))


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
