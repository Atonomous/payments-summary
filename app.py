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
        'cheque_paid': payment_totals.loc['i_paid', 'cheque'] if 'cheque' in payment_totals.columns and 'i_paid' in payment_totals.index else 0,
        'net_balance': df[df['type'] == 'paid_to_me']['amount'].sum() - df[df['type'] == 'i_paid']['amount'].sum()
    }

    transactions = df.rename(columns={
        'date': 'Date', 'person': 'Person', 'type': 'Type',
        'transaction_status': 'Status', 'description': 'Description',
        'payment_method': 'Method', 'cheque_number': 'Cheque No.',
        'cheque_status': 'Cheque Status', 'receipt_number': 'Receipt No.'
    })
    transactions['Amount'] = transactions['amount']
    transactions['Type'] = transactions['Type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'})
    
    # Format cheque numbers properly
    transactions['Cheque No.'] = transactions['Cheque No.'].apply(
        lambda x: f"{int(x):,}" if pd.notna(x) and str(x).replace('.','').isdigit() else str(x)
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Payment Summary | Financial Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --primary: #4361ee;
            --secondary: #3f37c9;
            --success: #4cc9f0;
            --danger: #f72585;
            --warning: #f8961e;
            --info: #4895ef;
            --light: #f8f9fa;
            --dark: #212529;
            --white: #ffffff;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Poppins', sans-serif;
            background-color: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 30px 20px;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 1px solid #e0e0e0;
        }}
        
        .logo {{
            font-size: 28px;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 10px;
        }}
        
        .report-title {{
            font-size: 24px;
            color: var(--dark);
            margin-bottom: 10px;
        }}
        
        .report-date {{
            color: #666;
            font-size: 14px;
        }}
        
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .card {{
            background: var(--white);
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
        }}
        
        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }}
        
        .card-icon {{
            width: 40px;
            height: 40px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
        }}
        
        .received .card-icon {{ background-color: rgba(67, 97, 238, 0.1); color: var(--primary); }}
        .paid .card-icon {{ background-color: rgba(247, 37, 133, 0.1); color: var(--danger); }}
        .balance .card-icon {{ background-color: rgba(76, 201, 240, 0.1); color: var(--success); }}
        
        .card-title {{
            font-size: 16px;
            font-weight: 500;
            color: #666;
        }}
        
        .card-amount {{
            font-size: 24px;
            font-weight: 600;
            margin: 5px 0;
        }}
        
        .card-details {{
            font-size: 14px;
            color: #666;
            margin-top: 10px;
        }}
        
        .section-title {{
            font-size: 20px;
            font-weight: 600;
            margin: 30px 0 20px;
            color: var(--dark);
            display: flex;
            align-items: center;
        }}
        
        .section-title i {{
            margin-right: 10px;
            color: var(--primary);
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--white);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        }}
        
        th, td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #f0f0f0;
        }}
        
        th {{
            background-color: var(--primary);
            color: white;
            font-weight: 500;
            text-transform: uppercase;
            font-size: 13px;
            letter-spacing: 0.5px;
        }}
        
        tr:hover {{
            background-color: #f8f9fa;
        }}
        
        .status {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }}
        
        .completed {{ background-color: rgba(40, 167, 69, 0.1); color: #28a745; }}
        .pending {{ background-color: rgba(255, 193, 7, 0.1); color: #ffc107; }}
        .processing {{ background-color: rgba(13, 110, 253, 0.1); color: #0d6efd; }}
        .bounced {{ background-color: rgba(220, 53, 69, 0.1); color: #dc3545; }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 14px;
        }}
        
        @media (max-width: 768px) {{
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
            
            th, td {{
                padding: 10px 8px;
                font-size: 14px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">Payment Tracker</div>
            <h1 class="report-title">Payment Summary Report</h1>
            <div class="report-date">Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
        </header>
        
        <div class="summary-cards">
            <div class="card received">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-arrow-down"></i>
                    </div>
                    <div>
                        <div class="card-title">Total Received</div>
                        <div class="card-amount">Rs.{totals['total_received']:,.2f}</div>
                    </div>
                </div>
                <div class="card-details">
                    <div><i class="fas fa-coins"></i> Cash: Rs.{totals['cash_received']:,.2f}</div>
                    <div><i class="fas fa-money-check-alt"></i> Cheque: Rs.{totals['cheque_received']:,.2f}</div>
                    <div><i class="fas fa-clock"></i> Pending: Rs.{totals['pending_received']:,.2f}</div>
                </div>
            </div>
            
            <div class="card paid">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-arrow-up"></i>
                    </div>
                    <div>
                        <div class="card-title">Total Paid</div>
                        <div class="card-amount">Rs.{totals['total_paid']:,.2f}</div>
                    </div>
                </div>
                <div class="card-details">
                    <div><i class="fas fa-coins"></i> Cash: Rs.{totals['cash_paid']:,.2f}</div>
                    <div><i class="fas fa-money-check-alt"></i> Cheque: Rs.{totals['cheque_paid']:,.2f}</div>
                    <div><i class="fas fa-clock"></i> Pending: Rs.{totals['pending_paid']:,.2f}</div>
                </div>
            </div>
            
            <div class="card balance">
                <div class="card-header">
                    <div class="card-icon">
                        <i class="fas fa-balance-scale"></i>
                    </div>
                    <div>
                        <div class="card-title">Net Balance</div>
                        <div class="card-amount">Rs.{totals['net_balance']:,.2f}</div>
                    </div>
                </div>
                <div class="card-details">
                    <div><i class="fas fa-info-circle"></i> Received - Paid</div>
                    <div style="margin-top: 10px;">
                        {f'<span style="color: #28a745;"><i class="fas fa-check-circle"></i> Positive Balance</span>' if totals['net_balance'] >= 0 else '<span style="color: #dc3545;"><i class="fas fa-exclamation-circle"></i> Negative Balance</span>'}
                    </div>
                </div>
            </div>
        </div>
        
        <h2 class="section-title"><i class="fas fa-list"></i> All Transactions</h2>
        
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Person</th>
                    <th>Amount</th>
                    <th>Type</th>
                    <th>Method</th>
                    <th>Cheque No.</th>
                    <th>Receipt No.</th>
                    <th>Status</th>
                    <th>Cheque Status</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>"""

    for _, row in transactions.iterrows():
        status_class = row['Status'].lower().replace('/', '-')
        cheque_status_class = str(row['Cheque Status']).lower().replace(' ', '-').replace('/', '-')
        
        html += f"""
                <tr>
                    <td>{row['Date']}</td>
                    <td>{row['Person']}</td>
                    <td>Rs.{row['Amount']:,.2f}</td>
                    <td>{row['Type']}</td>
                    <td>{row['Method'].capitalize()}</td>
                    <td>{row.get('Cheque No.', '-')}</td>
                    <td>{row.get('Receipt No.', '-')}</td>
                    <td><span class="status {status_class}">{row['Status'].capitalize()}</span></td>
                    <td><span class="status {cheque_status_class}">{row.get('Cheque Status', '-')}</span></td>
                    <td>{row['Description'] if pd.notna(row['Description']) else '-'}</td>
                </tr>"""

    html += """
            </tbody>
        </table>
        
        <div class="footer">
            <p>This report was automatically generated by Payment Tracker System</p>
            <p><i class="far fa-copyright"></i> {datetime.now().year} All Rights Reserved</p>
        </div>
    </div>
</body>
</html>"""

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
    except Exception:
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
    
    try:
        df = pd.read_csv(CSV_FILE)
        
        # Check if DataFrame is empty
        if df.empty:
            st.info("No transactions recorded yet.")
            st.stop()
            
        # Ensure required columns exist
        required_columns = ['date', 'person', 'amount', 'type', 'payment_method',
                           'transaction_status', 'cheque_status', 'description']
        
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            st.error(f"Missing required columns in data: {', '.join(missing_cols)}")
            st.stop()
            
        # Convert amount to float and handle missing values
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['amount_display'] = df['amount'].apply(lambda x: f"Rs. {x:,.2f}")
        df['type_display'] = df['type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'})
        df['original_index'] = df.index
        
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
            'date': 'Date',
            'person': 'Person',
            'amount_display': 'Amount',
            'type_display': 'Type',
            'payment_method': 'Method',
            'cheque_number': 'Cheque No.',
            'receipt_number': 'Receipt No.',
            'transaction_status': 'Status',
            'cheque_status': 'Cheque Status',
            'description': 'Description'
        }
        
        st.dataframe(
            filtered_df[list(display_columns.keys())].rename(columns=display_columns),
            use_container_width=True,
            hide_index=True
        )

        # Edit Section - More visible with a clear header
        if not filtered_df.empty:
            st.markdown("---")
            st.subheader("Edit Transaction")
            
            edit_options = [f"ID: {idx} - {row['date']} - {row['person']} - Rs.{row['amount']:,.2f}" 
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

                    edited_receipt_number = ""
                    edited_cheque_number = ""
                    edited_cheque_status = ""

                    if edited_payment_method == "cash":
                        edited_receipt_number = st.text_input(
                            "Receipt Number", 
                            value=edit_data.get('receipt_number', ''), 
                            key='edit_receipt_number'
                        )
                    elif edited_payment_method == "cheque":
                        edited_cheque_number = st.text_input(
                            "Cheque Number", 
                            value=edit_data.get('cheque_number', ''), 
                            key='edit_cheque_number'
                        )
                        edited_cheque_status = st.selectbox(
                            "Cheque Status",
                            ["received/given", "processing", "bounced", "processing done"],
                            index=["received/given", "processing", "bounced", "processing done"].index(
                                edit_data.get('cheque_status', 'processing')
                            ),
                            key='edit_cheque_status'
                        )
                
                with col2_edit:
                    people_df = pd.read_csv(PEOPLE_FILE)
                    edited_person = st.selectbox(
                        "Select Person", 
                        people_df['name'].tolist(), 
                        index=people_df['name'].tolist().index(edit_data['person']), 
                        key='edit_person'
                    )
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
                    elif edited_payment_method == "cash" and not edited_receipt_number:
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
                        st.success("✅ Transaction updated successfully!")
                        st.session_state['editing_row_idx'] = None
                        st.session_state['temp_edit_data'] = {}
                        st.rerun()
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
        if not ppl.empty:
            st.dataframe(ppl, use_container_width=True, hide_index=True)
            to_del = st.selectbox("Delete Person", ppl['name'])
            if st.button("Delete"):
                tx = pd.read_csv(CSV_FILE)
                if to_del in tx['person'].values:
                    st.error("Cannot delete person with transactions.")
                else:
                    ppl = ppl[ppl['name'] != to_del]
                    ppl.to_csv(PEOPLE_FILE, index=False)
                    st.success("Deleted.")
                    st.rerun()
        else:
            st.info("No people records yet.")
    except Exception as e:
        st.error(f"Error managing people: {e}")

# ------------------ Sidebar: Balances ------------------
st.sidebar.header("Current Balances")
try:
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
except Exception as e:
    st.sidebar.error(f"Error loading balances: {str(e)}")
