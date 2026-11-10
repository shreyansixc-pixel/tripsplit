"""
utils.py - Core Helper Functions and Debt Simplification Algorithm
==================================================================
This module contains the business logic for TripSplit, including:
1. Net balance calculations from expense logs.
2. The Min-Cash-Flow (debt simplification) greedy algorithm.
3. Currency formatting and text display helpers.

Beginner Python Concept:
------------------------
Keeping algorithmic logic in a dedicated 'utils.py' file separates
pure business logic from database queries and user interface code.
This is called "Separation of Concerns" and makes testing and debugging
much easier.
"""

from typing import List, Dict, Any


def format_currency(amount: float, symbol: str = "$") -> str:
    """
    Format a numeric amount into a clean currency string with 2 decimal places.
    
    Example:
        format_currency(12.5, "$") -> "$12.50"
        format_currency(-8.0, "₹") -> "-₹8.00"
    """
    if amount < 0:
        return f"-{symbol}{abs(amount):,.2f}"
    return f"{symbol}{amount:,.2f}"


def calculate_net_balances(
    members: List[Dict[str, Any]], 
    expenses: List[Dict[str, Any]], 
    splits: List[Dict[str, Any]]
) -> Dict[int, Dict[str, Any]]:
    """
    Computes how much each person paid versus how much they owe across all expenses.
    
    How Net Balance is defined:
    --------------------------
    - 'total_paid': Total money this member paid out of pocket.
    - 'total_owed': Total money this member is responsible for (their share of splits).
    - 'net_balance' = total_paid - total_owed
        * If net_balance > 0: The member overpaid and should RECEIVE money (Creditor).
        * If net_balance < 0: The member underpaid and OWES money (Debtor).
        * If net_balance == 0: The member is perfectly even.

    Parameters:
        members: List of member dictionaries with at least 'id' and 'name'.
        expenses: List of expense dictionaries with 'payer_id' and 'amount'.
        splits: List of split dictionaries with 'member_id' and 'amount'.

    Returns:
        Dict mapping member_id to balance information:
        {
            1: {
                "id": 1,
                "name": "Alice",
                "total_paid": 120.0,
                "total_owed": 60.0,
                "net_balance": 60.0
            },
            ...
        }
    """
    # Initialize balance dictionary for each member in the trip
    balances: Dict[int, Dict[str, Any]] = {}
    for m in members:
        balances[m["id"]] = {
            "id": m["id"],
            "name": m["name"],
            "total_paid": 0.0,
            "total_owed": 0.0,
            "net_balance": 0.0,
        }

    # Sum up how much each person paid out of pocket
    for exp in expenses:
        payer_id = exp["payer_id"]
        if payer_id in balances:
            balances[payer_id]["total_paid"] += float(exp["amount"])

    # Sum up each person's individual split shares
    for sp in splits:
        member_id = sp["member_id"]
        if member_id in balances:
            balances[member_id]["total_owed"] += float(sp["amount"])

    # Calculate net balance = paid - owed, rounded to 2 decimal places
    for member_id, info in balances.items():
        info["total_paid"] = round(info["total_paid"], 2)
        info["total_owed"] = round(info["total_owed"], 2)
        info["net_balance"] = round(info["total_paid"] - info["total_owed"], 2)

    return balances


def simplify_debts(balances: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Min-Cash-Flow Algorithm for Debt Simplification
    ===============================================
    Problem:
    --------
    If Alice owes Bob $20, Bob owes Charlie $20, and Charlie owes Alice $10:
    Without simplification, people make 3 transactions.
    With simplification, Alice pays Charlie $10, and Bob pays Charlie $10 (or Alice pays Charlie $10).
    In groups of 5-10 people, pairwise debts can create dozens of confusing payments.
    
    This greedy algorithm simplifies debts to at most (N - 1) total transactions!

    How It Works Step-by-Step:
    --------------------------
    1. Separate members into two pools:
       - 'debtors': People with negative net balance (they owe money).
       - 'creditors': People with positive net balance (they receive money).
    2. Sort both pools in descending order of amounts.
    3. Pair the person who owes the most (largest debtor) with the person who is owed
       the most (largest creditor).
    4. Settle the smaller of the two amounts:
       settle_amount = min(debtor_amount, creditor_amount)
    5. Record the transaction: "Debtor pays Creditor settle_amount".
    6. Deduct settle_amount from both balances:
       - If debtor still owes money, keep them in the debtor pool.
       - If creditor is still owed money, keep them in the creditor pool.
    7. Repeat until all balances reach 0.00.

    Parameters:
        balances: Output dictionary from calculate_net_balances().

    Returns:
        List of optimized settlement transactions:
        [
            {
                "from_id": 2,
                "from_name": "Bob",
                "to_id": 1,
                "to_name": "Alice",
                "amount": 25.00
            },
            ...
        ]
    """
    # 1. Identify debtors and creditors
    # We store amounts as positive floats for easy calculation
    debtors = []   # list of [amount_owed, member_id, member_name]
    creditors = [] # list of [amount_to_receive, member_id, member_name]

    # Threshold for floating point precision (ignore fractions less than 1 cent)
    EPSILON = 0.01

    for info in balances.values():
        net = info["net_balance"]
        if net < -EPSILON:
            # Net is negative: person owes abs(net)
            debtors.append({
                "amount": round(abs(net), 2),
                "id": info["id"],
                "name": info["name"]
            })
        elif net > EPSILON:
            # Net is positive: person receives net
            creditors.append({
                "amount": round(net, 2),
                "id": info["id"],
                "name": info["name"]
            })

    transactions: List[Dict[str, Any]] = []

    # 2. Greedily match the largest debtor with the largest creditor
    while debtors and creditors:
        # Sort debtors and creditors so the largest values come first
        debtors.sort(key=lambda x: x["amount"], reverse=True)
        creditors.sort(key=lambda x: x["amount"], reverse=True)

        debtor = debtors[0]
        creditor = creditors[0]

        # The transfer amount is the minimum of what debtor owes and what creditor needs
        settle_amount = min(debtor["amount"], creditor["amount"])
        settle_amount = round(settle_amount, 2)

        if settle_amount > 0:
            transactions.append({
                "from_id": debtor["id"],
                "from_name": debtor["name"],
                "to_id": creditor["id"],
                "to_name": creditor["name"],
                "amount": settle_amount,
            })

        # Update remaining amounts
        debtor["amount"] = round(debtor["amount"] - settle_amount, 2)
        creditor["amount"] = round(creditor["amount"] - settle_amount, 2)

        # Remove from list if fully settled (balance is 0)
        if debtor["amount"] <= EPSILON:
            debtors.pop(0)
        if creditor["amount"] <= EPSILON:
            creditors.pop(0)

    return transactions

