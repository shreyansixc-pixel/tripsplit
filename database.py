"""
database.py - SQLite Database Layer for TripSplit
=================================================
This module manages all database interactions using Python's built-in `sqlite3`
module. It provides functions to create tables, manage trips, add members,
record expenses, and handle split allocations.

Beginner Python & SQL Concepts:
------------------------------
1. SQLite: A serverless, zero-configuration SQL database stored as a single file.
2. Foreign Keys: Maintain relationships (e.g., each expense belongs to a trip).
   We explicitly run `PRAGMA foreign_keys = ON` because SQLite disables them by default!
3. Transactions: The `with conn:` context manager automatically commits if
   successful or rolls back if an error occurs.
4. Row Factory: Setting `conn.row_factory = sqlite3.Row` allows columns to be accessed
   both by index (row[0]) and by column name (row['name']), just like a dictionary!
"""

import sqlite3
from datetime import datetime, date
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = "tripsplit.db"


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    Enables foreign keys and uses sqlite3.Row for friendly column access.
    """
    conn = sqlite3.connect(db_path)
    # Enable foreign key constraint enforcement
    conn.execute("PRAGMA foreign_keys = ON;")
    # Return rows that can be indexed by column name
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Initializes the database schema if tables do not already exist.
    Creates 4 normalized tables:
    1. trips: General information about each trip or hostel stay.
    2. members: Friends or travelers participating in a specific trip.
    3. expenses: Header details for each expense (payer, amount, category).
    4. expense_splits: How much each participant owes for a given expense.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Trips table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. Members table (Linked to trips via trip_id)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
            );
        """)

        # 3. Expenses table (Linked to trips and the member who paid)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER NOT NULL,
                payer_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                expense_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE,
                FOREIGN KEY (payer_id) REFERENCES members (id) ON DELETE CASCADE
            );
        """)

        # 4. Expense splits table (Breakdown of who owes what for each expense)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expense_splits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY (expense_id) REFERENCES expenses (id) ON DELETE CASCADE,
                FOREIGN KEY (member_id) REFERENCES members (id) ON DELETE CASCADE
            );
        """)


# =====================================================================
# Trip Operations
# =====================================================================

