"""Shared pytest fixtures for Spendly tests.

Import-order matters here: we must patch ``database.db.DB_PATH`` to a
temp file BEFORE ``app`` is imported, because ``app.py`` calls
``init_db()`` and ``seed_db()`` at module load time. We also patch
``app.date`` with a ``FakeDate`` so the "today" used by the date-filter
presets is deterministic across machines.
"""
import tempfile
from datetime import date as _real_date

# ------------------------------------------------------------------ #
# 1. Temp DB path — created once at conftest load time, reused for    #
#    the whole test session. Never touches the real expense_tracker. #
# ------------------------------------------------------------------ #
_tmp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db_file.close()
TMP_DB_PATH = _tmp_db_file.name

# ------------------------------------------------------------------ #
# 2. Redirect the data layer to the temp DB. Must happen before app.  #
# ------------------------------------------------------------------ #
import database.db as _db_module
_db_module.DB_PATH = TMP_DB_PATH

# ------------------------------------------------------------------ #
# 3. Import app — triggers init_db() + seed_db() on the temp DB.     #
# ------------------------------------------------------------------ #
import app as _app_module  # noqa: E402  (import order is intentional)

# ------------------------------------------------------------------ #
# 4. Pin "today" to 2026-07-15 so preset math is deterministic.      #
#    app.py does ``from datetime import date, datetime`` so the       #
#    module-level reference is ``app.date``; replacing it here means  #
#    ``date.today()`` inside the profile() route returns the fake.   #
# ------------------------------------------------------------------ #
class _FakeDate(_real_date):
    """``datetime.date`` subclass with a fixed ``today()``."""

    @classmethod
    def today(cls):
        return _real_date(2026, 7, 15)


_app_module.date = _FakeDate


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #
import pytest  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402


@pytest.fixture
def app():
    """Flask app with a clean temp DB (no demo user, no expenses)."""
    _app_module.app.config["TESTING"] = True
    _app_module.app.config["SECRET_KEY"] = "test-secret"
    with _app_module.app.app_context():
        # Ensure tables exist (idempotent).
        _app_module.init_db()
        # Wipe any data left by the import-time seed_db() or previous tests.
        conn = _app_module.get_db()
        try:
            conn.execute("DELETE FROM expenses")
            conn.execute("DELETE FROM users")
            conn.commit()
        finally:
            conn.close()
        yield _app_module.app


@pytest.fixture
def client(app):
    """Unauthenticated Flask test client."""
    return app.test_client()


@pytest.fixture
def seeded_user(client):
    """A logged-in test user with expenses spanning several months.

    Expense layout (relative to pinned today = 2026-07-15):

        2026-07 (this month) : 4 expenses  — total  100.00
        2026-06              : 2 expenses  — total  110.00
        2026-05              : 2 expenses  — total  150.00
        2026-04              : 1 expense   — total   90.00
        2026-01              : 1 expense   — total  100.00
        ─────────────────────────────────────────────
        All time             : 10 expenses — total  550.00

    This lets us verify every preset range deterministically:

        This Month    (2026-07-01 → 2026-07-15) = 4 expenses, ₹100.00
        Last 3 Months (2026-05-01 → 2026-07-15) = 8 expenses, ₹360.00
        Last 6 Months (2026-02-01 → 2026-07-15) = 9 expenses, ₹450.00
        All Time                                = 10 expenses, ₹550.00
    """
    with _app_module.app.app_context():
        conn = _app_module.get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, email, password_hash) "
                "VALUES (?, ?, ?)",
                ("Test User", "test@spendly.com",
                 generate_password_hash("password")),
            )
            user_id = conn.execute(
                "SELECT id FROM users WHERE email = ?",
                ("test@spendly.com",),
            ).fetchone()["id"]

            expenses = [
                # 2026-07 (this month) — 4 expenses, ₹100.00
                (user_id,  10.00, "Food",          "2026-07-01", "Lunch 1"),
                (user_id,  20.00, "Transport",     "2026-07-05", "Bus pass"),
                (user_id,  30.00, "Bills",         "2026-07-10", "Electric"),
                (user_id,  40.00, "Health",        "2026-07-14", "Pharmacy"),
                # 2026-06 — 2 expenses, ₹110.00
                (user_id,  50.00, "Food",          "2026-06-15", "Groceries"),
                (user_id,  60.00, "Entertainment", "2026-06-20", "Movie"),
                # 2026-05 — 2 expenses, ₹150.00
                (user_id,  70.00, "Shopping",      "2026-05-10", "Clothes"),
                (user_id,  80.00, "Other",         "2026-05-25", "Misc"),
                # 2026-04 — 1 expense, ₹90.00
                (user_id,  90.00, "Food",          "2026-04-12", "Restaurant"),
                # 2026-01 — 1 expense, ₹100.00
                (user_id, 100.00, "Transport",     "2026-01-15", "Taxi"),
            ]
            conn.executemany(
                "INSERT INTO expenses "
                "(user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                expenses,
            )
            conn.commit()
        finally:
            conn.close()

    # Log the test user in via the real /login route.
    resp = client.post(
        "/login",
        data={"email": "test@spendly.com", "password": "password"},
    )
    assert resp.status_code == 302, (
        f"Login should redirect on success, got {resp.status_code}"
    )
    return client
