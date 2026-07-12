# Spec: Login and Logout

## Overview
Step 3 turns the existing `GET /login` stub into a working sign-in flow and the `GET /logout` placeholder into a real session-clearing endpoint. A returning user submits their email and password from the styled form, the email is matched (case-insensitive, against the canonical lowercase form written by Step 2) against the `users` table, the password is verified with `werkzeug.check_password_hash`, and on success a `user_id` is stored in the `session` and the user is redirected into the dashboard. A separate logout endpoint clears the session and sends the user back to the landing page. This wires up the second half of the auth loop that every later authenticated feature (profile, expenses) assumes.

## Depends on
- Step 1 — Database setup (the `users` table with `id`, `email` UNIQUE, `password_hash`).
- Step 2 — Registration (`session["user_id"]` is the auth marker, emails are stored lowercased, the dashboard view is the post-login landing target).

## Routes
- `GET /login` — render the sign-in form — public
- `POST /login` — validate input, look up user by email, verify password, set `session["user_id"]`, redirect to `/dashboard` on success or re-render the form with an error — public
- `GET /logout` — clear the session, redirect to `/` (landing) — logged-in (safe to call when already logged out)

## Database changes
No database changes. A new DB helper must be added to `database/db.py`:

- `get_user_by_email(email)` — returns the matching `users` row (as a `sqlite3.Row` with `id`, `name`, `email`, `password_hash`, `created_at`) or `None` if no row matches. Uses the existing `get_db()` connection and parameterized SQL.

The `users` table from Step 1 already has every column required for lookup and password verification.

## Templates
- **Modify:** `templates/login.html` — already renders the two-field form (email + password) and an `{{ error }}` block; no structural change needed, but verify it still extends `base.html` and that its `action="/login"` matches the new handler.
- **Modify:** `templates/base.html` — the top-right nav currently always shows `Sign in` + `Get started`. When the user is logged in (i.e. `session["user_id"]` is set), the nav should show `Dashboard` + `Log out` instead. Implement this with a Jinja `{% if session.user_id %}` block in the `.nav-links` div; no new files.
- **Modify:** `templates/dashboard.html` — extend the welcome card with a `Log out` button/link that hits `GET /logout`, so a freshly logged-in user has an obvious way out. Keep it minimal and consistent with existing `auth-card` styling.

## Files to change
- `app.py` — convert the `login()` view into a single function that handles both `GET` (render form) and `POST` (authenticate, set session, redirect); replace the `logout()` placeholder with a real handler that clears the session and redirects to `/`.
- `database/db.py` — add `get_user_by_email(email)`.
- `templates/login.html` — small adjustments only if the new handler needs extra fields or messages; preserve existing structure.
- `templates/base.html` — conditionally render logged-in vs logged-out nav links.
- `templates/dashboard.html` — add a `Log out` action.

## Files to create
- `.claude/specs/03-login-logout.md` — this spec.

No new template files. No new Python files.

## New dependencies
No new dependencies. Use:
- `sqlite3` (standard library) — already in use via `database/db.py`
- `werkzeug.security.check_password_hash` — already installed (Step 1 dependency)
- `flask.session` / `flask.redirect` / `flask.url_for` — already in use

## Rules for implementation
- No SQLAlchemy or any ORM — use the `sqlite3` connection returned by `get_db()`.
- Parameterised queries only — never interpolate user input into SQL strings.
- Never store or log plaintext passwords. The submitted password must be verified via `werkzeug.security.check_password_hash` against the stored `password_hash`.
- Look up the user by lowercased, trimmed email (matching the canonical form written by Step 2). Do not expose whether the email exists vs. the password was wrong — show a single generic "Invalid email or password." for both cases to avoid account-enumeration leaks.
- After a successful login, set `session["user_id"]` to the row's `id` (same shape Step 2 writes on registration) and redirect to `url_for("dashboard")`.
- If the credentials are wrong, re-render `login.html` with the generic error via the existing `{{ error }}` block — do not redirect (preserves the 200-with-inline-error pattern established in Step 2).
- `GET /logout` must call `session.clear()` before redirecting to `url_for("landing")`. Safe to hit while logged out — it should just clear an empty session and redirect. `/logout` is **not** gated on session state: the navbar's `Log out` link and the dashboard's `Log out` button both point at it, and it must stay reachable at all times.
- `GET /login` is soft-gated: if `session.get("user_id")` is already set, redirect to `url_for("dashboard")` instead of re-rendering the form. The `POST /login` branch is unaffected — submitting credentials while logged in still authenticates and refreshes the session, with the same validation/lookup rules as a fresh sign-in.
- Do **not** rate-limit or lock accounts in this step; that is a future concern. One failed attempt and one successful attempt are both allowed in quick succession.
- Use CSS variables from `static/css/style.css` — never hardcode hex values in templates or new CSS.
- All modified templates must continue to extend `base.html`.
- Close the DB connection in a `try/finally` like the rest of the data layer.
- Use `request.form.get(...)` with `.strip()` for `email` and lowercase it before lookup; pull `password` raw (no trim — leading/trailing spaces in a password are meaningful and a user might intentionally have one).

## Definition of done
- [ ] `GET /login` renders the form with no error when the user is logged out.
- [ ] `GET /login` while logged in redirects to `/dashboard` (soft gate). `/logout` is **not** gated — the navbar and dashboard's `Log out` actions both link to it, and it must stay reachable so a logged-in user can sign out.
- [ ] `POST /login` with a valid email + correct password sets `session["user_id"]` and redirects to `/dashboard`, which renders the user's name.
- [ ] `POST /login` with a valid email + wrong password re-renders the form with "Invalid email or password." and does not set the session.
- [ ] `POST /login` with an email that is not in `users` re-renders the form with the **same** "Invalid email or password." message (no enumeration leak) and does not set the session.
- [ ] `POST /login` with an empty email or empty password re-renders the form with a clear validation error and does not set the session.
- [ ] Email matching is case-insensitive in practice (e.g. `Demo@Spendly.com` and `demo@spendly.com` both log in the demo user).
- [ ] `GET /logout` clears `session["user_id"]` and redirects to `/`. Hitting `/logout` again when already logged out does not error.
- [ ] After login, the navbar shows `Dashboard` and `Log out`; after logout (or when logged out), it shows `Sign in` and `Get started`.
- [ ] The dashboard page exposes a working `Log out` action that clears the session.
- [ ] All SQL uses `?` placeholders; no string formatting in queries.
- [ ] `password_hash` is never selected into the rendered template — only used for `check_password_hash` server-side.
- [ ] No hex colors are added to templates or new CSS — only existing CSS variables are used.
- [ ] All modified templates continue to extend `base.html`.
- [ ] App starts without errors and `GET /login` returns 200.
