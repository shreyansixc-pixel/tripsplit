# 💸 TripSplit - Hostel & Trip Expense Tracker

TripSplit is a lightweight, high-performance expense tracking and debt-simplification web application designed for roommates, hostels, and group trips. It automates fair expense splitting and minimizes the number of transactions required to settle balances.

## 🚀 Features
- **Categorized Expense Logging:** Track expenses across categories like Food, Transport, Utilities, and Rent.
- **Automated Net Balances:** Instantly calculates individual spending shares and net financial standings.
- **Smart Debt Minimization Engine:** Uses a greedy algorithm to compute the exact transactions needed between members (e.g., "Person A pays Person B: ₹X").
- **Itemized Management:** Delete specific entries by ID or clear history securely.
- **Persistent Storage:** Backed by SQLite for lightweight, reliable data persistence without heavy binary dependencies.

## 🛠️ Tech Stack
- **Frontend/UI:** Streamlit (Python)
- **Database:** SQLite3
- **Language:** Python 3.13

## 🏃‍♂️ How to Run Locally
1. Ensure you have Python 3.13 installed.
2. Install dependencies:
   ```bash
   pip install streamlit

