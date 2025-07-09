import streamlit as st
import pandas as pd
from datetime import datetime
import os
from git import Repo

# Configuration
REPO_PATH = os.getcwd()
CSV_FILE = os.path.join(REPO_PATH, "payments.csv")
SUMMARY_FILE = os.path.join(REPO_PATH, "docs/index.html")

# Initialize data
if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=["date", "person", "amount", "type", "status"]).to_csv(CSV_FILE, index=False)

def git_push():
    repo = Repo(REPO_PATH)
    repo.git.add(update=True)
    repo.index.commit("Automated update: payment records")
    origin = repo.remote(name='origin')
    origin.push()

def generate_summary():
    df = pd.read_csv(CSV_FILE)
    
    summary = {
        "owed_to_me": df[df['type'] == 'owed_to_me']['amount'].sum(),
        "owed_by_me": df[df['type'] == 'owed_by_me']['amount'].sum(),
        "pending_to_me": df[(df['type'] == 'owed_to_me') & (df['status'] == 'pending')]['amount'].sum(),
        "pending_by_me": df[(df['type'] == 'owed_by_me') & (df['status'] == 'pending')]['amount'].sum(),
        "transactions": df.to_dict('records')
    }
    
    html = f"""
    <html>
    <head>
        <title>Payment Summary</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #333; }}
            .summary-box {{ 
                background: #f5f5f5; 
                padding: 15px; 
                border-radius: 5px; 
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
            }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
            tr:hover {{ background-color: #f5f5f5; }}
        </style>
    </head>
    <body>
        <h1>Payment Summary</h1>
        
        <div class="summary-box">
            <div>
                <h3>People owe me: ${summary['owed_to_me']}</h3>
                <p>Pending: ${summary['pending_to_me']}</p>
            </div>
            <div>
                <h3>I owe others: ${summary['owed_by_me']}</h3>
                <p>Pending: ${summary['pending_by_me']}</p>
            </div>
        </div>
        
        <h2>All Transactions</h2>
        <table>
            <tr>
                <th>Date</th>
                <th>Person</th>
                <th>Amount</th>
                <th>Type</th>
                <th>Status</th>
            </tr>
            {"".join(f"<tr><td>{t['date']}</td><td>{t['person']}</td><td>${t['amount']}</td><td>{'Owed to me' if t['type'] == 'owed_to_me' else 'I owe'}</td><td>{t['status'].capitalize()}</td></tr>" for t in summary['transactions'])}
        </table>
    </body>
    </html>
    """
    
    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    with open(SUMMARY_FILE, 'w') as f:
        f.write(html)
    git_push()

# Streamlit UI
st.title("Payment Tracker")

with st.form("payment_form"):
    col1, col2 = st.columns(2)
    with col1:
        person = st.text_input("Person/Company")
        amount = st.number_input("Amount", min_value=0.0, step=0.01)
    with col2:
        date = st.date_input("Date", datetime.now())
        payment_type = st.selectbox("Type", ["owed_to_me", "owed_by_me"])
        status = st.selectbox("Status", ["pending", "paid"])
    
    submitted = st.form_submit_button("Add Payment")
    if submitted:
        new_entry = pd.DataFrame([[date.strftime("%Y-%m-%d"), person, amount, payment_type, status]],
                               columns=["date", "person", "amount", "type", "status"])
        new_entry.to_csv(CSV_FILE, mode='a', header=False, index=False)
        st.success("Payment added!")
        generate_summary()

st.subheader("Recent Transactions")
df = pd.read_csv(CSV_FILE)
st.dataframe(df.tail(10))