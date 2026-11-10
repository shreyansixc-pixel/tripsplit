"""
test_tripsplit.py - Unit Tests for Database and Min-Cash-Flow Algorithm
======================================================================
This test suite verifies:
1. Net balance calculations from expense splits.
2. The Min-Cash-Flow greedy settlement algorithm.
3. Database creation, member addition, and expense logging with penny rounding.

Run these tests via:
    python -m unittest test_tripsplit.py
"""

import os
import unittest
import database as db
import utils

TEST_DB = "test_tripsplit.db"


class TestTripSplitUtils(unittest.TestCase):
    def test_calculate_net_balances(self):
        """Test that net balance = total_paid - total_owed for each member."""
        members = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
            {"id": 3, "name": "Charlie"}
        ]
        
        # Expense: Alice paid $60 split equally among Alice, Bob, Charlie ($20 each)
        expenses = [{"payer_id": 1, "amount": 60.0}]
        splits = [
            {"member_id": 1, "amount": 20.0},
            {"member_id": 2, "amount": 20.0},
            {"member_id": 3, "amount": 20.0}
        ]

        balances = utils.calculate_net_balances(members, expenses, splits)

        # Alice paid $60, owes $20 -> net balance +$40
        self.assertEqual(balances[1]["total_paid"], 60.0)
        self.assertEqual(balances[1]["total_owed"], 20.0)
        self.assertEqual(balances[1]["net_balance"], 40.0)

        # Bob paid $0, owes $20 -> net balance -$20
        self.assertEqual(balances[2]["total_paid"], 0.0)
        self.assertEqual(balances[2]["total_owed"], 20.0)
        self.assertEqual(balances[2]["net_balance"], -20.0)

        # Charlie paid $0, owes $20 -> net balance -$20
        self.assertEqual(balances[3]["net_balance"], -20.0)

        # The sum of all net balances must always equal zero
        net_sum = sum(b["net_balance"] for b in balances.values())
        self.assertAlmostEqual(net_sum, 0.0, places=2)

    def test_simplify_debts_two_parties(self):
        """Test simple 2-person settlement: Bob pays Alice $20."""
        balances = {
            1: {"id": 1, "name": "Alice", "net_balance": 20.0},
            2: {"id": 2, "name": "Bob", "net_balance": -20.0}
        }
        settlements = utils.simplify_debts(balances)

        self.assertEqual(len(settlements), 1)
        self.assertEqual(settlements[0]["from_name"], "Bob")
        self.assertEqual(settlements[0]["to_name"], "Alice")
        self.assertEqual(settlements[0]["amount"], 20.0)

    def test_simplify_debts_three_parties_chain(self):
        """
        Test circular / transitive settlement:
        Alice is owed $30.
        Bob owes $10.
        Charlie owes $20.
        Should result in:
        - Charlie pays Alice $20
        - Bob pays Alice $10
        Total transactions: 2 (<= N-1 = 2)
        """
        balances = {
            1: {"id": 1, "name": "Alice", "net_balance": 30.0},
            2: {"id": 2, "name": "Bob", "net_balance": -10.0},
            3: {"id": 3, "name": "Charlie", "net_balance": -20.0}
        }
        settlements = utils.simplify_debts(balances)

        self.assertEqual(len(settlements), 2)
        total_settled = sum(s["amount"] for s in settlements)
        self.assertEqual(total_settled, 30.0)

    def test_format_currency(self):
        """Test formatting of positive, negative, and zero values."""
        self.assertEqual(utils.format_currency(1234.5, "$"), "$1,234.50")
        self.assertEqual(utils.format_currency(-50.0, "₹"), "-₹50.00")
        self.assertEqual(utils.format_currency(0.0, "€"), "€0.00")


class TestTripSplitDatabase(unittest.TestCase):
    def setUp(self):
        """Set up a fresh temporary SQLite test database before each test."""
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        db.init_db(TEST_DB)

    def tearDown(self):
        """Clean up the test database file after each test."""
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    def test_create_trip_and_add_members(self):
        """Test creating a trip and adding members to it."""
        trip_id = db.create_trip("Himachal Backpacking", "Hostel dorms & trekking", db_path=TEST_DB)
        self.assertIsInstance(trip_id, int)

        m1 = db.add_member(trip_id, "Dev", db_path=TEST_DB)
        m2 = db.add_member(trip_id, "Priya", db_path=TEST_DB)

        members = db.get_members(trip_id, db_path=TEST_DB)
        self.assertEqual(len(members), 2)
        names = [m["name"] for m in members]
        self.assertIn("Dev", names)
        self.assertIn("Priya", names)

    def test_add_expense_with_penny_rounding(self):
        """
        Test logging an expense of $10.00 split among 3 people.
        $10.00 / 3 = 3.3333...
        Penny rounding should ensure the splits sum to exactly 10.00:
        Person 1: 3.34
        Person 2: 3.33
        Person 3: 3.33
        Total: 10.00
        """
        trip_id = db.create_trip("Weekend Trip", db_path=TEST_DB)
        m1 = db.add_member(trip_id, "User1", db_path=TEST_DB)
        m2 = db.add_member(trip_id, "User2", db_path=TEST_DB)
        m3 = db.add_member(trip_id, "User3", db_path=TEST_DB)

        exp_id = db.add_expense(
            trip_id=trip_id,
            payer_id=m1,
            amount=10.00,
            category="🍔 Food & Drinks",
            description="Lunch split 3 ways",
            expense_date="2026-11-10",
            split_member_ids=[m1, m2, m3],
            db_path=TEST_DB
        )

        splits = db.get_splits_for_expense(exp_id, db_path=TEST_DB)
        self.assertEqual(len(splits), 3)

        split_sum = sum(s["amount"] for s in splits)
        self.assertAlmostEqual(split_sum, 10.00, places=2)


if __name__ == "__main__":
    unittest.main()

