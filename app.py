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

# Initialize data files
def init_files():
    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=["date", "person", "amount", "type", "status", "description"]).to_csv(CSV_FILE, index=False)
    
    if not os.path.exists(PEOPLE_FILE):
        pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)
    else:
        # Ensure people.csv has correct format
        df = pd.read_csv(PEOPLE_FILE)
        if 'category' not in df.columns:
            df['category'] = 'client'  # Default category
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
        st.error(f"Error updating GitHub: {str(e)}")

def generate_summary():
    try:
        df = pd.read_csv(CSV_FILE)
        people_df = pd.read_csv(PEOPLE_FILE)
        
        # Ensure all columns exist
        for col in ["description"]:
            if col not in df.columns:
                df[col] = ''
        
        df = pd.merge(df, people_df, left_on='person', right_on='name', how='left')
        
        summary = {
            "received": df[df['type'] == 'paid_to_me']['amount'].sum(),
            "paid": df[df['type'] == 'i_paid']['amount'].sum(),
            "pending_received": df[(df['type'] == 'paid_to_me') & (df['status'] == 'pending')]['amount'].sum(),
            "pending_paid": df[(df['type'] == 'i_paid') & (df['status'] == 'pending')]['amount'].sum(),
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
                    <h3>Received from others: Rs.{summary['received']:,.2f}</h3>
                    <p>Pending: Rs.{summary['pending_received']:,.2f}</p>
                </div>
                <div>
                    <h3>Paid to others: Rs.{summary['paid']:,.2f}</h3>
                    <p>Pending: Rs.{summary['pending_paid']:,.2f}</p>
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
                    <th>Description</th>
                </tr>
                {"".join(
                    f"<tr><td>{t['date']}</td><td>{t['person']}</td><td>Rs.{float(t['amount']):,.2f}</td>"
                    f"<td>{'Received from' if t['type'] == 'paid_to_me' else 'Paid to'}</td>"
                    f"<td>{t['status'].capitalize()}</td><td>{t.get('description', '')}</td></tr>" 
                    for t in summary['transactions']
                )}
            </table>
        </body>
        </html>
        """
        
        os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
        with open(SUMMARY_FILE, 'w') as f:
            f.write(html)
        git_push()
    except Exception as e:
        st.error(f"Error generating summary: {str(e)}")

# Streamlit UI
st.set_page_config(layout="wide")
st.title("💰 Payment Tracker")

# Tab layout
tab1, tab2, tab3 = st.tabs(["Add Transaction", "View Transactions", "Manage People"])

with tab1:
    with st.form("payment_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            transaction_type = st.radio("Transaction Type", ["Paid to Me", "I Paid"], horizontal=True)
            amount = st.number_input("Amount (Rs.)", min_value=0.0, step=0.01, format="%.2f")
            date = st.date_input("Date", datetime.now())
            
        with col2:
            try:
                people_df = pd.read_csv(PEOPLE_FILE)
                
                # Force category to string and strip whitespace
                people_df['category'] = people_df['category'].astype(str).str.strip().str.lower()
                
                if transaction_type == "Paid to Me":
                    filtered_people = people_df[people_df['category'] == 'investor']['name'].tolist()
                else:
                    filtered_people = people_df[people_df['category'] == 'client']['name'].tolist()
                
                if not filtered_people:
                    st.warning(f"No {'investors' if transaction_type == 'Paid to Me' else 'clients'} found")
                    filtered_people = people_df['name'].tolist()
                
                person = st.selectbox(
                    f"Select {'Investor' if transaction_type == 'Paid to Me' else 'Client'}",
                    options=filtered_people,
                    index=0 if filtered_people else None
                )
                
            except Exception as e:
                st.error(f"Error loading people: {str(e)}")
                person = None
            
            status = st.selectbox("Status", ["completed", "pending"])
            description = st.text_input("Description (optional)")
        
        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            if not person:
                st.error("Please select a person")
            else:
                try:
                    new_entry = pd.DataFrame([[
                        date.strftime("%Y-%m-%d"), 
                        person, 
                        amount, 
                        'paid_to_me' if transaction_type == "Paid to Me" else 'i_paid', 
                        status,
                        description or ''
                    ]], columns=["date", "person", "amount", "type", "status", "description"])
                    
                    new_entry.to_csv(CSV_FILE, mode='a', header=False, index=False)
                    st.success("Transaction added successfully!")
                    generate_summary()
                except Exception as e:
                    st.error(f"Error adding transaction: {str(e)}")

with tab2:
    st.subheader("Transaction History")
    
    view_option = st.radio("View", ["All", "Received", "Paid"], horizontal=True)
    
    try:
        df = pd.read_csv(CSV_FILE)
        if len(df) > 0:
            for col in ["description"]:
                if col not in df.columns:
                    df[col] = ''
            
            people_df = pd.read_csv(PEOPLE_FILE)
            df = pd.merge(df, people_df, left_on='person', right_on='name', how='left')
            
            df['amount'] = df['amount'].apply(lambda x: f"Rs. {float(x):,.2f}")
            df['type'] = df['type'].apply(lambda x: "Received" if x == "paid_to_me" else "Paid")
            
            if view_option == "Received":
                df = df[df['type'] == "Received"]
            elif view_option == "Paid":
                df = df[df['type'] == "Paid"]
            
            columns_to_show = ['date', 'person', 'amount', 'type', 'status']
            if 'description' in df.columns:
                columns_to_show.append('description')
            
            st.dataframe(df[columns_to_show], hide_index=True, use_container_width=True)
        else:
            st.info("No transactions recorded yet.")
    except Exception as e:
        st.error(f"Error loading transactions: {str(e)}")

with tab3:
    st.subheader("Manage People")
    
    with st.expander("➕ Add New Person"):
        with st.form("person_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name")
            with col2:
                category = st.selectbox("Category", ["investor", "client"])
            
            submitted = st.form_submit_button("Add Person")
            if submitted:
                try:
                    people_df = pd.read_csv(PEOPLE_FILE)
                    if name.strip() == "":
                        st.warning("Please enter a name")
                    elif name not in people_df['name'].values:
                        new_person = pd.DataFrame([[name.strip(), category]], columns=["name", "category"])
                        new_person.to_csv(PEOPLE_FILE, mode='a', header=False, index=False)
                        st.success(f"{name} added as {category}!")
                        st.rerun()
                    else:
                        st.warning("This person already exists!")
                except Exception as e:
                    st.error(f"Error adding person: {str(e)}")
    
    try:
        people_df = pd.read_csv(PEOPLE_FILE)
        if len(people_df) > 0:
            st.dataframe(people_df, hide_index=True, use_container_width=True)
            
            person_to_delete = st.selectbox("Select person to delete", people_df['name'])
            if st.button("Delete Selected Person"):
                transactions = pd.read_csv(CSV_FILE)
                if person_to_delete in transactions['person'].values:
                    st.error("Cannot delete - this person has existing transactions")
                else:
                    people_df = people_df[people_df['name'] != person_to_delete]
                    people_df.to_csv(PEOPLE_FILE, index=False)
                    st.success(f"{person_to_delete} deleted!")
                    st.rerun()
        else:
            st.info("No people added yet.")
    except Exception as e:
        st.error(f"Error loading people: {str(e)}")

# Current balances in sidebar
st.sidebar.header("Current Balances")
try:
    df = pd.read_csv(CSV_FILE)
    if len(df) > 0:
        received = df[df['type'] == 'paid_to_me']['amount'].sum()
        paid = df[df['type'] == 'i_paid']['amount'].sum()
        st.sidebar.metric("Total Received", f"Rs. {received:,.2f}")
        st.sidebar.metric("Total Paid", f"Rs. {paid:,.2f}")
        st.sidebar.metric("Net Balance", f"Rs. {received - paid:,.2f}", delta_color="inverse")
    else:
        st.sidebar.info("No transactions yet")
except Exception as e:
    st.sidebar.error("Error loading balances")