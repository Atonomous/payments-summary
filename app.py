import streamlit as st
import pandas as pd
from datetime import datetime
import os
from git import Repo

# Configuration
REPO_PATH = os.getcwd()
CSV_FILE = os.path.join(REPO_PATH, "payments.csv")
PEOPLE_FILE = os.path.join(REPO_PATH, "people.csv")
SUMMARY_FILE = os.path.join(REPO_PATH, "docs/index.html")

def init_files():
    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=["date", "person", "amount", "type", "status", "description"]).to_csv(CSV_FILE, index=False)
    if not os.path.exists(PEOPLE_FILE):
        pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)
    else:
        df = pd.read_csv(PEOPLE_FILE)
        if 'category' not in df.columns:
            df['category'] = 'client'
            df.to_csv(PEOPLE_FILE, index=False)

init_files()

def git_push():
    try:
        repo = Repo(REPO_PATH)
        repo.git.add(update=True)
        repo.index.commit("Automated update: payment records")
        origin = repo.remote(name='origin')
        origin.push()
    except Exception as e:
        st.error(f"Error updating GitHub: {e}")

def generate_html_summary(df):
    df = df.copy()
    df['amount'] = df['amount'].astype(float)
    totals = {
        'total_received': df[df['type'] == 'paid_to_me']['amount'].sum(),
        'pending_received': df[(df['type'] == 'paid_to_me') & (df['status'] == 'pending')]['amount'].sum(),
        'total_paid': df[df['type'] == 'i_paid']['amount'].sum(),
        'pending_paid': df[(df['type'] == 'i_paid') & (df['status'] == 'pending')]['amount'].sum()
    }

    transactions = df.rename(columns={
        'date': 'Date', 'person': 'Person', 'type': 'Type', 'status': 'Status', 'description': 'Description'
    })
    transactions['Amount'] = transactions['amount']  # For display
    transactions['Type'] = transactions['Type'].map({'paid_to_me':'Received', 'i_paid':'Paid'})

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Payment Summary</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>body{{font-family:'Inter',sans-serif;max-width:960px;margin:0 auto;padding:40px 20px;background:#f8fafc;color:#1e293b}}
    h1{{text-align:center;margin-bottom:30px;color:#0f172a}}.summary-box{{background:#fff;box-shadow:0 4px 12px rgba(0,0,0,0.06);padding:25px;border-radius:12px;margin-bottom:30px;display:flex;justify-content:space-between;gap:30px}}
    .summary-box div{{flex:1}}.summary-box h3{{margin:0;font-size:20px;color:#2563eb}}.summary-box p{{margin:6px 0 0;color:#64748b}}
    h2{{margin-top:40px;color:#334155}}table{{width:100%;border-collapse:collapse;margin-top:15px;background:white;box-shadow:0 2px 8px rgba(0,0,0,0.04);border-radius:8px;overflow:hidden}}
    th,td{{padding:12px 15px;text-align:left}}th{{background-color:#f1f5f9;color:#475569;font-weight:600}}
    tr:nth-child(even){{background-color:#f9fafb}}tr:hover{{background-color:#eef2f7}}
    @media(max-width:600px){{.summary-box{{flex-direction:column}}th,td{{font-size:14px}}}}</style></head><body>
    <h1>📊 Payment Summary</h1><div class="summary-box">
    <div><h3>Received from others: Rs.{totals['total_received']:,.2f}</h3><p>Pending: Rs.{totals['pending_received']:,.2f}</p></div>
    <div><h3>Paid to others: Rs.{totals['total_paid']:,.2f}</h3><p>Pending: Rs.{totals['pending_paid']:,.2f}</p></div></div>
    <h2>All Transactions</h2><table><thead><tr><th>Date</th><th>Person</th><th>Amount</th><th>Type</th><th>Status</th><th>Description</th></tr></thead><tbody>"""

    for _, row in transactions.iterrows():
        html += f"<tr><td>{row['Date']}</td><td>{row['Person']}</td><td>Rs.{row['Amount']:,.2f}</td><td>{row['Type']}</td><td>{row['Status'].capitalize()}</td><td>{row['Description']}</td></tr>"
    html += "</tbody></table></body></html>"

    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(html)

# Streamlit UI setup
st.set_page_config(layout="wide")
st.title("💰 Payment Tracker")

# Sidebar: link to public summary
SUMMARY_URL = "https://atonomous.github.io/payments-summary/"
st.sidebar.markdown("[🌐 View Public Summary](" + SUMMARY_URL + ")", unsafe_allow_html=True)

def init_state():
    defaults = {
        'selected_transaction_type': 'Paid to Me',
        'selected_person': None,
        'amount_input': 0.0,
        'date_input': datetime.now().date(),
        'status_input': 'completed',
        'description_input': ''
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_state()

def reset_transaction_form():
    st.session_state['amount_input'] = 0.0
    st.session_state['date_input'] = datetime.now().date()
    st.session_state['status_input'] = 'completed'
    st.session_state['description_input'] = ''
    st.session_state['selected_person'] = None

tab1, tab2, tab3 = st.tabs(["Add Transaction", "View Transactions", "Manage People"])

with tab1:
    st.subheader("Add New Transaction")
    with st.form("transaction_form"):
        col1, col2 = st.columns(2)
        with col1:
            t_type = st.radio("Transaction Type", ["Paid to Me", "I Paid"], horizontal=True,
                               key='selected_transaction_type')
            amount = st.number_input("Amount (Rs.)", 0.0, step=0.01, format="%.2f", key='amount_input')
            date = st.date_input("Date", value=st.session_state['date_input'], key='date_input')
        with col2:
            try:
                people_df = pd.read_csv(PEOPLE_FILE)
                people_df['category'] = people_df['category'].astype(str).str.strip().str.lower()
            except:
                people_df = pd.DataFrame(columns=['name', 'category'])
            cat = 'investor' if t_type == "Paid to Me" else 'client'
            people_list = people_df[people_df['category'] == cat]['name'].tolist()
            person = st.selectbox("Select Person", ["Select..."] + people_list)
            st.session_state['selected_person'] = None if person == "Select..." else person
            status = st.selectbox("Status", ["completed", "pending"], key='status_input')
            description = st.text_input("Description (optional)", key='description_input')
        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            if st.session_state['selected_person'] is None:
                st.error("Please select a valid person.")
            else:
                df = pd.read_csv(CSV_FILE)
                df_entry = pd.DataFrame([[
                    st.session_state['date_input'].strftime("%Y-%m-%d"),
                    st.session_state['selected_person'],
                    st.session_state['amount_input'],
                    'paid_to_me' if t_type == "Paid to Me" else 'i_paid',
                    st.session_state['status_input'],
                    st.session_state['description_input']
                ]], columns=["date", "person", "amount", "type", "status", "description"])
                try:
                    df_entry.to_csv(CSV_FILE, mode='a', header=False, index=False)
                    st.success("Transaction added!")
                    df_all = pd.read_csv(CSV_FILE)
                    generate_html_summary(df_all)
                    git_push()
                    reset_transaction_form()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving transaction: {e}")

with tab2:
    st.subheader("Transaction History")
    view_opt = st.radio("View", ["All", "Received", "Paid"], horizontal=True)
    try:
        df = pd.read_csv(CSV_FILE)
        df['amount'] = df['amount'].astype(float)
        df['type'] = df['type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'})
        df['amount'] = df['amount'].apply(lambda x: f"Rs. {x:,.2f}")
        if view_opt != "All":
            df = df[df['type'] == view_opt]
        st.dataframe(df[['date', 'person', 'amount', 'type', 'status', 'description']],
                      use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error loading history: {e}")

with tab3:
    st.subheader("Manage People")
    with st.expander("Add New Person"):
        with st.form("person_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name")
            category = c2.selectbox("Category", ["investor", "client"])
            if st.form_submit_button("Add Person"):
                if not name.strip():
                    st.warning("Enter a name.")
                else:
                    ppl = pd.read_csv(PEOPLE_FILE)
                    if name.strip() in ppl['name'].values:
                        st.warning("Already exists.")
                    else:
                        pd.DataFrame([[name.strip(), category]], columns=["name", "category"])\
                          .to_csv(PEOPLE_FILE, mode='a', header=False, index=False)
                        st.success(f"{name.strip()} added!")
                        st.rerun()
    try:
        ppl = pd.read_csv(PEOPLE_FILE)
        st.dataframe(ppl, use_container_width=True, hide_index=True)
        to_del = st.selectbox("Delete person", ppl['name'] if not ppl.empty else [])
        if st.button("Delete"):
            tx = pd.read_csv(CSV_FILE)
            if to_del in tx['person'].values:
                st.error("Cannot delete person with transactions.")
            else:
                ppl = ppl[ppl['name'] != to_del]
                ppl.to_csv(PEOPLE_FILE, index=False)
                st.success("Deleted.")
                st.rerun()
    except Exception as e:
        st.error(f"Error managing people: {e}")

# Sidebar Balances
st.sidebar.header("Current Balances")
try:
    df_bal = pd.read_csv(CSV_FILE)
    df_bal['amount'] = df_bal['amount'].astype(float)
    rec = df_bal[df_bal['type'] == 'paid_to_me']['amount'].sum()
    pnt = df_bal[df_bal['type'] == 'i_paid']['amount'].sum()
    st.sidebar.metric("Total Received", f"Rs. {rec:,.2f}")
    st.sidebar.metric("Total Paid", f"Rs. {pnt:,.2f}")
    st.sidebar.metric("Net Balance", f"Rs. {rec - pnt:,.2f}", delta_color="inverse")
except:
    st.sidebar.info("No transactions yet.")
