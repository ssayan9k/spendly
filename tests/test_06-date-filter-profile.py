"""Tests for Spec 06: Date filter on /profile page.

These tests target the BEHAVIOR described in the spec — the public
``GET /profile`` route and the three DB helpers it calls — not the
internal helper function names. Tests run against a temp SQLite DB
(see ``conftest.py``) so the real ``expense_tracker.db`` is never
touched.

"Today" is pinned to 2026-07-15 via ``conftest._FakeDate`` so preset
ranges are deterministic regardless of the host clock.
"""
import re

import pytest


# ============================================================== #
# Happy path — default /profile and the four presets             #
# ============================================================== #

def test_profile_no_query_params_shows_all_expenses(client, seeded_user):
    """Default GET /profile (no query params) shows all 10 expenses."""
    resp = client.get("/profile")
    assert resp.status_code == 200

    # Total spent = sum of all 10 expenses = 550.00
    assert b"\xe2\x82\xb9550.00" in resp.data, (
        "Expected total spent ₹550.00 for unfiltered view"
    )

    # Out-of-range expenses from the test data (the January one) must appear.
    assert b"2026-01-15" in resp.data, "January expense should appear in unfiltered view"
    assert b"2026-04-12" in resp.data, "April expense should appear in unfiltered view"

    # Per-category totals (only visible in the unfiltered view).
    # Transport all-time = 20.00 + 100.00 = 120.00
    assert b"\xe2\x82\xb9120.00" in resp.data, "Transport all-time total ₹120.00 should appear"
    # Food all-time = 10.00 + 50.00 + 90.00 = 150.00
    assert b"\xe2\x82\xb9150.00" in resp.data, "Food all-time total ₹150.00 should appear"


def test_profile_preset_this_month_filters_to_current_month(client, seeded_user):
    """This Month preset shows only July 2026 expenses (4 rows, ₹100.00)."""
    resp = client.get(
        "/profile",
        query_string={"date_from": "2026-07-01", "date_to": "2026-07-15"},
    )
    assert resp.status_code == 200

    # July total = 10 + 20 + 30 + 40 = 100.00
    assert b"\xe2\x82\xb9100.00" in resp.data, "Expected July total ₹100.00"

    # Out-of-range months must NOT appear in the transaction table.
    assert b"2026-06-15" not in resp.data, "June expense should be filtered out"
    assert b"2026-05-10" not in resp.data, "May expense should be filtered out"
    assert b"2026-04-12" not in resp.data, "April expense should be filtered out"
    assert b"2026-01-15" not in resp.data, "January expense should be filtered out"

    # July dates must appear.
    assert b"2026-07-01" in resp.data
    assert b"2026-07-14" in resp.data

    # Per-category breakdown must reflect the filter.
    # July Transport = 20.00 (the all-time 120.00 must NOT appear).
    assert b"\xe2\x82\xb920.00" in resp.data, "July Transport total ₹20.00 should appear"
    assert b"\xe2\x82\xb9120.00" not in resp.data, (
        "All-time Transport total ₹120.00 should NOT appear in This Month view"
    )

    # The active-pill check: "This Month" should carry aria-current="page".
    assert b'aria-current="page">This Month</a>' in resp.data, (
        "This Month pill should be visually active"
    )


def test_profile_preset_last_3_months(client, seeded_user):
    """Last 3 Months preset covers May, Jun, Jul 2026 (₹360.00, 8 expenses)."""
    resp = client.get(
        "/profile",
        query_string={"date_from": "2026-05-01", "date_to": "2026-07-15"},
    )
    assert resp.status_code == 200

    # May + Jun + Jul = 10+20+30+40+50+60+70+80 = 360.00
    assert b"\xe2\x82\xb9360.00" in resp.data, "Expected Last 3 Months total ₹360.00"

    # In-range dates must appear.
    assert b"2026-07-01" in resp.data
    assert b"2026-06-15" in resp.data
    assert b"2026-05-10" in resp.data

    # Out-of-range dates must NOT appear.
    assert b"2026-04-12" not in resp.data, "April expense should be excluded"
    assert b"2026-01-15" not in resp.data, "January expense should be excluded"

    # All-time Transport total (120.00) must NOT appear; July Transport (20.00) should.
    assert b"\xe2\x82\xb9120.00" not in resp.data


