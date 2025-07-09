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
SUMMARY_URL = "https://atonomous.github.io/payments-summary/"

def init_files():
    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=[
            "date", "person", "amount", "type", "status",
            "description", "payment_method", "cheque_number",
            "cheque_status", "transaction_status", "receipt_number"
        ]).to_csv(CSV_FILE, index=False)
    else:
        df = pd.read_csv(CSV_FILE)
        # Add 'receipt_number' column if it doesn't exist
        if 'receipt_number' not in df.columns:
            df['receipt_number'] = ''
            df.to_csv(CSV_FILE, index=False)

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
    payment_totals = df.groupby(['type', 'payment_method'])['amount'].sum().unstack().fillna(0)
    totals = {
        'total_received': df[df['type'] == 'paid_to_me']['amount'].sum(),
        'pending_received': df[(df['type'] == 'paid_to_me') & (df['transaction_status'] == 'pending')]['amount'].sum(),
        'total_paid': df[df['type'] == 'i_paid']['amount'].sum(),
        'pending_paid': df[(df['type'] == 'i_paid') & (df['transaction_status'] == 'pending')]['amount'].sum(),
        'cash_received': payment_totals.loc['paid_to_me', 'cash'] if 'cash' in payment_totals.columns and 'paid_to_me' in payment_totals.index else 0,
        'cheque_received': payment_totals.loc['paid_to_me', 'cheque'] if 'cheque' in payment_totals.columns and 'paid_to_me' in payment_totals.index else 0,
        'cash_paid': payment_totals.loc['i_paid', 'cash'] if 'cash' in payment_totals.columns and 'i_paid' in payment_totals.index else 0,
        'cheque_paid': payment_totals.loc['i_paid', 'cheque'] if 'cheque' in payment_totals.columns and 'i_paid' in payment_totals.index else 0
    }

    transactions = df.rename(columns={
        'date': 'Date', 'person': 'Person', 'type': 'Type',
        'transaction_status': 'Status', 'description': 'Description',
        'payment_method': 'Method', 'cheque_number': 'Cheque No.',
        'cheque_status': 'Cheque Status', 'receipt_number': 'Receipt No.'
    })
    transactions['Amount'] = transactions['amount']
    transactions['Type'] = transactions['Type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'})

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Summary</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
    <style>body{{font-family:'Inter',sans-serif;max-width:960px;margin:0 auto;padding:40px 20px;background:#f8fafc;color:#1e293b}}
    h1{{text-align:center;color:#0f172a}}.summary-box{{background:#fff;box-shadow:0 4px 12px rgba(0,0,0,0.06);padding:25px;border-radius:12px;margin-bottom:30px}}
    .summary-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:30px}}.summary-item h3{{margin:0;color:#2563eb}}
    table{{width:100%;border-collapse:collapse;margin-top:15px;background:white}}th,td{{padding:12px;text-align:left}}
    th{{background:#f1f5f9}}tr:nth-child(even){{background:#f9fafb}}</style></head><body>
    <h1>📊 Payment Summary</h1>
    <div class="summary-box">
    <div class="summary-grid">
        <div><h3>Total Received: Rs.{totals['total_received']:,.2f}</h3>
        <p>Pending: Rs.{totals['pending_received']:,.2f}</p>
        <p>Cash: Rs.{totals['cash_received']:,.2f} | Cheque: Rs.{totals['cheque_received']:,.2f}</p></div>
        <div><h3>Total Paid: Rs.{totals['total_paid']:,.2f}</h3>
        <p>Pending: Rs.{totals['pending_paid']:,.2f}</p>
        <p>Cash: Rs.{totals['cash_paid']:,.2f} | Cheque: Rs.{totals['cheque_paid']:,.2f}</p></div>
    </div></div>
    <h2>All Transactions</h2><table><thead><tr><th>Date</th><th>Person</th><th>Amount</th><th>Type</th>
    <th>Method</th><th>Cheque No.</th><th>Receipt No.</th><th>Status</th><th>Cheque Status</th><th>Description</th></tr></thead><tbody>"""

    for _, row in transactions.iterrows():
        html += f"<tr><td>{row['Date']}</td><td>{row['Person']}</td><td>Rs.{row['Amount']:,.2f}</td><td>{row['Type']}</td>" \
                f"<td>{row['Method'].capitalize()}</td><td>{row.get('Cheque No.', '-') or '-'}</td>" \
                f"<td>{row.get('Receipt No.', '-') or '-'}</td><td>{row['Status'].capitalize()}</td><td>{row.get('Cheque Status', '-') or '-'}</td><td>{row['Description']}</td></tr>"
    html += "</tbody></table></body></html>"

    os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        f.write(html)

# Streamlit UI
st.set_page_config(layout="wide")
st.title("💰 Payment Tracker")
st.sidebar.markdown(f"[🌐 View Public Summary]({SUMMARY_URL})", unsafe_allow_html=True)

# Session State Initialization
def init_state():
    keys = [
        'selected_transaction_type', 'payment_method', 'editing_row_idx', 'selected_person'
    ]
    defaults = {
        'selected_transaction_type': 'Paid to Me',
        'payment_method': 'cash',
        'editing_row_idx': None,
        'selected_person': "Select..." # Default value for the selectbox
    }
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = defaults[k]

init_state()

# Function to reset session state for elements not cleared by form
def reset_form_session_state_for_add_transaction():
    st.session_state['selected_transaction_type'] = 'Paid to Me'
    st.session_state['payment_method'] = 'cash'
    st.session_state['selected_person'] = "Select..." # Reset the selected person to default
    st.session_state['editing_row_idx'] = None # Ensure editing mode is off

tab1, tab2, tab3 = st.tabs(["Add Transaction", "View Transactions", "Manage People"])

# ------------------ Tab 1: Add Transaction ------------------
with tab1:
    st.subheader("Add New Transaction")

    # Transaction Type selection outside the form for immediate reactivity
    st.session_state['selected_transaction_type'] = st.radio(
        "Transaction Type", ["Paid to Me", "I Paid"], horizontal=True,
        key='selected_transaction_type_radio'
    )

    # Payment Method selection outside the form for immediate reactivity
    st.session_state['payment_method'] = st.radio(
        "Payment Method", ["cash", "cheque"], horizontal=True,
        key='payment_method_radio'
    )

    # Filter people based on the selected transaction type
    try:
        people_df = pd.read_csv(PEOPLE_FILE)
        category = 'investor' if st.session_state['selected_transaction_type'] == "Paid to Me" else 'client'
        filtered_people = people_df[people_df['category'] == category]['name'].tolist()
    except Exception:
        filtered_people = []

    person_options = ["Select..."] + sorted(filtered_people)
    
    # Ensure selected_person is a valid option or default to "Select..."
    if st.session_state['selected_person'] not in person_options:
        st.session_state['selected_person'] = "Select..."

    current_person_index = person_options.index(st.session_state['selected_person'])

    with st.form("transaction_form", clear_on_submit=True): # clear_on_submit handles resetting form fields
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount (Rs.)", min_value=0.0, format="%.2f")
            date = st.date_input("Date", value=datetime.now().date())

            receipt_number = ""
            cheque_number = ""
            cheque_status = ""

            if st.session_state['payment_method'] == "cash":
                receipt_number = st.text_input("Receipt Number")
            elif st.session_state['payment_method'] == "cheque":
                cheque_number = st.text_input("Cheque Number")
                cheque_status = st.selectbox(
                    "Cheque Status",
                    ["received/given", "processing", "bounced", "processing done"]
                )

        with col2:
            # st.session_state['selected_person'] is managed by this selectbox
            st.session_state['selected_person'] = st.selectbox(
                "Select Person", person_options, index=current_person_index, key='selected_person_dropdown'
            )
            if st.session_state['selected_person'] == "Select...":
                # If "Select..." is chosen, ensure the stored value is None for logic
                st.session_state['selected_person'] = None

            status = st.selectbox("Transaction Status", ["completed", "pending"])
            description = st.text_input("Description")

        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            if not st.session_state['selected_person']:
                st.warning("Please select a valid person.")
            elif st.session_state['payment_method'] == "cash" and not receipt_number:
                st.warning("Receipt Number is required for cash payments.")
            elif st.session_state['payment_method'] == "cheque" and not cheque_number:
                st.warning("Cheque Number is required for cheque payments.")
            else:
                new_row = {
                    "date": date.strftime("%Y-%m-%d"),
                    "person": st.session_state['selected_person'],
                    "amount": amount,
                    "type": 'paid_to_me' if st.session_state['selected_transaction_type'] == "Paid to Me" else 'i_paid',
                    "status": status,
                    "description": description,
                    "payment_method": st.session_state['payment_method'],
                    "cheque_number": cheque_number,
                    "cheque_status": cheque_status,
                    "transaction_status": status,
                    "receipt_number": receipt_number
                }
                pd.DataFrame([new_row]).to_csv(CSV_FILE, mode='a', header=False, index=False)
                generate_html_summary(pd.read_csv(CSV_FILE))
                git_push()
                st.success("Transaction added successfully.")
                reset_form_session_state_for_add_transaction()
                st.rerun()

# ------------------ Tab 2: View Transactions ------------------
with tab2:
    st.subheader("Transaction History")
    view_filter = st.radio("Filter by Type", ["All", "Received", "Paid"], horizontal=True, key='view_filter')
    method_filter = st.selectbox("Payment Method", ["All", "Cash", "Cheque"], key='method_filter')
    status_filter = st.selectbox("Status", ["All", "Completed", "Pending", "Received/Given", "Processing", "Bounced", "Processing Done"], key='status_filter')

    try:
        df = pd.read_csv(CSV_FILE)
        df['amount'] = df['amount'].astype(float)
        df['amount_display'] = df['amount'].apply(lambda x: f"Rs. {x:,.2f}")
        df['type_display'] = df['type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'})
        
        df['original_index'] = df.index

        filtered_df = df.copy()

        if view_filter != "All":
            filtered_df = filtered_df[filtered_df['type_display'] == view_filter]
        if method_filter != "All":
            filtered_df = filtered_df[filtered_df['payment_method'] == method_filter.lower()]
        if status_filter != "All":
            if status_filter in ["Completed", "Pending"]:
                filtered_df = filtered_df[filtered_df['transaction_status'] == status_filter.lower()]
            else:
                filtered_df = filtered_df[filtered_df['cheque_status'].str.lower() == status_filter.lower()]

        st.dataframe(filtered_df[[
            'date', 'person', 'amount_display', 'type_display', 'payment_method',
            'cheque_number', 'receipt_number', 'transaction_status', 'cheque_status', 'description', 'original_index'
        ]].rename(columns={
            'date': 'Date', 'person': 'Person', 'amount_display': 'Amount',
            'type_display': 'Type', 'payment_method': 'Method', 'cheque_number': 'Cheque No.',
            'receipt_number': 'Receipt No.', 'transaction_status': 'Status',
            'cheque_status': 'Cheque Status', 'description': 'Description',
            'original_index': 'Edit'
        }), use_container_width=True, hide_index=True,
        column_config={
            "Edit": st.column_config.ButtonColumn(
                "Edit",
                help="Click to edit transaction",
                key="edit_button_col"
            )
        })

        if st.session_state.get('edit_button_col') is not None:
            edited_row_index = st.session_state['edit_button_col']

            st.session_state['editing_row_idx'] = filtered_df.iloc[edited_row_index]['original_index']
            st.session_state['temp_edit_data'] = df.loc[st.session_state['editing_row_idx']].to_dict()
            st.rerun()

        if st.session_state['editing_row_idx'] is not None and st.session_state.get('temp_edit_data'):
            st.subheader("Edit Transaction")
            edit_data = st.session_state['temp_edit_data']
            
            with st.form("edit_transaction_form"):
                col1_edit, col2_edit = st.columns(2)
                with col1_edit:
                    edited_amount = st.number_input("Amount (Rs.)", value=float(edit_data.get('amount', 0.0)), format="%.2f", key='edit_amount')
                    edited_date = st.date_input("Date", value=datetime.strptime(edit_data['date'], "%Y-%m-%d").date(), key='edit_date')
                    edited_payment_method = st.radio("Payment Method", ["cash", "cheque"], horizontal=True, key='edit_payment_method', index=["cash", "cheque"].index(edit_data.get('payment_method', 'cash')))

                    edited_receipt_number = ""
                    edited_cheque_number = ""
                    edited_cheque_status = ""

                    if edited_payment_method == "cash":
                        edited_receipt_number = st.text_input("Receipt Number", value=edit_data.get('receipt_number', ''), key='edit_receipt_number')
                    elif edited_payment_method == "cheque":
                        edited_cheque_number = st.text_input("Cheque Number", value=edit_data.get('cheque_number', ''), key='edit_cheque_number')
                        edited_cheque_status = st.selectbox(
                            "Cheque Status",
                            ["received/given", "processing", "bounced", "processing done"],
                            index=["received/given", "processing", "bounced", "processing done"].index(edit_data.get('cheque_status', 'processing')),
                            key='edit_cheque_status'
                        )
                
                with col2_edit:
                    edited_person = st.selectbox("Select Person", people_df['name'].tolist(), index=people_df['name'].tolist().index(edit_data['person']), key='edit_person')
                    edited_transaction_status = st.selectbox("Transaction Status", ["completed", "pending"], index=["completed", "pending"].index(edit_data.get('transaction_status', 'completed')), key='edit_transaction_status')
                    edited_description = st.text_input("Description", value=edit_data.get('description', ''), key='edit_description')

                col_buttons = st.columns(2)
                with col_buttons[0]:
                    save_edited = st.form_submit_button("Save Changes")
                with col_buttons[1]:
                    cancel_edit = st.form_submit_button("Cancel")

                if save_edited:
                    if edited_payment_method == "cash" and not edited_receipt_number:
                        st.warning("Receipt Number is required for cash payments.")
                    elif edited_payment_method == "cheque" and not edited_cheque_number:
                        st.warning("Cheque Number is required for cheque payments.")
                    else:
                        df.loc[st.session_state['editing_row_idx']] = {
                            "date": edited_date.strftime("%Y-%m-%d"),
                            "person": edited_person,
                            "amount": edited_amount,
                            "type": edit_data['type'],
                            "status": edited_transaction_status,
                            "description": edited_description,
                            "payment_method": edited_payment_method,
                            "cheque_number": edited_cheque_number,
                            "cheque_status": edited_cheque_status,
                            "transaction_status": edited_transaction_status,
                            "receipt_number": edited_receipt_number
                        }
                        df.to_csv(CSV_FILE, index=False)
                        generate_html_summary(df)
                        git_push()
                        st.success("Transaction updated successfully.")
                        st.session_state['editing_row_idx'] = None
                        st.session_state['temp_edit_data'] = {}
                        st.rerun()
                elif cancel_edit:
                    st.session_state['editing_row_idx'] = None
                    st.session_state['temp_edit_data'] = {}
                    st.rerun()

    except Exception as e:
        st.error(f"Error loading history: {e}")

# ------------------ Tab 3: Manage People ------------------
with tab3:
    st.subheader("Manage People")
    with st.expander("Add New Person"):
        with st.form("person_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name")
            category = c2.selectbox("Category", ["investor", "client"])
            if st.form_submit_button("Add Person"):
                if not name.strip():
                    st.warning("Name is required.")
                else:
                    df = pd.read_csv(PEOPLE_FILE)
                    if name.strip() in df['name'].values:
                        st.warning("Person already exists.")
                    else:
                        pd.DataFrame([[name.strip(), category]], columns=["name", "category"])\
                            .to_csv(PEOPLE_FILE, mode='a', header=False, index=False)
                        st.success(f"{name.strip()} added!")
                        st.rerun()

    try:
        ppl = pd.read_csv(PEOPLE_FILE)
        st.dataframe(ppl, use_container_width=True, hide_index=True)
        to_del = st.selectbox("Delete Person", ppl['name'] if not ppl.empty else [])
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

# ------------------ Sidebar: Balances ------------------
st.sidebar.header("Current Balances")
try:
    df_bal = pd.read_csv(CSV_FILE)
    df_bal['amount'] = df_bal['amount'].astype(float)
    rec = df_bal[df_bal['type'] == 'paid_to_me']['amount'].sum()
    paid = df_bal[df_bal['type'] == 'i_paid']['amount'].sum()
    cash_rec = df_bal[(df_bal['type'] == 'paid_to_me') & (df_bal['payment_method'] == 'cash')]['amount'].sum()
    cheque_rec = df_bal[(df_bal['type'] == 'paid_to_me') & (df_bal['payment_method'] == 'cheque')]['amount'].sum()
    cash_paid = df_bal[(df_bal['type'] == 'i_paid') & (df_bal['payment_method'] == 'cash')]['amount'].sum()
    cheque_paid = df_bal[(df_bal['type'] == 'i_paid') & (df_bal['payment_method'] == 'cheque')]['amount'].sum()

    st.sidebar.metric("Total Received", f"Rs. {rec:,.2f}")
    st.sidebar.metric("Total Paid", f"Rs. {paid:,.2f}")
    st.sidebar.metric("Net Balance", f"Rs. {rec - paid:,.2f}", delta_color="inverse")

    with st.sidebar.expander("Payment Methods"):
        st.write("**Received**")
        st.write(f"Cash: Rs. {cash_rec:,.2f}")
        st.write(f"Cheque: Rs. {cheque_rec:,.2f}")
        st.write("**Paid**")
        st.write(f"Cash: Rs. {cash_paid:,.2f}")
        st.write(f"Cheque: Rs. {cheque_paid:,.2f}")
except Exception as e:
    st.sidebar.info("No transactions yet.")