def create_trip(name: str, description: str = "", db_path: str = DEFAULT_DB_PATH) -> int:
    """Creates a new trip and returns its newly generated integer ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO trips (name, description) VALUES (?, ?);",
            (name.strip(), description.strip())
        )
        return cursor.lastrowid


def get_trips(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Returns all trips with summary stats (member count and total spending)."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        # Query trips with subqueries for member counts and total expenses
        query = """
            SELECT 
                t.id, 
                t.name, 
                t.description, 
                t.created_at,
                (SELECT COUNT(*) FROM members m WHERE m.trip_id = t.id) AS member_count,
                COALESCE((SELECT SUM(amount) FROM expenses e WHERE e.trip_id = t.id), 0.0) AS total_spent
            FROM trips t
            ORDER BY t.created_at DESC;
        """
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def get_trip(trip_id: int, db_path: str = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    """Retrieves a single trip by ID."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trips WHERE id = ?;", (trip_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_trip(trip_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """Deletes a trip. SQLite cascade will automatically remove members and expenses."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM trips WHERE id = ?;", (trip_id,))


# =====================================================================
# Member Operations
# =====================================================================

def add_member(trip_id: int, name: str, db_path: str = DEFAULT_DB_PATH) -> int:
    """Adds a new member/friend to a trip."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO members (trip_id, name) VALUES (?, ?);",
            (trip_id, name.strip())
        )
        return cursor.lastrowid


def get_members(trip_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves all members for a given trip."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM members WHERE trip_id = ? ORDER BY id ASC;",
            (trip_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_member(member_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """Deletes a member from a trip."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM members WHERE id = ?;", (member_id,))


# =====================================================================
# Expense & Split Operations
# =====================================================================

def add_expense(
    trip_id: int,
    payer_id: int,
    amount: float,
    category: str,
    description: str,
    expense_date: str,
    split_member_ids: List[int],
    db_path: str = DEFAULT_DB_PATH
) -> int:
    """
    Logs an expense and automatically calculates equal splits among selected members.
    
    Real-world Penny-Rounding Detail:
    ---------------------------------
    When splitting $10.00 across 3 people:
    10 / 3 = 3.333333...
    If each gets 3.33, total is 9.99 (missing 1 cent!).
    We distribute any leftover cent to the first member so the split sum
    EXACTLY equals the total expense amount.
    """
    if not split_member_ids:
        raise ValueError("At least one member must be selected to split this expense.")

    amount = round(float(amount), 2)
    num_members = len(split_member_ids)

    # Base split amount rounded down to 2 decimals
    base_split = round(amount / num_members, 2)
    # Check discrepancy
    diff = round(amount - (base_split * num_members), 2)

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. Insert header expense record
        cursor.execute("""
            INSERT INTO expenses (trip_id, payer_id, amount, category, description, expense_date)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (trip_id, payer_id, amount, category, description.strip(), expense_date))
        expense_id = cursor.lastrowid

        # 2. Insert split for each participant
        for idx, m_id in enumerate(split_member_ids):
            # Give the remainder fraction/cent to the first member
            member_share = base_split + (diff if idx == 0 else 0.0)
            member_share = round(member_share, 2)

            cursor.execute("""
                INSERT INTO expense_splits (expense_id, member_id, amount)
                VALUES (?, ?, ?);
            """, (expense_id, m_id, member_share))

        return expense_id


def get_expenses(trip_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Retrieves all expenses for a trip with the payer's name and split member count.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                e.id,
                e.trip_id,
                e.payer_id,
                m.name AS payer_name,
                e.amount,
                e.category,
                e.description,
                e.expense_date,
                e.created_at,
                (SELECT COUNT(*) FROM expense_splits es WHERE es.expense_id = e.id) AS split_count
            FROM expenses e
            JOIN members m ON e.payer_id = m.id
            WHERE e.trip_id = ?
            ORDER BY e.expense_date DESC, e.id DESC;
        """
        cursor.execute(query, (trip_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_expense_splits_for_trip(trip_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Retrieves all split rows for all expenses within a trip.
    Used by utils.py to calculate net balances.
    """
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                es.id,
                es.expense_id,
                es.member_id,
                m.name AS member_name,
                es.amount
            FROM expense_splits es
            JOIN expenses e ON es.expense_id = e.id
            JOIN members m ON es.member_id = m.id
            WHERE e.trip_id = ?;
        """
        cursor.execute(query, (trip_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_splits_for_expense(expense_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves the split details for a single expense."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                es.member_id,
                m.name AS member_name,
                es.amount
            FROM expense_splits es
            JOIN members m ON es.member_id = m.id
            WHERE es.expense_id = ?;
        """
        cursor.execute(query, (expense_id,))
        return [dict(row) for row in cursor.fetchall()]


def delete_expense(expense_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """Deletes an expense and its associated splits."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM expenses WHERE id = ?;", (expense_id,))


# =====================================================================
# Demo / Seed Data Generator
# =====================================================================

def seed_sample_data(db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Seeds a realistic example trip with 4 hostel friends and several expenses.
    Useful for beginners to immediately explore the UI without manual typing.
    Returns the new trip_id.
    """
    init_db(db_path)
    
    trip_id = create_trip(
        name="🌴 Goa Beach & Hostel Getaway",
        description="Shared hostel dorms, scooter rentals, beach shacks, and seafood dinners.",
        db_path=db_path
    )

    # Add 4 friends
    m_alice = add_member(trip_id, "Alice (Organizer)", db_path=db_path)
    m_bob = add_member(trip_id, "Bob", db_path=db_path)
    m_charlie = add_member(trip_id, "Charlie", db_path=db_path)
    m_diana = add_member(trip_id, "Diana", db_path=db_path)

    all_members = [m_alice, m_bob, m_charlie, m_diana]

    today_str = date.today().isoformat()

    # Expense 1: Alice paid for Hostel Booking for all 4
    add_expense(
        trip_id=trip_id,
        payer_id=m_alice,
        amount=240.00,
        category="🏨 Accommodation",
        description="4-bed Dorm Room Booking (3 Nights)",
        expense_date=today_str,
        split_member_ids=all_members,
        db_path=db_path
    )

    # Expense 2: Bob paid for Scooter Rentals for Alice, Bob, and Charlie
    add_expense(
        trip_id=trip_id,
        payer_id=m_bob,
        amount=60.00,
        category="🚗 Transport",
        description="Scooter & Helmet Rentals",
        expense_date=today_str,
        split_member_ids=[m_alice, m_bob, m_charlie],
        db_path=db_path
    )

    # Expense 3: Charlie paid for Sunset Beach Shack Dinner
    add_expense(
        trip_id=trip_id,
        payer_id=m_charlie,
        amount=90.00,
        category="🍔 Food & Drinks",
        description="Seafood Platters & Tropical Drinks",
        expense_date=today_str,
        split_member_ids=all_members,
        db_path=db_path
    )

    # Expense 4: Diana paid for Groceries and Snacks
    add_expense(
        trip_id=trip_id,
        payer_id=m_diana,
        amount=36.00,
        category="🛒 Groceries",
        description="Breakfast Cereal, Fruit, Bottled Water",
        expense_date=today_str,
        split_member_ids=all_members,
        db_path=db_path
    )

    return trip_id

