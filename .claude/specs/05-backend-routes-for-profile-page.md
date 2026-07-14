# Spec: Backend Routes For Profile Page

## Overview
This step wires the `/profile` page up to real database queries. The Step 4 implementation rendered hardcoded mock data (stats, transaction rows, category totals) so the UI could be designed and reviewed in isolation. Step 5 replaces every literal in `app.py:180-205` with a real SQLite aggregate / lookup against the `expenses` table, scoped to the logged-in user. The template (`templates/profile.html`) and its stylesheet (`static/css/profile.css`) do not change — they already render whatever context the route passes in, so the same shape is preserved with real values.

## Depends on
- Step 1: Database setup (`expenses` table with `(user_id, amount, category, date, description)` must exist)
- Step 2: Registration (user accounts must exist)
- Step 3: Login + Logout (session must be set; `/profile` must be a protected route)
- Step 4: Profile Page (template and hardcoded context shape must already be in place)

## Routes
No new routes. The existing route is modified:
- `GET /profile` — render the profile page with real DB-driven data — logged-in only (redirect to `/login` if not authenticated)

## Database changes
No schema changes. The existing `expenses` and `users` tables are sufficient.

The step introduces **new helper functions in `database/db.py`** (no inline SQL in `app.py` — keeps the data layer centralised per CLAUDE.md):

| Helper | Returns | Purpose |
|---|---|---|
| `get_expense_stats(user_id)` | `dict` with keys `total_spent` (float or 0.0), `transaction_count` (int), `top_category` (str or `None`) | Aggregates over the user's expenses. `top_category` is the category with the highest total spend; ties broken by alphabetical order for determinism. |
| `get_recent_expenses(user_id, limit=8)` | `list[sqlite3.Row]` ordered by `date DESC, id DESC` | Most recent N expenses for the transaction history table. |
| `get_category_totals(user_id)` | `list[sqlite3.Row]` with `(category, total)` ordered by `total DESC, category ASC` | Per-category spend for the category breakdown section. |

All three helpers open their own connection via `get_db()` and close it before returning, matching the style of `get_user_by_email` / `get_user_by_id` already in the file.

## Templates
- **Modify:** `templates/profile.html` — no changes. The template already iterates `stats`, `transactions`, and `categories` and renders them via the existing category-badge classes, so swapping the data source in `app.py` is enough.
- No new templates.

## Files to change
- `app.py` — `/profile` view function only:
  - Remove the three hardcoded Python literals (`profile_stats`, `profile_transactions`, `profile_categories`).
  - Call the three new `database.db` helpers, scoped to `session["user_id"]`.
  - Format the results to match the shape the template already expects:
    - `stats` → list of `{"label": str, "value": str}` with currency-formatted amounts (`₹1,248.50` style)
    - `transactions` → list of `{"date": "YYYY-MM-DD", "description": str | "", "category": str, "amount": "₹…"}`
    - `categories` → list of `{"name": str, "total": "₹…"}` (always include all 7 fixed categories; show `₹0.00` when a user has no expenses in that category, so the breakdown list stays complete)
  - Handle the empty-state: a brand-new user with no expenses must still see a valid page (total `₹0.00`, count `0`, top category `—`, empty transaction list, all seven categories at `₹0.00`).
- `database/db.py` — add the three helpers listed under *Database changes* above.

## Files to create
No new files.

## New dependencies
No new dependencies. Uses only `sqlite3` from the standard library and the existing `get_db()` helper.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()`
- Parameterised queries only — never string-format SQL (use `?` placeholders)
- All DB logic in `database/db.py` — no `conn.execute(...)` calls inside route functions
- Each helper opens and closes its own connection (no shared connection / no connection leaks)
- Use CSS variables — never hardcode hex values (no template changes, but do not introduce inline styles in any modified file)
- All templates extend `base.html` (no change — the profile template already does)
- Passwords hashed with werkzeug (no auth changes in this step)
- Authentication guard stays in place: `session.get("user_id")` must be checked first; redirect to `/login` if missing
- Defensive: if the user row is missing despite a valid session (e.g. account deleted out from under us), clear the session and redirect to `/login` — this behaviour already exists in Step 4 and must be preserved
- Never expose `password_hash` to the template (already handled — only `name`, `email`, `created_at` are read)
- Currency formatting: use `f"₹{amount:,.2f}"` for amounts; render `0.00` (not `0`) so the visual style matches the seeded demo data
- Category list: the seven fixed values (`Food, Transport, Bills, Health, Entertainment, Shopping, Other`) must always be shown, in that order, with `₹0.00` when a user has none in that category — use a Python module-level constant `CATEGORIES = (...)` in `database/db.py` so the list is single-sourced
- Top-category tie-breaker: alphabetical (`ORDER BY total DESC, category ASC`) for deterministic rendering

## Definition of done
- [ ] Visiting `/profile` while logged in returns HTTP 200 and renders the same layout as Step 4
- [ ] The "Total spent" tile shows the real `SUM(amount)` for the logged-in user, formatted as `₹X,XXX.XX`
- [ ] The "Transactions" tile shows the real `COUNT(*)` of the logged-in user's expenses
- [ ] The "Top category" tile shows the category with the highest total spend, or `—` when the user has zero expenses
- [ ] The transaction history table shows the user's most recent 8 expenses, ordered by date descending (most recent first)
- [ ] When a user has fewer than 8 expenses, the table shows only what they have (no blank rows)
- [ ] The category breakdown list always shows all 7 fixed categories, with `₹0.00` for any category the user has no expenses in
- [ ] Switching to a user with zero expenses (e.g. a freshly registered account) renders a valid page — no tracebacks, no empty sections
- [ ] The totals in the stat tiles match the sum of the per-category amounts in the breakdown list
- [ ] `app.py` contains zero `conn.execute(...)` calls inside the `profile()` function (all queries live in `database/db.py`)
- [ ] All SQL uses `?` placeholders — no f-strings, no `+` concatenation, no `.format()` calls in SQL
- [ ] `pytest` still runs cleanly (no test regressions; the suite may still be empty, but it must not break)
- [ ] Logging in as `demo@spendly.com` / `demo123` (the seeded demo user with 8 expenses) shows non-zero values across the page that match the seed data
