"""Seed a single random Indian user into the Spendly database.

Uses the same get_db() pattern as database/db.py. Generates a unique email
on collision and inserts with the schema's defaults for created_at.
"""

import os
import random
import sys
from datetime import datetime

from werkzeug.security import generate_password_hash

# Make the project root importable so we can use the same get_db() helper.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db import get_db  # noqa: E402

# Common Indian first + last names spanning regions (North, South, East, West).
FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
    "Ayaan", "Krishna", "Ishaan", "Rohit", "Rahul", "Amit", "Vikram",
    "Priya", "Ananya", "Diya", "Aisha", "Neha", "Pooja", "Kavya",
    "Sneha", "Meera", "Riya", "Sita", "Lakshmi", "Anjali", "Divya",
    "Arun", "Karthik", "Ravi", "Suresh", "Manoj", "Deepak", "Nikhil",
    "Tanvi", "Shreya", "Nandini", "Roshni",
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Gupta", "Iyer", "Reddy", "Nair",
    "Kumar", "Singh", "Khan", "Das", "Roy", "Banerjee", "Mukherjee",
    "Chatterjee", "Joshi", "Mehta", "Shah", "Kapoor", "Bhat", "Rao",
    "Pillai", "Menon", "Krishnan", "Bose", "Saxena", "Mishra", "Tiwari",
    "Pandey", "Chauhan", "Yadav", "Jain", "Agarwal", "Srinivasan",
]

# Common email domains used in India.
EMAIL_DOMAINS = [
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "rediffmail.com",
]


def generate_candidate() -> tuple[str, str, str]:
    """Return (first, last, email) for a random Indian user."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    # 2-3 digit numeric suffix; lower chance of collision, still looks natural.
    suffix = random.randint(10, 999)
    domain = random.choice(EMAIL_DOMAINS)
    # Mirror the example format: first.lastNN@domain
    email = f"{first.lower()}.{last.lower()}{suffix}@{domain}"
    return first, last, email


def email_exists(conn, email: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM users WHERE email = ?", (email,)
    ).fetchone()
    return row is not None


def main() -> None:
    conn = get_db()
    try:
        # Keep regenerating until we land on a unique email.
        for _ in range(100):
            first, last, email = generate_candidate()
            if not email_exists(conn, email):
                break
        else:
            raise RuntimeError("Could not generate a unique email after 100 attempts")

        # Use a current datetime string. Schema default uses SQLite's datetime('now'),
        # but we set it explicitly per the task.
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        name = f"{first} {last}"
        password_hash = generate_password_hash("password123")

        cursor = conn.execute(
            """
            INSERT INTO users (name, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (name, email, password_hash, created_at),
        )
        conn.commit()
        user_id = cursor.lastrowid

        print("User created successfully:")
        print(f"  id:    {user_id}")
        print(f"  name:  {name}")
        print(f"  email: {email}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
