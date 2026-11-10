import sqlite3
import streamlit as st

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("tripsplit.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS expenses 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  category TEXT,
                  title TEXT, 
                  payer TEXT, 
                  amount REAL, 
                  participants TEXT)''')
    
    try:
        c.execute("SELECT category FROM expenses LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("DROP TABLE expenses")
        c.execute('''CREATE TABLE expenses 
                     (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                      category TEXT,
                      title TEXT, 
                      payer TEXT, 
                      amount REAL, 
                      participants TEXT)''')
    conn.commit()
    conn.close()

init_db()

st.title("💸 TripSplit: Hostel & Trip Expense Tracker")
st.subheader("Master your shared living expenses effortlessly")

# --- SIDEBAR: ADD & MANAGE EXPENSES ---
st.sidebar.header("Manage Expenses")

with st.sidebar.expander("➕ Add New Expense", expanded=True):
    with st.form("expense_form", clear_on_submit=True):
        category = st.selectbox("Category", ["Food", "Transport", "Utilities", "Rent", "Entertainment", "Other"])
        title = st.text_input("Description (e.g., Domino's Pizza, Uber)")
        payer = st.text_input("Paid By (e.g., Shreya)")
        amount = st.number_input("Amount (₹)", min_value=0.0, format="%.2f")
        participants_input = st.text_input("Split Between (comma-separated names)")
        submitted = st.form_submit_button("Add Expense")

        if submitted and title and payer and amount > 0 and participants_input:
            conn = sqlite3.connect("tripsplit.db")
            c = conn.cursor()
            c.execute("INSERT INTO expenses (category, title, payer, amount, participants) VALUES (?, ?, ?, ?, ?)",
                      (category, title, payer.strip().capitalize(), amount, participants_input))
            conn.commit()
            conn.close()
            st.sidebar.success(f"Added {category}: {title} (₹{amount})")
            st.rerun()

# Fetch current rows
conn = sqlite3.connect("tripsplit.db")
c = conn.cursor()
c.execute("SELECT id, category, title, payer, amount, participants FROM expenses")
rows = c.fetchall()
conn.close()

if rows:
    with st.sidebar.expander("🗑️ Delete Specific Expense"):
        with st.form("delete_form"):
            expense_ids = [row[0] for row in rows]
            selected_id = st.selectbox("Select Expense ID to Delete", expense_ids)
            delete_submitted = st.form_submit_button("Delete Expense")
            
            if delete_submitted:
                conn = sqlite3.connect("tripsplit.db")
                c = conn.cursor()
                c.execute("DELETE FROM expenses WHERE id = ?", (selected_id,))
                conn.commit()
                conn.close()
                st.sidebar.warning(f"Deleted expense ID: {selected_id}")
                st.rerun()

    with st.sidebar.expander("⚠️ Danger Zone"):
        if st.button("Clear All History"):
            conn = sqlite3.connect("tripsplit.db")
            c = conn.cursor()
            c.execute("DELETE FROM expenses")
            conn.commit()
            conn.close()
            st.sidebar.error("All expenses cleared!")
            st.rerun()

# --- MAIN DASHBOARD ---
if rows:
    st.subheader("📜 Itemized Expense History")
    total_spent = 0.0
    
    st.markdown("| ID | Category | Description | Paid By | Amount (₹) | Split Between |")
    st.markdown("|---|---|---|---|---|---|")
    for row in rows:
        exp_id, cat, desc, payer, amt, parts = row
        st.markdown(f"| {exp_id} | **{cat}** | {desc} | {payer} | ₹{amt:.2f} | {parts} |")
        total_spent += amt

    st.metric(label="Total Expenses Logged", value=f"₹{total_spent:.2f}")

    # --- BALANCE & SETTLEMENT CALCULATOR ---
    st.subheader("⚖️ Balance & Settlement Summary")
    
    paid_mapping = {}
    owed_mapping = {}
    all_people = set()

    for row in rows:
        _, _, _, payer, amount, participants_str = row
        payer = payer.strip().capitalize()
        
        participants = [p.strip().capitalize() for p in participants_str.split(",") if p.strip()]
        if not participants:
            continue
            
        share = amount / len(participants)
        
        paid_mapping[payer] = paid_mapping.get(payer, 0.0) + amount
        all_people.add(payer)
        
        for p in participants:
            all_people.add(p)
            owed_mapping[p] = owed_mapping.get(p, 0.0) + share

    net_mapping = {}
    st.markdown("| Person | Total Paid (₹) | Total Share (₹) | Net Balance (₹) |")
    st.markdown("|---|---|---|---|")
    for person in sorted(list(all_people)):
        total_paid = paid_mapping.get(person, 0.0)
        total_share = owed_mapping.get(person, 0.0)
        net = total_paid - total_share
        net_mapping[person] = net
        
        if net > 0:
            status_text = f"🟢 Gets back ₹{net:.2f}"
        elif net < 0:
            status_text = f"🔴 Owes ₹{abs(net):.2f}"
        else:
            status_text = "✅ Settled up"
            
        st.markdown(f"| **{person}** | ₹{total_paid:.2f} | ₹{total_share:.2f} | {status_text} |")

    # --- WHO OWES WHO (Smart Debt Simplification) ---
    st.subheader("🤝 Who Owes Who")
    
    debtors = []
    creditors = []
    for person, net in net_mapping.items():
        if net < -0.01:
            debtors.append([person, -net])
        elif net > 0.01:
            creditors.append([person, net])
            
    debtors.sort(key=lambda x: x[1], reverse=True)
    creditors.sort(key=lambda x: x[1], reverse=True)
    
    settlements = []
    d_idx = 0
    c_idx = 0
    
    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor, debt_amt = debtors[d_idx]
        creditor, credit_amt = creditors[c_idx]
        
        settle_amt = min(debt_amt, credit_amt)
        settlements.append(f"👉 **{debtor}** pays **{creditor}**: **₹{settle_amt:.2f}**")
        
        debtors[d_idx][1] -= settle_amt
        creditors[c_idx][1] -= settle_amt
        
        if debtors[d_idx][1] < 0.01:
            d_idx += 1
        if creditors[c_idx][1] < 0.01:
            c_idx += 1
            
    if settlements:
        for s in settlements:
            st.markdown(s)
    else:
        st.success("All balances are completely settled up! 🎉")

else:
    st.info("No expenses logged yet. Use the sidebar to add your first expense!")