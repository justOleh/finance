"""
backend.seed_data
-----------------
Populates the database with dummy expense data spread across the last six
months so the dashboard has meaningful charts on first launch.

Usage
~~~~~
Run once from the backend directory (after the DB has been created):

    python seed_data.py

The script is idempotent: it checks whether any expenses already exist and
skips seeding if the table is not empty.
"""

import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine
from models import Base, Expense

# ---------------------------------------------------------------------------
# Dummy data – six months of realistic grocery / utility / dining expenses
# ---------------------------------------------------------------------------

_SEED_EXPENSES = [
    # --- August 2024 ---
    {
        "date": date(2024, 8, 3),
        "store": "Whole Foods",
        "items": [
            {"name": "Organic Milk", "price": 4.99},
            {"name": "Sourdough Bread", "price": 6.49},
            {"name": "Free-range Eggs", "price": 5.99},
        ],
        "total": 17.47,
        "notes": "Weekly grocery run",
    },
    {
        "date": date(2024, 8, 10),
        "store": "Amazon",
        "items": [
            {"name": "USB-C Cable", "price": 12.99},
            {"name": "Phone Case", "price": 9.99},
        ],
        "total": 22.98,
        "notes": None,
    },
    {
        "date": date(2024, 8, 17),
        "store": "Trader Joe's",
        "items": [
            {"name": "Frozen Pizza", "price": 5.49},
            {"name": "Orange Juice", "price": 3.99},
            {"name": "Greek Yogurt", "price": 2.99},
            {"name": "Pasta", "price": 1.99},
        ],
        "total": 14.46,
        "notes": None,
    },
    {
        "date": date(2024, 8, 22),
        "store": "Electric Company",
        "items": [{"name": "Monthly Bill", "price": 87.50}],
        "total": 87.50,
        "notes": "August electricity bill",
    },
    {
        "date": date(2024, 8, 28),
        "store": "Olive Garden",
        "items": [
            {"name": "Pasta Dinner", "price": 18.99},
            {"name": "Salad", "price": 7.99},
            {"name": "Wine", "price": 12.00},
        ],
        "total": 38.98,
        "notes": "Date night",
    },
    # --- September 2024 ---
    {
        "date": date(2024, 9, 5),
        "store": "Costco",
        "items": [
            {"name": "Chicken Breast (5 lb)", "price": 14.99},
            {"name": "Mixed Nuts", "price": 18.99},
            {"name": "Laundry Detergent", "price": 22.49},
            {"name": "Paper Towels", "price": 19.99},
        ],
        "total": 76.46,
        "notes": "Bulk shopping",
    },
    {
        "date": date(2024, 9, 12),
        "store": "Starbucks",
        "items": [
            {"name": "Latte", "price": 5.75},
            {"name": "Croissant", "price": 3.45},
        ],
        "total": 9.20,
        "notes": None,
    },
    {
        "date": date(2024, 9, 18),
        "store": "Whole Foods",
        "items": [
            {"name": "Salmon Fillet", "price": 12.99},
            {"name": "Baby Spinach", "price": 3.99},
            {"name": "Cherry Tomatoes", "price": 4.49},
        ],
        "total": 21.47,
        "notes": None,
    },
    {
        "date": date(2024, 9, 22),
        "store": "Electric Company",
        "items": [{"name": "Monthly Bill", "price": 79.00}],
        "total": 79.00,
        "notes": "September electricity bill",
    },
    {
        "date": date(2024, 9, 27),
        "store": "Netflix",
        "items": [{"name": "Monthly Subscription", "price": 15.49}],
        "total": 15.49,
        "notes": None,
    },
    # --- October 2024 ---
    {
        "date": date(2024, 10, 2),
        "store": "Target",
        "items": [
            {"name": "T-Shirt", "price": 14.99},
            {"name": "Shampoo", "price": 6.99},
            {"name": "Toothpaste", "price": 3.49},
        ],
        "total": 25.47,
        "notes": None,
    },
    {
        "date": date(2024, 10, 9),
        "store": "Trader Joe's",
        "items": [
            {"name": "Pumpkin Soup", "price": 3.99},
            {"name": "Sparkling Water (12pk)", "price": 5.99},
            {"name": "Dark Chocolate", "price": 2.49},
        ],
        "total": 12.47,
        "notes": "Fall favorites",
    },
    {
        "date": date(2024, 10, 15),
        "store": "Gas Station",
        "items": [{"name": "Fuel (12 gal)", "price": 50.40}],
        "total": 50.40,
        "notes": None,
    },
    {
        "date": date(2024, 10, 20),
        "store": "Amazon",
        "items": [
            {"name": "Notebook (3-pack)", "price": 11.99},
            {"name": "Pens", "price": 5.49},
        ],
        "total": 17.48,
        "notes": "Office supplies",
    },
    {
        "date": date(2024, 10, 25),
        "store": "Electric Company",
        "items": [{"name": "Monthly Bill", "price": 92.00}],
        "total": 92.00,
        "notes": "October electricity bill",
    },
    {
        "date": date(2024, 10, 30),
        "store": "Party City",
        "items": [
            {"name": "Halloween Decorations", "price": 24.99},
            {"name": "Candy (assorted)", "price": 18.99},
        ],
        "total": 43.98,
        "notes": "Halloween supplies",
    },
    # --- November 2024 ---
    {
        "date": date(2024, 11, 3),
        "store": "Whole Foods",
        "items": [
            {"name": "Turkey (12 lb)", "price": 34.99},
            {"name": "Cranberry Sauce", "price": 3.49},
            {"name": "Stuffing Mix", "price": 2.99},
            {"name": "Sweet Potatoes", "price": 5.49},
        ],
        "total": 46.96,
        "notes": "Thanksgiving prep",
    },
    {
        "date": date(2024, 11, 11),
        "store": "Costco",
        "items": [
            {"name": "Kirkland Coffee", "price": 19.99},
            {"name": "Olive Oil", "price": 14.99},
            {"name": "Frozen Berries", "price": 12.99},
        ],
        "total": 47.97,
        "notes": None,
    },
    {
        "date": date(2024, 11, 19),
        "store": "Spotify",
        "items": [{"name": "Monthly Subscription", "price": 10.99}],
        "total": 10.99,
        "notes": None,
    },
    {
        "date": date(2024, 11, 22),
        "store": "Electric Company",
        "items": [{"name": "Monthly Bill", "price": 105.00}],
        "total": 105.00,
        "notes": "November electricity bill",
    },
    {
        "date": date(2024, 11, 29),
        "store": "Best Buy",
        "items": [
            {"name": "Wireless Headphones", "price": 79.99},
            {"name": "HDMI Cable", "price": 14.99},
        ],
        "total": 94.98,
        "notes": "Black Friday deals",
    },
    # --- December 2024 ---
    {
        "date": date(2024, 12, 5),
        "store": "Amazon",
        "items": [
            {"name": "Christmas Lights", "price": 24.99},
            {"name": "Wrapping Paper", "price": 9.99},
            {"name": "Tape (3-pack)", "price": 4.99},
        ],
        "total": 39.97,
        "notes": "Holiday decorations",
    },
    {
        "date": date(2024, 12, 10),
        "store": "Whole Foods",
        "items": [
            {"name": "Prime Rib (4 lb)", "price": 44.99},
            {"name": "Brie Cheese", "price": 8.99},
            {"name": "Champagne", "price": 19.99},
        ],
        "total": 73.97,
        "notes": "Holiday party",
    },
    {
        "date": date(2024, 12, 18),
        "store": "Target",
        "items": [
            {"name": "Gift Card - Coffee", "price": 25.00},
            {"name": "Gift Card - Amazon", "price": 50.00},
            {"name": "Gift Bag Set", "price": 7.99},
        ],
        "total": 82.99,
        "notes": "Christmas gifts",
    },
    {
        "date": date(2024, 12, 22),
        "store": "Electric Company",
        "items": [{"name": "Monthly Bill", "price": 118.00}],
        "total": 118.00,
        "notes": "December electricity bill",
    },
    {
        "date": date(2024, 12, 28),
        "store": "Trader Joe's",
        "items": [
            {"name": "Champagne (2 bottles)", "price": 23.98},
            {"name": "Party Snacks", "price": 15.47},
        ],
        "total": 39.45,
        "notes": "New Year's Eve prep",
    },
    # --- January 2025 ---
    {
        "date": date(2025, 1, 4),
        "store": "Gym",
        "items": [{"name": "Annual Membership", "price": 360.00}],
        "total": 360.00,
        "notes": "New Year resolution",
    },
    {
        "date": date(2025, 1, 9),
        "store": "Whole Foods",
        "items": [
            {"name": "Protein Powder", "price": 29.99},
            {"name": "Quinoa", "price": 5.99},
            {"name": "Avocados (6-pack)", "price": 6.49},
        ],
        "total": 42.47,
        "notes": "Healthy eating",
    },
    {
        "date": date(2025, 1, 15),
        "store": "Electric Company",
        "items": [{"name": "Monthly Bill", "price": 124.00}],
        "total": 124.00,
        "notes": "January electricity bill",
    },
    {
        "date": date(2025, 1, 20),
        "store": "Netflix",
        "items": [{"name": "Monthly Subscription", "price": 15.49}],
        "total": 15.49,
        "notes": None,
    },
    {
        "date": date(2025, 1, 25),
        "store": "Gas Station",
        "items": [{"name": "Fuel (10 gal)", "price": 42.00}],
        "total": 42.00,
        "notes": None,
    },
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Expense).count() > 0:
            print("Database already has data – skipping seed.")
            return
        for data in _SEED_EXPENSES:
            items = data.pop("items")
            expense = Expense(**data)
            expense.items = items
            db.add(expense)
        db.commit()
        print(f"Seeded {len(_SEED_EXPENSES)} expenses into the database.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
