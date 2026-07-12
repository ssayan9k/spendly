"""Seed N random realistic expenses for a user across the past M months.

Usage: python seed_user_expenses.py <user_id> <count> <months>
"""

import os
import random
import sys
from datetime import date, timedelta

from werkzeug.security import generate_password_hash  # noqa: F401  (kept for parity with db.py)

# Make the project root importable so we can use the same get_db() helper.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import get_db  # noqa: E402


# (category, amount_low, amount_high, sample_descriptions)
CATEGORIES: list[tuple[str, int, int, list[str]]] = [
    (
        "Food",
        50, 800,
        [
            "Chai and samosa", "Veg thali at local dhaba", "Masala dosa",
            "Butter chicken with naan", "Biryani at Paradise", "Pav bhaji",
            "Idli sambhar at Anand", "Cold coffee at Cafe Coffee Day",
            "South Indian breakfast", "Pani puri from street stall",
            "Dominos pizza order", "Zomato lunch order",
        ],
    ),
    (
        "Transport",
        20, 500,
        [
            "Uber auto to office", "Ola cab ride", "Metro card recharge",
            "Petrol refill", "Rapido bike ride", "Auto rickshaw to station",
            "Monthly bus pass", "Train ticket to Bengaluru", "Diesel for car",
        ],
    ),
    (
        "Bills",
        200, 3000,
        [
            "Airtel broadband bill", "Jio postpaid mobile bill", "Electricity bill",
            "Tata Play DTH recharge", "Gas cylinder refill", "Water bill",
            "Credit card statement", "Apartment maintenance",
        ],
    ),
    (
        "Health",
        100, 2000,
        [
            "Pharmacy medicines", "Apollo clinic consultation", "Blood test at Thyrocare",
            "Dental cleaning", "Eye checkup at Sankara", "Monthly vitamin restock",
        ],
    ),
    (
        "Entertainment",
        100, 1500,
        [
            "PVR movie tickets", "BookMyShow concert", "Netflix monthly plan",
            "Spotify Premium", "Disney+ Hotstar", "IPL match tickets",
            "Weekend pub outing",
        ],
    ),
    (
        "Shopping",
        200, 5000,
        [
            "Amazon order - headphones", "Flipkart Big Billion order",
            "Myntra clothes haul", "Decathlon sports shoes", "DMart grocery run",
            "BigBasket monthly groceries", "Croma - phone charger",
            "Reliance Digital - smart bulb",
        ],
    ),
    (
        "Other",
        50, 1000,
        [
            "Barber shop haircut", "Laundry pickup", "Parking fee", "Temple donation",
            "House help salary top-up", "Birthday gift for friend",
            "Courier parcel to hometown", "Notebooks and pens",
        ],
    ),
]

# Distribution roughly proportional: Food most common, then Transport, Bills,
# Shopping, Other; Health and Entertainment least. We weight by repeating entries
# in the pool, then sample once per expense.
WEIGHTED_POOL: list[tuple[str, int, int, list[str]]] = []
WEIGHT_BY_CATEGORY = {
    "Food": 5,
    "Transport": 4,
    "Bills": 3,
    "Shopping": 3,
    "Other": 2,
    "Health": 1,
    "Entertainment": 1,
}
for cat in CATEGORIES:
    WEIGHTED_POOL.extend([cat] * WEIGHT_BY_CATEGORY[cat[0]])


def random_past_date(months: int) -> date:
    """Pick a random date within the past `months` months (inclusive of today)."""
    today = date.today()
    # Use the 1st of (today.month - months + 1) as the earliest possible month
    # boundary, then offset anywhere up to today.
    earliest_year = today.year
    earliest_month = today.month - (months - 1)
    while earliest_month <= 0:
        earliest_month += 12
        earliest_year -= 1
    earliest = date(earliest_year, earliest_month, 1)
    span_days = (today - earliest).days
    if span_days < 0:
        span_days = 0
    return earliest + timedelta(days=random.randint(0, span_days))


def main() -> None:
    if len(sys.argv) != 4:
        print("Usage: /seed-expenses <user_id> <count> <months>")
        print("Example: /seed-expenses 1 50 6")
        sys.exit(1)

    try:
        user_id = int(sys.argv[1])
        count = int(sys.argv[2])
        months = int(sys.argv[3])
    except ValueError:
        print("Usage: /seed-expenses <user_id> <count> <months>")
        print("Example: /seed-expenses 1 50 6")
        sys.exit(1)

    if count <= 0 or months <= 0:
        print("count and months must be positive integers.")
        sys.exit(1)

    conn = get_db()
    try:
        user = conn.execute(
            "SELECT id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user is None:
            print(f"No user found with id {user_id}.")
            sys.exit(1)

        # Build all rows first so we can insert in a single transaction.
        rows: list[tuple] = []
        for _ in range(count):
            cat, low, high, descs = random.choice(WEIGHTED_POOL)
            amount = round(random.uniform(low, high), 2)
            description = random.choice(descs)
            d = random_past_date(months)
            rows.append((user_id, amount, cat, d.isoformat(), description))

        # Single transaction: cursor.executemany + commit; rollback on any failure.
        try:
            conn.execute("BEGIN")
            conn.executemany(
                """
                INSERT INTO expenses (user_id, amount, category, date, description)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Insert failed, rolled back: {e}")
            sys.exit(1)

        # Report
        dates = sorted(row[3] for row in rows)
        print(f"Inserted {len(rows)} expenses for user_id={user_id} "
              f"spanning {months} month(s).")
        print(f"Date range: {dates[0]} to {dates[-1]}")
        print("Sample of 5 inserted records:")
        sample = random.sample(rows, k=min(5, len(rows)))
        for r in sample:
            print(f"  user_id={r[0]} amount={r[1]} category={r[2]} "
                  f"date={r[3]} description={r[4]!r}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