def test_profile_preset_last_6_months(client, seeded_user):
    """Last 6 Months preset covers Feb–Jul 2026 (9 expenses, ₹450.00)."""
    resp = client.get(
        "/profile",
        query_string={"date_from": "2026-02-01", "date_to": "2026-07-15"},
    )
    assert resp.status_code == 200

    # All expenses EXCEPT the January one (100.00) = 550 - 100 = 450.00
    assert b"\xe2\x82\xb9450.00" in resp.data, "Expected Last 6 Months total ₹450.00"

    # April (2026-04-12) is in the Feb–Jul range and must appear.
    assert b"2026-04-12" in resp.data, "April expense should be in the 6-month window"

    # January (2026-01-15) is outside the range and must NOT appear.
    assert b"2026-01-15" not in resp.data, "January expense should be excluded"


def test_profile_preset_all_time_has_clean_url(client, seeded_user):
    """The 'All Time' preset link must have href=/profile (no query string)."""
    resp = client.get("/profile")
    assert resp.status_code == 200

    # Find the <a> tag wrapping the 'All Time' label and inspect its href.
    match = re.search(
        rb'<a\s+href="([^"]*)"[^>]*>\s*All Time\s*</a>',
        resp.data,
    )
    assert match is not None, "All Time pill link not found in /profile HTML"
    href = match.group(1)
    assert href == b"/profile", (
        f"All Time href should be a clean '/profile' with no query string, "
        f"got {href!r}"
    )
    # Belt-and-braces: the href must contain no '?' character.
    assert b"?" not in href


