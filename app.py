import sqlite3
from datetime import date, datetime

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import (
    CATEGORIES,
    get_category_totals,
    get_db,
    get_expense_stats,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

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
    user_id = session.get("user_id")
    if user_id is None:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        # Defensive: session points at a deleted user. Clear and redirect.
        session.clear()
        return redirect(url_for("login"))

    # Only pass safe fields to the template — never expose password_hash.
    member_since = user["created_at"].split(" ")[0]  # "YYYY-MM-DD HH:MM:SS" -> "YYYY-MM-DD"

    # ------------------------------------------------------------------ #
    # Date filter (Spec 06). Read & validate the optional date_from and #
    # date_to query params; pass them to the three query helpers below.  #
    # Preset links and the active highlight are computed from the same  #
    # helpers used to render the filter bar in the template.             #
    # ------------------------------------------------------------------ #
    today = date.today()
    date_from = _parse_iso_date(request.args.get("date_from"))
    date_to = _parse_iso_date(request.args.get("date_to"))
    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        flash("Start date must be before end date.")
        date_from = None
        date_to = None

    active_preset = _active_preset(date_from, date_to, today)
    preset_links = _build_preset_links(today, date_from, date_to)

    # ------------------------------------------------------------------ #
    # Real DB-driven data (Spec 05). Each section is built by a helper    #
    # in app.py that wraps a query in database/db.py. Three subagents     #
    # own those helpers in disjoint zones below; do NOT edit these lines. #
    # ------------------------------------------------------------------ #
    # >>> SUBAGENT_1_STATS_ZONE_START
    profile_stats = _format_stats(get_expense_stats(user_id, date_from, date_to))
    # >>> SUBAGENT_1_STATS_ZONE_END

    # >>> SUBAGENT_2_TRANSACTIONS_ZONE_START
    profile_transactions = _format_transactions(
        get_recent_expenses(user_id, date_from=date_from, date_to=date_to)
    )
    # >>> SUBAGENT_2_TRANSACTIONS_ZONE_END

    # >>> SUBAGENT_3_CATEGORIES_ZONE_START
    profile_categories = _format_categories(
        get_category_totals(user_id, date_from, date_to)
    )
    # >>> SUBAGENT_3_CATEGORIES_ZONE_END

    # Avatar initials: first letter of the first two words of the name,
    # uppercased. Falls back to a single letter for one-word names.
    avatar_initials = "".join(
        part[0] for part in (user["name"].split() + ["E"])[:2]
    ).upper()[:2]

    return render_template(
        "profile.html",
        name=user["name"],
        email=user["email"],
        member_since=member_since,
        avatar_initials=avatar_initials,
        stats=profile_stats,
        transactions=profile_transactions,
        categories=profile_categories,
        active_preset=active_preset,
        preset_links=preset_links,
        date_from_str=date_from.isoformat() if date_from else "",
        date_to_str=date_to.isoformat() if date_to else "",
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


# ------------------------------------------------------------------ #
# Profile helpers (Spec 05)                                            #
# One helper per page section, owned by one subagent each.             #
# All SQL lives in database/db.py; these helpers only format results. #
# ------------------------------------------------------------------ #

# === AGENT_1_HELPER ===
def _format_stats(stats_row):
    """Format the raw get_expense_stats() row into the stats list the template expects.

    Returns:
        list[dict] — exactly three entries with keys "label" and "value":
            [{"label": "Total spent",  "value": "₹X,XXX.XX"},
             {"label": "Transactions", "value": "N"},
             {"label": "Top category", "value": "<category>"}]

    Rules:
        - Currency: f"₹{amount:,.2f}" — renders 0.00, not 0
        - Top category: when stats_row["top_category"] is None, render "—"
          (U+2014 EM DASH), matching the spec's empty-state wording
        - Transaction count: integer, no thousands separator
    """
    top_category = stats_row["top_category"]
    return [
        {"label": "Total spent",  "value": f"₹{stats_row['total_spent']:,.2f}"},
        {"label": "Transactions", "value": str(stats_row["transaction_count"])},
        {"label": "Top category", "value": top_category if top_category is not None else "—"},
    ]


# === AGENT_2_HELPER ===
def _format_transactions(rows):
    """Format raw expense rows into the transaction list the template expects.

    Returns:
        list[dict] where each entry has keys:
            {"date": "YYYY-MM-DD",
             "description": str,  # "" when the row's description is None
             "category": str,
             "amount": "₹X,XXX.XX"}  # f"₹{amount:,.2f}"

    Returns [] (not None) when the user has no expenses, so the template
    renders an empty transaction history cleanly. The date is taken as-is
    from the DB (already stored as YYYY-MM-DD by the seed and add routes).
    """
    return [
        {
            "date": row["date"],
            "description": row["description"] if row["description"] is not None else "",
            "category": row["category"],
            "amount": f"₹{row['amount']:,.2f}",
        }
        for row in rows
    ]


# === AGENT_3_HELPER ===


def _format_categories(rows):
    """Format raw category rows into the 7-row breakdown list the template expects.

    Always returns one entry per CATEGORIES constant value, in the constant's
    declared order, with `₹0.00` for any category not present in `rows`.
    This guarantees the breakdown list is visually complete even for a
    brand-new user with no expenses.

    Returns:
        list[dict] where each entry has keys:
            {"name": str,    # category name from CATEGORIES
             "total": "₹X,XXX.XX"}  # f"₹{amount:,.2f}"

    Implementation: build a dict {category: total} from `rows` (coerce
    missing amounts to 0.0), then iterate CATEGORIES in order and emit one
    formatted dict per category. Length of returned list is always
    len(CATEGORIES) (7).
    """
    totals_by_category = {row["category"]: float(row["total"] or 0.0) for row in rows}
    return [
        {"name": category, "total": f"₹{totals_by_category.get(category, 0.0):,.2f}"}
        for category in CATEGORIES
    ]


# ------------------------------------------------------------------ #
# Date-filter helpers (Spec 06)                                       #
# Pure-Python: parse, preset math, and active-state detection.       #
# All SQL stays in database/db.py.                                   #
# ------------------------------------------------------------------ #

def _first_of_months_ago(today, n):
    """Return the first day of the month `n` calendar months before `today`.

    Always returns a date with ``day == 1``. Handles year wrap by computing
    the absolute month offset, normalising into [1, 12], and adjusting the
    year. Used by the "Last N Months" presets so the lower bound is a
    stable month boundary rather than a moving day-of-month.
    """
    total_month = today.year * 12 + (today.month - 1) - n
    new_year, new_month0 = divmod(total_month, 12)
    return date(new_year, new_month0 + 1, 1)


def _preset_range(name, today):
    """Return the (date_from, date_to) range for a preset name, or None for "all_time".

    Preset names:
        "this_month"   -> (first of current month, today)
        "last_3_months" -> (first of 2 months back, today) — 3 calendar months
                            inclusive of the current month.
        "last_6_months" -> (first of 5 months back, today) — 6 calendar months
                            inclusive of the current month.
        "all_time"      -> None (caller passes (None, None) to the query helpers).

    Returns a 2-tuple of ``datetime.date`` objects, or None for "all_time".
    Unknown names raise ValueError so a typo in the preset list fails loudly.
    """
    if name == "this_month":
        return (today.replace(day=1), today)
    if name == "last_3_months":
        return (_first_of_months_ago(today, 2), today)
    if name == "last_6_months":
        return (_first_of_months_ago(today, 5), today)
    if name == "all_time":
        return None
    raise ValueError(f"Unknown preset: {name!r}")


def _parse_iso_date(value):
    """Parse a ``YYYY-MM-DD`` query-string value into a date, or None on bad input.

    Returns None for None, an empty string, or any ValueError from
    ``datetime.strptime``. Per the spec, malformed input is treated as
    "absent" so the route silently falls back to the unfiltered view.
    """
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _active_preset(date_from, date_to, today):
    """Return the key of the preset that matches the current range, or "custom"/"all_time".

    Exact-match against the four preset ranges (re-derived here from
    `_preset_range` so the comparison is deterministic). If both bounds
    are None, returns "all_time". If no preset matches, returns "custom".
    """
    if date_from is None and date_to is None:
        return "all_time"
    for key in ("this_month", "last_3_months", "last_6_months"):
        preset_from, preset_to = _preset_range(key, today)
        if date_from == preset_from and date_to == preset_to:
            return key
    return "custom"


def _build_preset_links(today, active_date_from, active_date_to):
    """Return the ordered list of preset link dicts for the filter bar.

    Each entry: ``{"key": str, "label": str, "url": str, "is_active": bool}``.
    The "all_time" entry passes no query params (clean ``/profile`` URL);
    the others include ``date_from`` and ``date_to`` via ``url_for``.
    Order is the display order: This Month, Last 3 Months, Last 6 Months,
    All Time.
    """
    active = _active_preset(active_date_from, active_date_to, today)
    ranges = {
        "this_month": _preset_range("this_month", today),
        "last_3_months": _preset_range("last_3_months", today),
        "last_6_months": _preset_range("last_6_months", today),
    }
    links = []
    for key, label in (
        ("this_month", "This Month"),
        ("last_3_months", "Last 3 Months"),
        ("last_6_months", "Last 6 Months"),
    ):
        d_from, d_to = ranges[key]
        links.append(
            {
                "key": key,
                "label": label,
                "url": url_for(
                    "profile",
                    date_from=d_from.isoformat(),
                    date_to=d_to.isoformat(),
                ),
                "is_active": active == key,
            }
        )
    # All Time -> no query params (clean URL), always last in the row.
    links.append(
        {
            "key": "all_time",
            "label": "All Time",
            "url": url_for("profile"),
            "is_active": active == "all_time",
        }
    )
    return links



if __name__ == "__main__":
    app.run(debug=True, port=5001)
