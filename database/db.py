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
