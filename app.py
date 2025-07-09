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
    try:
        # Initialize payments.csv if it doesn't exist
        if not os.path.exists(CSV_FILE):
            pd.DataFrame(columns=[
                "date", "person", "amount", "type", "status",
                "description", "payment_method", "reference_number",
                "cheque_status", "transaction_status"
            ]).to_csv(CSV_FILE, index=False)
            st.toast(f"Created new {CSV_FILE}")
        else:
            # Handle migration from old format to new format if needed
            df = pd.read_csv(CSV_FILE)
            if 'receipt_number' in df.columns or 'cheque_number' in df.columns:
                df['reference_number'] = df.apply(
                    lambda row: row['receipt_number'] if row['payment_method'] == 'cash' 
                    else row['cheque_number'] if row['payment_method'] == 'cheque' 
                    else '', 
                    axis=1
                )
                df = df.drop(columns=['receipt_number', 'cheque_number'], errors='ignore')
                df.to_csv(CSV_FILE, index=False)

        # Initialize people.csv if it doesn't exist
        if not os.path.exists(PEOPLE_FILE):
            pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)
            st.toast(f"Created new {PEOPLE_FILE}")
        else:
            df = pd.read_csv(PEOPLE_FILE)
            if 'category' not in df.columns:
                df['category'] = 'client'
                df.to_csv(PEOPLE_FILE, index=False)
    except Exception as e:
        st.error(f"Error initializing files: {e}")

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
    try:
        # Create a copy and ensure proper data types
        df = df.copy()
        
        # Convert amounts to float and handle missing values
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        
        # Format dates as day-month-year
        df['formatted_date'] = pd.to_datetime(df['date']).dt.strftime('%d-%m-%Y')
        
        # Force string type for reference numbers
        df['reference_number'] = df['reference_number'].astype(str)
        
        # Clean up 'nan' strings and empty values
        df['reference_number'] = df['reference_number'].replace('nan', '').replace('None', '')
        
        # Format reference numbers to avoid scientific notation
        def format_reference_number(num):
            if num.replace('.', '').isdigit():
                try:
                    clean_num = num.replace(',', '').replace('.', '')
                    return "{:,}".format(int(clean_num))
                except:
                    return num
            return num
        
        df['reference_number'] = df['reference_number'].apply(format_reference_number)
        
        # Calculate payment totals
        payment_totals = df.groupby(['type', 'payment_method'])['amount'].sum().unstack().fillna(0)
        
        # Prepare summary statistics
        totals = {
            'total_received': df[df['type'] == 'paid_to_me']['amount'].sum(),
            'pending_received': df[(df['type'] == 'paid_to_me') & 
                                  (df['transaction_status'] == 'pending')]['amount'].sum(),
            'total_paid': df[df['type'] == 'i_paid']['amount'].sum(),
            'pending_paid': df[(df['type'] == 'i_paid') & 
                               (df['transaction_status'] == 'pending')]['amount'].sum(),
            'cash_received': payment_totals.loc['paid_to_me', 'cash'] 
                             if 'cash' in payment_totals.columns and 'paid_to_me' in payment_totals.index 
                             else 0,
            'cheque_received': payment_totals.loc['paid_to_me', 'cheque'] 
                               if 'cheque' in payment_totals.columns and 'paid_to_me' in payment_totals.index 
                               else 0,
            'cash_paid': payment_totals.loc['i_paid', 'cash'] 
                          if 'cash' in payment_totals.columns and 'i_paid' in payment_totals.index 
                          else 0,
            'cheque_paid': payment_totals.loc['i_paid', 'cheque'] 
                            if 'cheque' in payment_totals.columns and 'i_paid' in payment_totals.index 
                            else 0,
            'net_balance': (df[df['type'] == 'paid_to_me']['amount'].sum() - 
                           df[df['type'] == 'i_paid']['amount'].sum())
        }

        # Prepare transactions table
        transactions = df.rename(columns={
            'date': 'Date', 
            'person': 'Person', 
            'type': 'Type',
            'transaction_status': 'Status', 
            'description': 'Description',
            'payment_method': 'Method', 
            'reference_number': 'Reference No.',
            'cheque_status': 'Cheque Status'
        })
        
        transactions['Amount'] = transactions['amount'].apply(lambda x: f"Rs. {x:,.2f}")
        transactions['Type'] = transactions['Type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'})
        
        # Generate HTML with premium styling and filters
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Summary | Financial Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <style>
        /* [Previous CSS styles remain the same] */
        
        table {{
            width: 100%;
            table-layout: fixed;
        }}
        th:nth-child(1), td:nth-child(1) {{
            width: 100px;  /* Fixed width for date column */
        }}
        th:nth-child(2), td:nth-child(2) {{
            width: 150px;  /* Fixed width for person column */
        }}
        th:nth-child(3), td:nth-child(3) {{
            width: 100px;  /* Fixed width for amount column */
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">
                <i class="fas fa-wallet"></i> Payment Tracker
            </div>
            <h1 class="report-title">Payment Summary Report</h1>
            <div class="report-date">
                <i class="far fa-calendar-alt"></i> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </header>
        
        <!-- [Previous summary cards HTML remains the same] -->
        
        <table id="transactions-table">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Person</th>
                    <th>Amount</th>
                    <th>Type</th>
                    <th>Method</th>
                    <th>Reference No.</th>
                    <th>Status</th>
                    <th>Cheque Status</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>"""

        # Add transaction rows with data attributes for filtering
        for _, row in transactions.iterrows():
            status_class = row['Status'].lower().replace(' ', '-')
            cheque_status_class = str(row['Cheque Status']).lower().replace(' ', '-').replace('/', '-')
            
            html += f"""
                <tr data-date="{row['Date']}" 
                    data-person="{row['Person']}" 
                    data-type="{'paid_to_me' if row['Type'] == 'Received' else 'i_paid'}" 
                    data-method="{row['Method'].lower()}" 
                    data-cheque-status="{row['Cheque Status'].lower() if pd.notna(row['Cheque Status']) else ''}">
                    <td>{row['formatted_date']}</td>
                    <td>{row['Person']}</td>
                    <td>{row['Amount']}</td>
                    <td>{row['Type']}</td>
                    <td>{row['Method'].capitalize()}</td>
                    <td>{row['Reference No.'] if row['Reference No.'] else '-'}</td>
                    <td><span class="status {status_class}">{row['Status'].capitalize()}</span></td>
                    <td><span class="status {cheque_status_class}">{row['Cheque Status'] if pd.notna(row['Cheque Status']) else '-'}</span></td>
                    <td>{row['Description'] if pd.notna(row['Description']) else '-'}</td>
                </tr>"""

        html += """
            </tbody>
        </table>
        
        <!-- [Rest of the HTML remains the same] -->
    </div>
</body>
</html>"""

        # Save the HTML file
        os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            f.write(html)
    except Exception as e:
        st.error(f"Error generating HTML summary: {e}")

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
        'selected_person': "Select..."
    }
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = defaults[k]

init_state()

def reset_form_session_state_for_add_transaction():
    st.session_state['selected_transaction_type'] = 'Paid to Me'
    st.session_state['payment_method'] = 'cash'
    st.session_state['selected_person'] = "Select..."
    st.session_state['editing_row_idx'] = None

tab1, tab2, tab3 = st.tabs(["Add Transaction", "View Transactions", "Manage People"])

# ------------------ Tab 1: Add Transaction ------------------
with tab1:
    st.subheader("Add New Transaction")
    st.session_state['selected_transaction_type'] = st.radio(
        "Transaction Type", ["Paid to Me", "I Paid"], horizontal=True,
        key='selected_transaction_type_radio'
    )
    st.session_state['payment_method'] = st.radio(
        "Payment Method", ["cash", "cheque"], horizontal=True,
        key='payment_method_radio'
    )

    try:
        people_df = pd.read_csv(PEOPLE_FILE)
        category = 'investor' if st.session_state['selected_transaction_type'] == "Paid to Me" else 'client'
        filtered_people = people_df[people_df['category'] == category]['name'].tolist()
    except Exception as e:
        st.error(f"Error loading people data: {e}")
        filtered_people = []

    person_options = ["Select..."] + sorted(filtered_people)
    
    if st.session_state['selected_person'] not in person_options:
        st.session_state['selected_person'] = "Select..."

    current_person_index = person_options.index(st.session_state['selected_person'])

    with st.form("transaction_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount (Rs.)", min_value=0.0, format="%.2f")
            date = st.date_input("Date", value=datetime.now().date())

            reference_number = st.text_input("Reference Number (Receipt/Cheque No.)")
            
            cheque_status = ""
            if st.session_state['payment_method'] == "cheque":
                cheque_status = st.selectbox(
                    "Cheque Status",
                    ["received/given", "processing", "bounced", "processing done"]
                )

        with col2:
            st.session_state['selected_person'] = st.selectbox(
                "Select Person", person_options, index=current_person_index, key='selected_person_dropdown'
            )
            if st.session_state['selected_person'] == "Select...":
                st.session_state['selected_person'] = None

            status = st.selectbox("Transaction Status", ["completed", "pending"])
            description = st.text_input("Description")

        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            if not st.session_state['selected_person']:
                st.warning("Please select a valid person.")
            elif amount <= 0:
                st.warning("Amount must be greater than 0.")
            elif not reference_number:
                st.warning("Reference Number is required.")
            else:
                try:
                    new_row = {
                        "date": date.strftime("%Y-%m-%d"),
                        "person": st.session_state['selected_person'],
                        "amount": amount,
                        "type": 'paid_to_me' if st.session_state['selected_transaction_type'] == "Paid to Me" else 'i_paid',
                        "status": status,
                        "description": description,
                        "payment_method": st.session_state['payment_method'],
                        "reference_number": reference_number,
                        "cheque_status": cheque_status if st.session_state['payment_method'] == "cheque" else "",
                        "transaction_status": status
                    }
                    pd.DataFrame([new_row]).to_csv(CSV_FILE, mode='a', header=False, index=False)
                    generate_html_summary(pd.read_csv(CSV_FILE))
                    git_push()
                    st.success("Transaction added successfully.")
                    reset_form_session_state_for_add_transaction()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving transaction: {e}")

# ------------------ Tab 2: View Transactions ------------------
with tab2:
    st.subheader("Transaction History")
    
    try:
        df = pd.read_csv(CSV_FILE)
        
        # Check if DataFrame is empty
        if df.empty:
            st.info("No transactions recorded yet.")
            st.stop()
            
        # Ensure required columns exist
        required_columns = ['date', 'person', 'amount', 'type', 'payment_method',
                         'transaction_status', 'cheque_status', 'description', 'reference_number']
        
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            st.error(f"Missing required columns in data: {', '.join(missing_cols)}")
            st.stop()
            
        # Convert amount to float and handle missing values
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['amount_display'] = df['amount'].apply(lambda x: f"Rs. {x:,.2f}")
        df['type_display'] = df['type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'})
        df['original_index'] = df.index
        df['formatted_date'] = pd.to_datetime(df['date']).dt.strftime('%d-%m-%Y')

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            view_filter = st.radio("Filter by Type", ["All", "Received", "Paid"], horizontal=True)
        with col2:
            method_filter = st.selectbox("Payment Method", ["All", "Cash", "Cheque"])
        with col3:
            status_filter = st.selectbox("Status", ["All", "Completed", "Pending", "Received/Given", "Processing", "Bounced", "Processing Done"])

        # Apply filters
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

        # Display DataFrame with clearer column names
        display_columns = {
            'original_index': 'ID',
            'formatted_date': 'Date',
            'person': 'Person',
            'amount_display': 'Amount',
            'type_display': 'Type',
            'payment_method': 'Method',
            'reference_number': 'Reference No.',
            'transaction_status': 'Status',
            'cheque_status': 'Cheque Status',
            'description': 'Description'
        }
        
        st.dataframe(
            filtered_df[list(display_columns.keys())].rename(columns=display_columns),
            use_container_width=True,
            hide_index=True
        )

        # Edit Section
        if not filtered_df.empty:
            st.markdown("---")
            st.subheader("Edit Transaction")
            
            edit_options = [f"ID: {idx} - {row['formatted_date']} - {row['person']} - Rs.{row['amount']:,.2f}" 
                           for idx, row in filtered_df.iterrows()]
            
            selected_edit_option = st.selectbox(
                "Select transaction to edit:", 
                ["Select a transaction"] + edit_options,
                key='select_edit_transaction'
            )
            
            if selected_edit_option != "Select a transaction":
                selected_original_index = int(selected_edit_option.split(' - ')[0].replace('ID: ', ''))
                
                if st.button("Edit Selected Transaction", key='edit_button'):
                    st.session_state['editing_row_idx'] = selected_original_index
                    st.session_state['temp_edit_data'] = df.loc[st.session_state['editing_row_idx']].to_dict()
                    st.rerun()

        # Edit Form (appears when editing_row_idx is set)
        if st.session_state['editing_row_idx'] is not None and st.session_state.get('temp_edit_data'):
            st.markdown("---")
            st.subheader("Edit Transaction Details")
            edit_data = st.session_state['temp_edit_data']
            
            with st.form("edit_transaction_form"):
                col1_edit, col2_edit = st.columns(2)
                with col1_edit:
                    edited_amount = st.number_input("Amount (Rs.)", value=float(edit_data.get('amount', 0.0)), format="%.2f", key='edit_amount')
                    
                    try:
                        default_date_value = datetime.strptime(edit_data.get('date', ''), "%Y-%m-%d").date()
                    except:
                        default_date_value = datetime.now().date()
                    edited_date = st.date_input("Date", value=default_date_value, key='edit_date')

                    edited_payment_method = st.radio(
                        "Payment Method", 
                        ["cash", "cheque"], 
                        horizontal=True, 
                        index=["cash", "cheque"].index(edit_data.get('payment_method', 'cash')),
                        key='edit_payment_method'
                    )

                    edited_reference_number = st.text_input(
                        "Reference Number", 
                        value=edit_data.get('reference_number', ''), 
                        key='edit_reference_number'
                    )

                    if edited_payment_method == "cheque":
                        edited_cheque_status = st.selectbox(
                            "Cheque Status",
                            ["received/given", "processing", "bounced", "processing done"],
                            index=["received/given", "processing", "bounced", "processing done"].index(
                                edit_data.get('cheque_status', 'processing')
                            ),
                            key='edit_cheque_status'
                        )
                    else:
                        edited_cheque_status = ""
                
                with col2_edit:
                    try:
                        people_df = pd.read_csv(PEOPLE_FILE)
                        edited_person = st.selectbox(
                            "Select Person", 
                            people_df['name'].tolist(), 
                            index=people_df['name'].tolist().index(edit_data['person']), 
                            key='edit_person'
                        )
                    except Exception as e:
                        st.error(f"Error loading people data: {e}")
                        edited_person = edit_data['person']

                    edited_transaction_status = st.selectbox(
                        "Transaction Status", 
                        ["completed", "pending"], 
                        index=["completed", "pending"].index(edit_data.get('transaction_status', 'completed')), 
                        key='edit_transaction_status'
                    )
                    edited_description = st.text_input(
                        "Description", 
                        value=edit_data.get('description', ''), 
                        key='edit_description'
                    )

                col_buttons = st.columns(2)
                with col_buttons[0]:
                    save_edited = st.form_submit_button("💾 Save Changes")
                with col_buttons[1]:
                    cancel_edit = st.form_submit_button("❌ Cancel")

                if save_edited:
                    if edited_amount <= 0:
                        st.warning("Amount must be greater than 0.")
                    elif not edited_reference_number:
                        st.warning("Reference Number is required.")
                    else:
                        try:
                            df.loc[st.session_state['editing_row_idx']] = {
                                "date": edited_date.strftime("%Y-%m-%d"),
                                "person": edited_person,
                                "amount": edited_amount,
                                "type": edit_data['type'],
                                "status": edited_transaction_status,
                                "description": edited_description,
                                "payment_method": edited_payment_method,
                                "reference_number": edited_reference_number,
                                "cheque_status": edited_cheque_status,
                                "transaction_status": edited_transaction_status
                            }
                            df.to_csv(CSV_FILE, index=False)
                            generate_html_summary(df)
                            git_push()
                            st.success("✅ Transaction updated successfully!")
                            st.session_state['editing_row_idx'] = None
                            st.session_state['temp_edit_data'] = {}
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving transaction: {e}")
                elif cancel_edit:
                    st.session_state['editing_row_idx'] = None
                    st.session_state['temp_edit_data'] = {}
                    st.rerun()

    except Exception as e:
        st.error(f"Error loading transaction history: {str(e)}")
        st.stop()

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
                    try:
                        if not os.path.exists(PEOPLE_FILE):
                            pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)
                        
                        df = pd.read_csv(PEOPLE_FILE)
                        if name.strip() in df['name'].values:
                            st.warning("Person already exists.")
                        else:
                            pd.DataFrame([[name.strip(), category]], columns=["name", "category"])\
                                .to_csv(PEOPLE_FILE, mode='a', header=False, index=False)
                            st.success(f"{name.strip()} added!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error saving person: {e}")

    try:
        if os.path.exists(PEOPLE_FILE):
            ppl = pd.read_csv(PEOPLE_FILE)
            if not ppl.empty:
                st.dataframe(ppl, use_container_width=True, hide_index=True)
                to_del = st.selectbox("Delete Person", ppl['name'])
                if st.button("Delete"):
                    try:
                        tx = pd.read_csv(CSV_FILE)
                        if to_del in tx['person'].values:
                            st.error("Cannot delete person with transactions.")
                        else:
                            ppl = ppl[ppl['name'] != to_del]
                            ppl.to_csv(PEOPLE_FILE, index=False)
                            st.success("Deleted.")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error deleting person: {e}")
            else:
                st.info("No people records yet.")
        else:
            st.info("People database not found. Add a new person to create it.")
    except Exception as e:
        st.error(f"Error managing people: {e}")

# ------------------ Sidebar: Balances ------------------
st.sidebar.header("Current Balances")
try:
    if os.path.exists(CSV_FILE):
        df_bal = pd.read_csv(CSV_FILE)
        if not df_bal.empty:
            df_bal['amount'] = pd.to_numeric(df_bal['amount'], errors='coerce').fillna(0.0)
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
        else:
            st.sidebar.info("No transactions yet.")
    else:
        st.sidebar.info("Transaction database not found. Add a transaction to create it.")
except Exception as e:
    st.sidebar.error(f"Error loading balances: {str(e)}")