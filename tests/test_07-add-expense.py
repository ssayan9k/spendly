"""Tests for Spec 07: Add Expense.

These tests target the BEHAVIOR described in the spec — the public
``GET /expenses/add`` and ``POST /expenses/add`` routes and the
``insert_expense`` helper — not internal helper function names.
Tests run against a temp SQLite DB (see ``conftest.py``) so the real
``expense_tracker.db`` is never touched.

"Today" is pinned to 2026-07-15 via ``conftest._FakeDate`` so any
default-date behavior is deterministic regardless of the host clock.
"""
import sqlite3

import pytest

import database.db as db
from database.db import CATEGORIES


# ============================================================== #
# Unit tests — insert_expense                                     #
# ============================================================== #

def test_insert_expense_with_description_round_trips(app):
    """A row inserted via insert_expense can be read back with the same fields."""
    with app.app_context():
        # Set up: one user, no expenses.
        conn = db.get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) "
                "VALUES (?, ?, ?)",
                ("Alice", "alice@example.com", "x"),
            )
            user_id = conn.execute(
                "SELECT id FROM users WHERE email = ?", ("alice@example.com",)
            ).fetchone()["id"]
            conn.commit()
        finally:
            conn.close()

        # Act
        new_id = db.insert_expense(
            user_id=user_id,
            amount=50.0,
            category="Food",
            date="2026-03-20",
            description="Lunch",
        )

        # Assert — row exists and round-trips
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT user_id, amount, category, date, description "
                "FROM expenses WHERE id = ?",
                (new_id,),
            ).fetchone()
        finally:
            conn.close()

        assert row is not None, "insert_expense should return the new row's id"
        assert row["user_id"] == user_id
        assert row["amount"] == 50.0
        assert row["category"] == "Food"
        assert row["date"] == "2026-03-20"
        assert row["description"] == "Lunch"


def test_insert_expense_with_none_description_stores_null(app):
    """Passing description=None stores NULL in the description column."""
    with app.app_context():
        conn = db.get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) "
                "VALUES (?, ?, ?)",
                ("Bob", "bob@example.com", "x"),
            )
            user_id = conn.execute(
                "SELECT id FROM users WHERE email = ?", ("bob@example.com",)
            ).fetchone()["id"]
            conn.commit()
        finally:
            conn.close()

        new_id = db.insert_expense(
            user_id=user_id,
            amount=12.5,
            category="Transport",
            date="2026-03-20",
            description=None,
        )

        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses WHERE id = ?", (new_id,)
            ).fetchone()
        finally:
            conn.close()

        assert row is not None
        assert row["description"] is None, (
            "description=None should be stored as SQL NULL, not the string 'None'"
        )


# ============================================================== #
# Route tests — GET /expenses/add                                  #
# ============================================================== #

def test_get_add_expense_unauthenticated_redirects_to_login(client):
    """GET /expenses/add while logged out → 302 to /login."""
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_get_add_expense_authenticated_returns_form_with_select_and_post_form(client, seeded_user):
    """GET /expenses/add while logged in returns 200 and a form with the category select."""
    resp = client.get("/expenses/add")
    assert resp.status_code == 200

    body = resp.data.decode("utf-8")

    # The form must POST to /expenses/add
    assert "<form" in body, "Response should contain a <form> element"
    assert 'method="POST"' in body or "method='POST'" in body, "Form should use POST"
    assert "/expenses/add" in body, "Form should submit to /expenses/add"

    # The category select must contain all 7 fixed options.
    assert "<select" in body, "Response should contain a <select> for category"
    for cat in CATEGORIES:
        assert f">{cat}</option>" in body, f"Category {cat!r} must be a <select> option"


# ============================================================== #
# Route tests — POST /expenses/add (auth)                         #
# ============================================================== #

def test_post_add_expense_unauthenticated_redirects_to_login(client):
    """POST /expenses/add while logged out → 302 to /login."""
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        },
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_post_add_expense_valid_data_inserts_and_redirects(client, seeded_user, app):
    """Valid POST inserts a row, then redirects to /profile."""
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "50.00",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302, f"Expected 302, got {resp.status_code}"
    assert "/profile" in resp.headers["Location"], (
        f"Should redirect to /profile, got {resp.headers['Location']}"
    )

    # Row exists in the DB for the test user.
    with app.app_context():
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT id, amount, category, date, description "
                "FROM expenses WHERE date = ? AND category = ?",
                ("2026-03-20", "Food"),
            ).fetchone()
        finally:
            conn.close()

    assert row is not None, "Expected the new expense row to be in the database"
    assert row["amount"] == 50.00
    assert row["description"] == "Lunch"


# ============================================================== #
# Route tests — POST validation (each branch re-renders form)     #
# ============================================================== #

def test_post_add_expense_missing_amount_shows_error(client, seeded_user):
    """Missing amount → 200 with an error message, no row inserted."""
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "",
            "category": "Food",
            "date": "2026-03-20",
            "description": "Lunch",
        },
    )
    assert resp.status_code == 200, "Form should re-render on validation failure"
    body = resp.data.decode("utf-8").lower()
    # An error message of some kind must be on the page.
    assert "amount" in body, "Error message should mention the amount field"
    # And the category the user submitted should be retained.
    assert "food" in body, "Previously selected category should be retained"


def test_post_add_expense_zero_amount_shows_error(client, seeded_user):
    """Amount = 0 → 200 with an error message."""
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "0",
            "category": "Food",
            "date": "2026-03-20",
            "description": "",
        },
    )
    assert resp.status_code == 200
    body = resp.data.decode("utf-8").lower()
    # Error should reference the amount / zero / positive constraint.
    assert ("zero" in body or "greater" in body or "positive" in body), (
        "Error message should explain the amount must be greater than zero"
    )


def test_post_add_expense_non_numeric_amount_shows_error(client, seeded_user):
    """Non-numeric amount → 200 with an error message."""
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "not-a-number",
            "category": "Food",
            "date": "2026-03-20",
            "description": "",
        },
    )
    assert resp.status_code == 200
    body = resp.data.decode("utf-8").lower()
    assert "valid" in body or "number" in body, (
        "Error message should ask for a valid number"
    )


def test_post_add_expense_invalid_category_shows_error(client, seeded_user):
    """Category not in the fixed CATEGORIES list → 200 with an error."""
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "10.00",
            "category": "NotARealCategory",
            "date": "2026-03-20",
            "description": "",
        },
    )
    assert resp.status_code == 200
    body = resp.data.decode("utf-8").lower()
    assert "category" in body, "Error message should mention category"


def test_post_add_expense_invalid_date_shows_error(client, seeded_user):
    """Unparseable date string → 200 with an error."""
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "10.00",
            "category": "Food",
            "date": "not-a-date",
            "description": "",
        },
    )
    assert resp.status_code == 200
    body = resp.data.decode("utf-8").lower()
    assert "date" in body, "Error message should mention the date field"


def test_post_add_expense_no_description_inserts_null(client, seeded_user, app):
    """Empty description is allowed and stored as NULL."""
    resp = client.post(
        "/expenses/add",
        data={
            "amount": "25.00",
            "category": "Other",
            "date": "2026-03-21",
            "description": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302, "Valid submission with empty description should redirect"
    assert "/profile" in resp.headers["Location"]

    with app.app_context():
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT description FROM expenses "
                "WHERE date = ? AND category = ? AND amount = ?",
                ("2026-03-21", "Other", 25.00),
            ).fetchone()
        finally:
            conn.close()

    assert row is not None, "Row should have been inserted"
    assert row["description"] is None, (
        "Empty description should be stored as SQL NULL"
    )
