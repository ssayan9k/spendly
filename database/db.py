"""SQLite data layer for Spendly.

Provides:
    get_db()   -- returns a connection with row_factory set and foreign keys ON
    init_db()  -- creates the users and expenses tables (idempotent)
    seed_db()  -- inserts demo user + 8 sample expenses (idempotent)
"""

import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

# Fixed set of expense categories. Single source of truth for the 7 valid
# values — used by the seed, the category breakdown, and (later) the add
# / edit expense forms. Order matters: the breakdown list is rendered in
# this order so a user always sees the same shape.
CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)

# Database file lives at the project root, next to app.py.
# Path: <this file>/../expense_tracker.db
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "expense_tracker.db"
)


def get_db():
    """Open a SQLite connection to the Spendly database.

    Sets row_factory for dict-like access and enables foreign key enforcement.
    Callers are responsible for closing the connection.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # PRAGMA foreign_keys must be set per-connection; SQLite does not persist it.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the users and expenses tables if they do not already exist.

    Safe to call on every app startup.
    """
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT    NOT NULL,
                email         TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL    NOT NULL,
                category    TEXT    NOT NULL,
                date        TEXT    NOT NULL,
                description TEXT,
                created_at  TEXT    DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    """Insert a demo user and 8 sample expenses.

    Returns early without inserting if the users table already has any rows,
    so repeated startups never duplicate the seed.
    """
    conn = get_db()
    try:
        existing = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        if existing > 0:
            return

        # --- demo user ---------------------------------------------------- #
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (
                "Demo User",
                "demo@spendly.com",
                generate_password_hash("demo123"),
            ),
        )
        demo_user_id = cursor.lastrowid

        # --- 8 sample expenses ------------------------------------------- #
        # Cover all 7 fixed categories (one appears twice to total 8).
        # Dates spread across the current month.
        today = date.today()
        year, month = today.year, today.month

        # First of the month, then a few days later in the month.
        d1 = f"{year:04d}-{month:02d}-01"
        d2 = f"{year:04d}-{month:02d}-03"
        d3 = f"{year:04d}-{month:02d}-05"
        d4 = f"{year:04d}-{month:02d}-08"
        d5 = f"{year:04d}-{month:02d}-12"
        d6 = f"{year:04d}-{month:02d}-15"
        d7 = f"{year:04d}-{month:02d}-20"
        d8 = f"{year:04d}-{month:02d}-{min(today.day, 28):02d}"

        sample_expenses = [
            (demo_user_id, 12.50, "Food",          d1, "Lunch with team"),
            (demo_user_id, 45.00, "Transport",     d2, "Monthly metro pass"),
            (demo_user_id, 89.99, "Bills",         d3, "Internet bill"),
            (demo_user_id, 32.40, "Health",        d4, "Pharmacy"),
            (demo_user_id, 15.00, "Entertainment", d5, "Movie tickets"),
            (demo_user_id, 67.80, "Shopping",      d6, "Groceries"),
            (demo_user_id, 25.00, "Other",         d7, None),
            (demo_user_id,  8.75, "Food",          d8, "Morning coffee"),
        ]

        conn.executemany(
            """
            INSERT INTO expenses (user_id, amount, category, date, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            sample_expenses,
        )

        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    """Look up a user by their (already-normalised) email address.

    The caller is responsible for trimming and lowercasing the email before
    passing it in; this function does no normalization so it stays a
    single-purpose lookup. Returns a sqlite3.Row with id, name, email,
    password_hash, and created_at, or None if no row matches.

    The connection is opened via get_db() so row_factory and
    PRAGMA foreign_keys are consistent with the rest of the data layer.
    """
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, password_hash, created_at "
            "FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    """Look up a user by primary key.

    Returns a sqlite3.Row with id, name, email, password_hash, and created_at,
    or None if no row matches. The caller is responsible for any defensive
    handling (e.g. clearing a stale session if the row has been deleted).

    The connection is opened via get_db() so row_factory and
    PRAGMA foreign_keys are consistent with the rest of the data layer.
    """
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, password_hash, created_at "
            "FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


# === AGENT_1_DB ===
def get_expense_stats(user_id, date_from=None, date_to=None):
    """Aggregate total spent, transaction count, and top category for a user.

    Optional date-range filter: when both `date_from` and `date_to` are
    provided (ISO ``"YYYY-MM-DD"`` strings), results are restricted to
    expenses with ``date BETWEEN date_from AND date_to``. Passing only one
    bound is treated as "no filter" — the contract is both-or-none, so the
    helper stays simple and the caller never sees a half-applied range.
    With both bounds ``None`` the generated SQL and param tuple are
    identical to the pre-filter behaviour (no regression for the
    unfiltered case).

    Returns a sqlite3.Row with keys:
        - total_spent: float (sum of amount, or 0.0 if no expenses)
        - transaction_count: int (COUNT(*), or 0)
        - top_category: str or None (category with highest SUM(amount)
          within the active range; ties broken alphabetically via
          ORDER BY total DESC, category ASC; None when the user has zero
          expenses in the range)

    The correlated subquery that produces ``top_category`` receives the
    same date filter as the outer query, so the "Top category" stat
    always agrees with the "Total spent" stat.

    Opens its own connection via get_db() and closes it before returning.
    """
    conn = get_db()
    try:
        if date_from is not None and date_to is not None:
            sql = """
                SELECT
                    COALESCE(SUM(amount), 0.0) AS total_spent,
                    COUNT(*)                    AS transaction_count,
                    (
                        SELECT category
                        FROM expenses
                        WHERE user_id = ? AND date BETWEEN ? AND ?
                        GROUP BY category
                        ORDER BY SUM(amount) DESC, category ASC
                        LIMIT 1
                    ) AS top_category
                FROM expenses
                WHERE user_id = ? AND date BETWEEN ? AND ?
            """
            params = (user_id, date_from, date_to, user_id, date_from, date_to)
        else:
            sql = """
                SELECT
                    COALESCE(SUM(amount), 0.0) AS total_spent,
                    COUNT(*)                    AS transaction_count,
                    (
                        SELECT category
                        FROM expenses
                        WHERE user_id = ?
                        GROUP BY category
                        ORDER BY SUM(amount) DESC, category ASC
                        LIMIT 1
                    ) AS top_category
                FROM expenses
                WHERE user_id = ?
            """
            params = (user_id, user_id)
        row = conn.execute(sql, params).fetchone()
        return row
    finally:
        conn.close()


# === AGENT_2_DB ===
def get_recent_expenses(user_id, limit=8, date_from=None, date_to=None):
    """Return the user's `limit` most recent expenses, optionally within a date range.

    When both `date_from` and `date_to` are provided (ISO ``"YYYY-MM-DD"``
    strings), results are restricted to expenses with
    ``date BETWEEN date_from AND date_to``. Passing only one bound is
    treated as "no filter" — see ``get_expense_stats`` for the rationale.
    With both bounds ``None`` the generated SQL and param tuple are
    identical to the pre-filter behaviour.

    Returns:
        list[sqlite3.Row] with columns id, amount, category, date, description,
        ordered by date DESC, id DESC (most recent first). Returns an empty
        list (not None) when the user has no matching expenses.

    Opens its own connection via get_db() and closes it before returning.
    """
    conn = get_db()
    try:
        if date_from is not None and date_to is not None:
            sql = (
                "SELECT id, amount, category, date, description "
                "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
                "ORDER BY date DESC, id DESC LIMIT ?"
            )
            params = (user_id, date_from, date_to, limit)
        else:
            sql = (
                "SELECT id, amount, category, date, description "
                "FROM expenses WHERE user_id = ? "
                "ORDER BY date DESC, id DESC LIMIT ?"
            )
            params = (user_id, limit)
        rows = conn.execute(sql, params).fetchall()
        return list(rows)
    finally:
        conn.close()


# === AGENT_3_DB ===


def get_category_totals(user_id, date_from=None, date_to=None):
    """Return per-category spend for a user within an optional date range.

    When both `date_from` and `date_to` are provided (ISO ``"YYYY-MM-DD"``
    strings), results are restricted to expenses with
    ``date BETWEEN date_from AND date_to``. Passing only one bound is
    treated as "no filter" — see ``get_expense_stats`` for the rationale.
    With both bounds ``None`` the generated SQL and param tuple are
    identical to the pre-filter behaviour.

    Returns:
        list[sqlite3.Row] with columns (category, total) where total is
        SUM(amount) for that category within the range. Categories with
        no matching expenses are NOT included — the caller is responsible
        for merging with the CATEGORIES constant to render zero rows for
        missing categories. Ordered by total DESC, category ASC for
        deterministic tie-breaking.

    Opens its own connection via get_db() and closes it before returning.
    """
    conn = get_db()
    try:
        if date_from is not None and date_to is not None:
            sql = (
                "SELECT category, COALESCE(SUM(amount), 0.0) AS total "
                "FROM expenses WHERE user_id = ? AND date BETWEEN ? AND ? "
                "GROUP BY category "
                "ORDER BY total DESC, category ASC"
            )
            params = (user_id, date_from, date_to)
        else:
            sql = (
                "SELECT category, COALESCE(SUM(amount), 0.0) AS total "
                "FROM expenses WHERE user_id = ? "
                "GROUP BY category "
                "ORDER BY total DESC, category ASC"
            )
            params = (user_id,)
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()