def test_profile_custom_range_with_valid_dates(client, seeded_user):
    """A custom range filters all three sections (stats, transactions, categories)."""
    resp = client.get(
        "/profile",
        query_string={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert resp.status_code == 200

    # June only: 50 + 60 = 110.00
    assert b"\xe2\x82\xb9110.00" in resp.data, "Expected June total ₹110.00"

    # In-range June dates must appear.
    assert b"2026-06-15" in resp.data
    assert b"2026-06-20" in resp.data

    # Out-of-range dates must NOT appear.
    assert b"2026-07-01" not in resp.data, "July expense should be excluded"
    assert b"2026-05-10" not in resp.data, "May expense should be excluded"
    assert b"2026-04-12" not in resp.data, "April expense should be excluded"

    # Category breakdown must reflect the filter.
    # June Food = 50.00, June Entertainment = 60.00.
    assert b"\xe2\x82\xb950.00" in resp.data
    assert b"\xe2\x82\xb960.00" in resp.data
    # All-time Food (150.00) and all-time Entertainment (60.00 only in June,
    # so 60.00 IS correct here — we just need to check 150.00 is absent).
    assert b"\xe2\x82\xb9150.00" not in resp.data, (
        "All-time Food total ₹150.00 should NOT appear in June-only view"
    )


# ============================================================== #
# Active-pill / filter-bar visual state                           #
# ============================================================== #

def test_profile_all_time_pill_is_active_by_default(client, seeded_user):
    """With no query params, the 'All Time' pill carries aria-current='page'."""
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b'aria-current="page">All Time</a>' in resp.data, (
        "All Time pill should be the active pill when no filter is applied"
    )


def test_profile_custom_range_has_no_active_pill(client, seeded_user):
    """A custom (non-preset) range must NOT highlight any preset pill."""
    resp = client.get(
        "/profile",
        query_string={"date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert resp.status_code == 200
    # Only active pills carry aria-current="page"; a custom range matches none.
    assert b'aria-current="page"' not in resp.data, (
        "No preset pill should be active for a custom date range"
    )


def test_profile_preset_links_contain_iso_date_params(client, seeded_user):
    """The This Month preset link must include date_from=2026-07-01 and date_to=2026-07-15."""
    resp = client.get("/profile")
    assert resp.status_code == 200
    # Flask's url_for renders these as URL-encoded query params.
    assert b"date_from=2026-07-01" in resp.data, (
        "This Month preset link should include date_from=2026-07-01"
    )
    assert b"date_to=2026-07-15" in resp.data, (
        "This Month preset link should include date_to=2026-07-15"
    )


# ============================================================== #
# Edge cases & validation                                          #
# ============================================================== #

def test_profile_start_after_end_flashes_error(client, seeded_user):
    """date_from > date_to flashes the spec message and falls back to unfiltered."""
    resp = client.get(
        "/profile",
        query_string={"date_from": "2026-07-15", "date_to": "2026-07-01"},
    )
    assert resp.status_code == 200

    # Flash message must be present in the rendered HTML.
    assert b"Start date must be before end date." in resp.data, (
        "Spec flash message should appear when date_from > date_to"
    )

    # Data must fall back to unfiltered (all 10 expenses, ₹550.00).
    assert b"\xe2\x82\xb9550.00" in resp.data, (
        "Total should fall back to unfiltered ₹550.00"
    )
    assert b"2026-01-15" in resp.data, "January expense should appear in fallback view"

    # And the 'All Time' pill should be the active one after the fallback.
    assert b'aria-current="page">All Time</a>' in resp.data


def test_profile_malformed_date_silent_fallback(client, seeded_user):
    """A malformed date_from must not crash; route silently falls back to unfiltered."""
    resp = client.get(
        "/profile",
        query_string={"date_from": "not-a-date", "date_to": "2026-07-15"},
    )
    # Must NOT be a 500 error.
    assert resp.status_code == 200, "Malformed date must not cause a 500 error"

    # No 'start after end' flash (only one bound is valid).
    assert b"Start date must be before end date." not in resp.data

    # Data falls back to unfiltered.
    assert b"\xe2\x82\xb9550.00" in resp.data
    assert b"2026-01-15" in resp.data


def test_profile_only_date_from_falls_back_to_unfiltered(client, seeded_user):
    """Per the spec: if either bound is absent, the route falls back to unfiltered.

    The DB helpers treat "only one bound" as "no filter", so the route
    passes (date_from=X, date_to=None) to them and gets unfiltered data.
    """
    resp = client.get(
        "/profile",
        query_string={"date_from": "2026-07-01"},  # no date_to
    )
    assert resp.status_code == 200
    # All 10 expenses should still be visible.
    assert b"\xe2\x82\xb9550.00" in resp.data
    assert b"2026-01-15" in resp.data


def test_profile_empty_range_shows_zeros_and_em_dash(client, seeded_user):
    """A range matching zero expenses shows ₹0.00, 0 transactions, em-dash top category."""
    resp = client.get(
        "/profile",
        query_string={"date_from": "2025-01-01", "date_to": "2025-12-31"},
    )
    assert resp.status_code == 200

    # Total spent must be ₹0.00.
    assert b"\xe2\x82\xb90.00" in resp.data, "Empty range should show total ₹0.00"

    # Top category must be the em-dash (U+2014) placeholder.
    # The full UTF-8 encoding of — is \xe2\x80\x94.
    assert b"\xe2\x80\x94" in resp.data, "Empty range should show em-dash for Top category"

    # No transaction dates should appear.
    assert b"2026-07-01" not in resp.data
    assert b"2026-06-15" not in resp.data
    assert b"2026-01-15" not in resp.data

    # The category breakdown must still render all 7 CATEGORIES, each at ₹0.00.
    for category in (
        b"Food", b"Transport", b"Bills", b"Health",
        b"Entertainment", b"Shopping", b"Other",
    ):
        assert category in resp.data, f"Category {category!r} should still appear in breakdown"


def test_profile_rupee_symbol_always_shown(client, seeded_user):
    """The ₹ rupee symbol must appear in the response for every filter state."""
    for qs in (
        {},                                                       # unfiltered
        {"date_from": "2026-07-01", "date_to": "2026-07-15"},    # this month
        {"date_from": "2026-02-01", "date_to": "2026-07-15"},    # last 6 months
        {"date_from": "2025-01-01", "date_to": "2025-12-31"},    # empty range
    ):
        resp = client.get("/profile", query_string=qs)
        assert resp.status_code == 200
        # UTF-8 encoding of ₹ is \xe2\x82\xb9.
        assert b"\xe2\x82\xb9" in resp.data, (
            f"₹ symbol missing from /profile response for query={qs}"
        )


# ============================================================== #
# Auth guard                                                       #
# ============================================================== #

def test_profile_unauthenticated_redirects_to_login(client):
    """Unauthenticated GET /profile must redirect to /login."""
    resp = client.get("/profile")
    assert resp.status_code == 302, (
        f"Unauthenticated /profile should redirect, got {resp.status_code}"
    )
    location = resp.headers.get("Location", "")
    assert "/login" in location, (
        f"Redirect target should be /login, got {location!r}"
    )


# ============================================================== #
# DB helper behavior — tested directly through the data layer          #
# ============================================================== #

def test_get_recent_expenses_filters_by_date(app):
    """get_recent_expenses must restrict results to the date range when both bounds are set."""
    from database.db import get_db, get_recent_expenses, init_db

    # Set up an isolated user + expenses.
    init_db()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Helper Test", "helper@test.com", "hash"),
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("helper@test.com",)
        ).fetchone()["id"]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 10.0, "Food", "2026-07-01", "in range"),
                (user_id, 20.0, "Food", "2026-07-10", "in range"),
                (user_id, 30.0, "Food", "2026-06-15", "out of range"),
                (user_id, 40.0, "Food", "2026-01-15", "out of range"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    # Unfiltered: all 4 expenses.
    all_rows = get_recent_expenses(user_id, limit=100)
    assert len(all_rows) == 4

    # Filtered to July: 2 expenses.
    july_rows = get_recent_expenses(
        user_id, limit=100, date_from="2026-07-01", date_to="2026-07-31",
    )
    assert len(july_rows) == 2
    returned_dates = {row["date"] for row in july_rows}
    assert returned_dates == {"2026-07-01", "2026-07-10"}


def test_get_category_totals_filters_by_date(app):
    """get_category_totals must restrict the per-category sums to the date range."""
    from database.db import get_db, get_category_totals, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Cat Test", "cat@test.com", "hash"),
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("cat@test.com",)
        ).fetchone()["id"]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, 10.0, "Food", "2026-07-01", "july food"),
                (user_id, 20.0, "Food", "2026-07-10", "july food"),
                (user_id, 50.0, "Food", "2026-06-15", "june food"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    # Unfiltered: Food = 80.0
    all_cats = get_category_totals(user_id)
    food_total = next(c["total"] for c in all_cats if c["category"] == "Food")
    assert food_total == 80.0

    # Filtered to July: Food = 30.0
    july_cats = get_category_totals(
        user_id, date_from="2026-07-01", date_to="2026-07-31",
    )
    food_total_july = next(c["total"] for c in july_cats if c["category"] == "Food")
    assert food_total_july == 30.0

    # Filtered to an empty range: no category rows at all.
    empty_cats = get_category_totals(
        user_id, date_from="2025-01-01", date_to="2025-12-31",
    )
    assert empty_cats == []


def test_get_expense_stats_subquery_respects_date_filter(app):
    """The top_category subquery in get_expense_stats must receive the date filter.

    Concretely: if the overall top category is Transport (200.00 in June)
    and the July top category is Food (100.00), then filtering the stats
    call to July must report Food — not Transport.
    """
    from database.db import get_db, get_expense_stats, init_db

    init_db()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Stats Test", "stats@test.com", "hash"),
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("stats@test.com",)
        ).fetchone()["id"]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                # Overall top: Transport at 200.00
                (user_id, 200.00, "Transport", "2026-06-15", "big transport"),
                # July top: Food at 100.00 (50 + 50)
                (user_id,  50.00, "Food",      "2026-07-05", "july food 1"),
                (user_id,  50.00, "Food",      "2026-07-12", "july food 2"),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    # Unfiltered: Transport is the overall top.
    overall = get_expense_stats(user_id)
    assert overall["top_category"] == "Transport"
    assert overall["total_spent"] == 300.00
    assert overall["transaction_count"] == 3

    # Filtered to July: Food is the top, Transport is excluded.
    july = get_expense_stats(
        user_id, date_from="2026-07-01", date_to="2026-07-31",
    )
    assert july["top_category"] == "Food", (
        "top_category subquery must receive the date filter; "
        "July's top should be Food, not the overall top Transport"
    )
    assert july["total_spent"] == 100.00
    assert july["transaction_count"] == 2


def test_queries_use_parameterized_placeholders(app):
    """Date params containing SQL-special characters must be treated as data, not SQL.

    If the helpers were string-formatting dates into SQL, a value like
    ``"' OR '1'='1"`` would either raise a SQL syntax error or return
    all rows. With parameterized queries, the string is bound as a
    parameter and simply matches no date — so the helpers return empty
    results without raising.
    """
    from database.db import (
        get_category_totals,
        get_db,
        get_expense_stats,
        get_recent_expenses,
        init_db,
    )

    init_db()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Injection Test", "inject@test.com", "hash"),
        )
        user_id = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("inject@test.com",)
        ).fetchone()["id"]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(user_id, 10.0, "Food", "2026-07-01", "test expense")],
        )
        conn.commit()
    finally:
        conn.close()

    injection = "' OR '1'='1"

    # None of these should raise; all should return empty / zero results
    # because the injection string does not match any real date.
    rows = get_recent_expenses(
        user_id, date_from=injection, date_to=injection,
    )
    assert rows == [], (
        "get_recent_expenses must treat date params as data (parameterized). "
        f"Got {len(rows)} rows for injection payload."
    )

    cats = get_category_totals(user_id, injection, injection)
    assert cats == [], (
        "get_category_totals must treat date params as data (parameterized). "
        f"Got {len(cats)} category rows for injection payload."
    )

    stats = get_expense_stats(user_id, injection, injection)
    assert stats["total_spent"] == 0.0
    assert stats["transaction_count"] == 0
    assert stats["top_category"] is None
