# Spec: Registration

## Overview
The Registration step turns the existing static `GET /register` page into a working account-creation flow. Visitors can submit a name, email, and password from the styled form, the password is hashed with `werkzeug`, the user is persisted to the `users` table, and on success they are shown with a success message and then redirected into the app (the post-registration destination for now is a simple "logged in" landing — the proper dashboard/login flow lands in later steps). This is the foundation every later authenticated feature (login, profile, expense CRUD) depends on.

## Depends on
- Step 1 — Database setup (the `users` table with `id`, `name`, `email` UNIQUE, `password_hash`, `created_at`).

## Routes
- `GET /register` — render the registration form — public
- `POST /register` — validate input, hash password, insert user, redirect on success or re-render the form with an error — public

## Database changes
No database changes. A new DB helper must be added to `database/db.py`. The existing `users` table from Step 1 already has all required columns (`name`, `email` UNIQUE, `password_hash`, `created_at` with default).

## Templates
- **Modify:** `templates/register.html` — already renders the three-field form and an `{{ error }}` block; no structural change needed, but verify it stays compatible with the new POST handler and that it still extends `base.html`.
- **Create:** `templates/dashboard.html` — minimal "Welcome, {{ name }}" placeholder page that the post-registration redirect targets until Step 3 (Login) and beyond land a real dashboard.

## Files to change
- `app.py` — convert the `register()` view into a single function that handles both `GET` (render form) and `POST` (create user); add the `dashboard()` view; remove or update the placeholder `/profile` route only if it would shadow the new flow (it currently can stay as a later-step placeholder).
- `templates/register.html` — small adjustments only if the new handler needs extra fields or messages; preserve existing structure.

## Files to create
- `templates/dashboard.html` — minimal welcome page extending `base.html`, displaying the logged-in user's name.
- `.claude/specs/02-registration.md` — this spec.

## New dependencies
No new dependencies. Use:
- `sqlite3` (standard library) — already in use via `database/db.py`
- `werkzeug.security.generate_password_hash` — already in use
- `flask` — already in use

## Rules for implementation
- No SQLAlchemy or any ORM — use the `sqlite3` connection returned by `get_db()`.
- Parameterised queries only — never interpolate user input into SQL strings.
- Passwords must be hashed with `werkzeug.security.generate_password_hash` before storage. Never store plaintext passwords or log them.
- Enforce a minimum password length of 8 characters (matching the existing `Min. 8 characters` placeholder hint).
- Validate `name` is non-empty (after `.strip()`), `email` is non-empty and contains `@`, `password` is at least 8 chars. Show a single friendly error via `{{ error }}` on re-render.
- Handle the `UNIQUE` constraint on `email` by catching the `sqlite3.IntegrityError` and surfacing "An account with that email already exists." instead of a 500.
- After successful insert, store a minimal "logged in" marker in `session` (e.g. `session["user_id"]`) so later steps can read it. The post-registration redirect target is `url_for("dashboard")` for now.
- Use CSS variables from `static/css/style.css` — never hardcode hex values in templates or new CSS.
- All new and modified templates must extend `base.html`.
- Trim whitespace on `name` and `email` before validation and storage; lowercase the email so login (Step 3) can rely on a canonical form.
- Close the DB connection in a `try/finally` like the rest of the data layer.
- Keep the response on a duplicate email as a 200 with the form re-rendered, not a redirect — the user should see the inline error.

## Definition of done
- [ ] `GET /register` renders the form with no error.
- [ ] `POST /register` with valid name + valid email + password ≥ 8 chars inserts a row in `users` and redirects to `/dashboard` (or equivalent logged-in landing).
- [ ] The inserted `password_hash` is a `werkzeug` hash, never plaintext.
- [ ] `POST /register` with a password shorter than 8 chars re-renders the form with "Password must be at least 8 characters." and does not insert.
- [ ] `POST /register` with an empty name or an email missing `@` re-renders the form with a clear validation error and does not insert.
- [ ] `POST /register` with an email already present in `users` re-renders the form with "An account with that email already exists." and does not insert (no 500).
- [ ] The new user's `created_at` is populated (defaulted by the schema).
- [ ] After registration, `session["user_id"]` is set and `/dashboard` renders the user's name.
- [ ] Templates (`register.html`, new `dashboard.html`) extend `base.html` and inherit navbar/footer.
- [ ] No hex colors are added to templates or new CSS — only existing CSS variables are used.
- [ ] All SQL uses `?` placeholders; no string formatting in queries.
- [ ] App starts without errors and the dev server returns 200 for `GET /register`.
