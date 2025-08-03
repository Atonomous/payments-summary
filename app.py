import streamlit as st
import pandas as pd
from datetime import datetime
import os
from git import Repo, GitCommandError
import numpy as np
import uuid
from fpdf import FPDF
import json
import re
import shutil

# --- Constants ---
CSV_FILE = 'payments.csv'
PEOPLE_FILE = 'people.csv'
CLIENT_EXPENSES_FILE = 'client_expenses.csv'
GIT_REPO_PATH = '.'
GIT_REMOTE_NAME = 'origin'
GIT_BRANCH_NAME = 'main'
GITHUB_REPO_URL = "https://github.com/Autonomous/payments-summary"
REPORTS_DIR = 'reports'
DOCS_DIR = 'docs'
BACKUP_DIR = 'backups'
HTML_SUMMARY_FILE = os.path.join(DOCS_DIR, 'index.html')

# --- State Management ---
def init_state():
    """Initializes the session state variables if they don't already exist."""
    keys = [
        'selected_transaction_type', 'payment_method', 'editing_row_idx', 'selected_person', 'reset_add_form',
        'add_amount', 'add_date', 'add_reference_number', 'add_cheque_status', 'add_status', 'add_description',
        'temp_edit_data', 'invoice_person_name', 'invoice_type', 'invoice_start_date', 'invoice_end_date',
        'generated_invoice_pdf_path', 'show_download_button', 'view_person_filter', 'view_reference_number_search',
        'selected_client_for_expense', 'add_client_expense_amount', 'add_client_expense_date',
        'add_client_expense_category', 'add_client_expense_description', 'reset_client_expense_form',
        'add_client_expense_quantity', 'client_expense_ref_num_search', 'editing_client_expense_idx',
        'temp_edit_client_expense_data', 'selected_payment_uuid', 'selected_expense_uuid', 'payment_ref_num_search',
        'generated_pdf_data', 'report_type', 'generated_pdf_filename', 'use_date_range',
        'show_payment_delete_confirm', 'payment_to_delete_uuid', 'show_expense_delete_confirm', 'expense_to_delete_uuid'
    ]
    
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = None

    if st.session_state.reset_add_form is None:
        st.session_state.reset_add_form = False
    if st.session_state.reset_client_expense_form is None:
        st.session_state.reset_client_expense_form = False
    
    today = datetime.now().date()
    if 'view_payments_start_date' not in st.session_state:
        st.session_state.view_payments_start_date = today
    if 'view_payments_end_date' not in st.session_state:
        st.session_state.view_payments_end_date = today
    if 'view_expenses_start_date' not in st.session_state:
        st.session_state.view_expenses_start_date = today
    if 'view_expenses_end_date' not in st.session_state:
        st.session_state.view_expenses_end_date = today
    if 'invoice_start_date' not in st.session_state:
        st.session_state.invoice_start_date = today
    if 'invoice_end_date' not in st.session_state:
        st.session_state.invoice_end_date = today

# --- File & Git Management Functions ---
def sanitize_filename(filename):
    """Sanitizes a string to be a valid filename."""
    return re.sub(r'[\\/*?:"<>|]', '', filename)

def push_to_git():
    """Pushes the current state of the repo to the remote origin."""
    try:
        if not os.path.exists(os.path.join(GIT_REPO_PATH, '.git')):
            st.error("Git repository not found. Please initialize a git repo.")
            return

        repo = Repo(GIT_REPO_PATH)
        repo.git.add(A=True)
        repo.index.commit(f"Automated commit on {datetime.now()}")
        st.session_state.commit_hash = repo.head.commit.hexsha
        
        origin = repo.remote(GIT_REMOTE_NAME)
        if GIT_BRANCH_NAME not in [ref.name.split('/')[-1] for ref in origin.refs]:
            repo.git.push('--set-upstream', GIT_REMOTE_NAME, GIT_BRANCH_NAME)
        else:
            repo.git.push(GIT_REMOTE_NAME, GIT_BRANCH_NAME)
        
        st.success("Successfully pushed changes to Git.")
    except GitCommandError as e:
        st.error(f"Git command error: {e.stderr}. Check your Git configuration.")
    except Exception as e:
        st.error(f"An error occurred while pushing to Git: {e}")

def load_data(file_path, columns):
    """Loads a CSV file into a pandas DataFrame, creating it if it doesn't exist."""
    try:
        if not os.path.exists(file_path):
            df = pd.DataFrame(columns=columns)
            df.to_csv(file_path, index=False)
            return df
        # Added dtype for UUID to ensure it's always a string
        return pd.read_csv(file_path, dtype={'reference_number': str, 'uuid': str}, keep_default_na=False)
    except Exception as e:
        st.error(f"Error loading {file_path}: {e}")
        return pd.DataFrame(columns=columns)

def load_people():
    """Loads people data from CSV."""
    try:
        if not os.path.exists(PEOPLE_FILE):
            return pd.DataFrame(columns=['name', 'type'])
        df = pd.read_csv(PEOPLE_FILE)
        if 'category' in df.columns:
            df.rename(columns={'category': 'type'}, inplace=True)
        return df
    except Exception as e:
        st.error(f"Error loading {PEOPLE_FILE}: {e}")
        return pd.DataFrame(columns=['name', 'type'])

def backup_file(file_path):
    """Creates a timestamped backup of the given file."""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_name = os.path.basename(file_path)
    backup_path = os.path.join(BACKUP_DIR, f"{timestamp}_{file_name}.bak")
    
    try:
        shutil.copy(file_path, backup_path)
        st.info(f"Backup created at: {backup_path}")
    except Exception as e:
        st.warning(f"Could not create backup: {e}")


# --- Report Generation Functions ---
def generate_report_pdf(person_name, report_type, start_date, end_date, payments_df, client_expenses_df, use_date_range):
    """Generates a professional-looking PDF report."""
    
    payments_df['date'] = pd.to_datetime(payments_df['date'])
    client_expenses_df['date'] = pd.to_datetime(client_expenses_df['date'])
    
    person_payments = payments_df[(payments_df['person'] == person_name)].copy()
    person_expenses = client_expenses_df[(client_expenses_df['person'] == person_name)].copy()
    
    if use_date_range:
        person_payments = person_payments[
            (person_payments['date'].dt.date >= start_date) &
            (person_payments['date'].dt.date <= end_date)
        ]
        person_expenses = person_expenses[
            (person_expenses['date'].dt.date >= start_date) &
            (person_expenses['date'].dt.date <= end_date)
        ]
    
    pdf = FPDF()
    pdf.add_page()

    # --- Header ---
    pdf.set_font("Arial", 'B', 16)
    pdf.set_text_color(51, 102, 153) # Dark blue
    pdf.cell(0, 10, "Financial Report", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0, 0, 0)
    
    title_map = {
        'Bill': 'Bill (Client Expenses)',
        'Invoice': 'Invoice (Account Statement)',
        'Inquiry': 'Inquiry (My Payments to Client)'
    }
    
    pdf.cell(0, 10, txt=f"Report Type: {title_map[report_type]}", ln=True, align='L')
    pdf.cell(0, 10, txt=f"Client: {person_name}", ln=True, align='L')
    if use_date_range:
        pdf.cell(0, 10, txt=f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", ln=True, align='L')
    pdf.ln(10)

    # --- Payments Section ---
    if report_type in ['Invoice', 'Inquiry']:
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(51, 102, 153)
        pdf.cell(0, 10, "Payments (Debits: I Paid to Client)", ln=True, align='L')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 7, "Date", 1)
        pdf.cell(50, 7, "Reference No.", 1)
        pdf.cell(80, 7, "Description", 1)
        pdf.cell(30, 7, "Amount (Rs.)", 1, ln=True, align='R')
        
        pdf.set_font("Arial", '', 10)
        if not person_payments.empty:
            for _, row in person_payments.iterrows():
                pdf.cell(30, 7, row['date'].strftime('%Y-%m-%d'), 1)
                pdf.cell(50, 7, row['reference_number'], 1)
                pdf.cell(80, 7, row['description'], 1)
                pdf.cell(30, 7, f"{row['amount']:,.2f}", 1, ln=True, align='R')
        else:
            pdf.cell(0, 7, "No payments found for this period.", 1, ln=True)

        total_payments = person_payments['amount'].sum() if not person_payments.empty else 0
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Total Payments: Rs. {total_payments:,.2f}", ln=True, align='R')
        pdf.ln(5)

    # --- Client Expenses Section ---
    if report_type in ['Invoice', 'Bill']:
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(51, 102, 153)
        pdf.cell(0, 10, "Client Expenses (Credits: Client Spent)", ln=True, align='L')
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(30, 7, "Date", 1)
        pdf.cell(50, 7, "Reference No.", 1)
        pdf.cell(80, 7, "Description", 1)
        pdf.cell(30, 7, "Amount (Rs.)", 1, ln=True, align='R')
        
        pdf.set_font("Arial", '', 10)
        if not person_expenses.empty:
            for _, row in person_expenses.iterrows():
                pdf.cell(30, 7, row['date'].strftime('%Y-%m-%d'), 1)
                pdf.cell(50, 7, row['reference_number'], 1)
                pdf.cell(80, 7, row['description'], 1)
                pdf.cell(30, 7, f"{row['amount']:,.2f}", 1, ln=True, align='R')
        else:
            pdf.cell(0, 7, "No client expenses found for this period.", 1, ln=True)

        total_expenses = person_expenses['amount'].sum() if not person_expenses.empty else 0
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Total Client Expenses: Rs. {total_expenses:,.2f}", ln=True, align='R')
        pdf.ln(5)

    # --- Summary for Invoice ---
    if report_type == 'Invoice':
        pdf.ln(10)
        net_balance = total_payments - total_expenses
        pdf.set_font("Arial", 'B', 14)
        pdf.set_text_color(51, 102, 153)
        pdf.cell(0, 10, f"Net Balance: Rs. {net_balance:,.2f}", ln=True, align='L')
    
    return pdf.output(dest='S')

def generate_html_summary(payments_df, client_expenses_df):
    """Generates an HTML summary file for the docs folder."""
    try:
        payments_df['amount'] = pd.to_numeric(payments_df['amount'], errors='coerce').fillna(0)
        client_expenses_df['amount'] = pd.to_numeric(client_expenses_df['amount'], errors='coerce').fillna(0)

        total_received = payments_df[payments_df['type'] == 'i_received']['amount'].sum()
        total_paid = payments_df[payments_df['type'] == 'i_paid']['amount'].sum()
        total_client_expenses = client_expenses_df['amount'].sum()
        net_balance = total_received - (total_paid + total_client_expenses)

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Financial Summary</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }}
                .container {{ max-width: 800px; margin: auto; padding: 20px; background: #fff; border-radius: 8px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); }}
                h1 {{ color: #004080; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
                .metric {{ margin-top: 15px; padding: 15px; border-left: 5px solid #007bff; background: #e9f5ff; border-radius: 4px; }}
                .metric-title {{ font-weight: bold; color: #555; }}
                .metric-value {{ font-size: 1.5em; font-weight: normal; color: #000; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Financial Summary</h1>
                <div class="metric">
                    <div class="metric-title">Total Received</div>
                    <div class="metric-value">Rs. {total_received:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Total Paid (to clients)</div>
                    <div class="metric-value">Rs. {total_paid:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Total Client Expenses</div>
                    <div class="metric-value">Rs. {total_client_expenses:,.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-title">Net Balance</div>
                    <div class="metric-value">Rs. {net_balance:,.2f}</div>
                </div>
            </div>
        </body>
        </html>
        """
        if not os.path.exists(DOCS_DIR):
            os.makedirs(DOCS_DIR)
        
        with open(HTML_SUMMARY_FILE, "w") as f:
            f.write(html_content)
    except Exception as e:
        st.error(f"An error occurred while generating the HTML summary: {e}")

def update_balances_and_sidebar(payments_df, client_expenses_df):
    """Calculates and displays financial metrics in the sidebar."""
    st.sidebar.title("Financial Summary")
    st.sidebar.markdown(f"**[GitHub Repo]({GITHUB_REPO_URL})**")
    
    st.sidebar.link_button("See Payments Summary", f"{GITHUB_REPO_URL}/tree/{GIT_BRANCH_NAME}/{DOCS_DIR}/index.html")

    try:
        payments_df['amount'] = pd.to_numeric(payments_df['amount'], errors='coerce').fillna(0)
        client_expenses_df['amount'] = pd.to_numeric(client_expenses_df['amount'], errors='coerce').fillna(0)

        total_received = payments_df[payments_df['type'] == 'i_received']['amount'].sum()
        total_paid = payments_df[payments_df['type'] == 'i_paid']['amount'].sum()
        total_client_expenses = client_expenses_df['amount'].sum()
        net_balance = total_received - (total_paid + total_client_expenses)

        st.sidebar.metric("Total Received", f"Rs. {total_received:,.2f}")
        st.sidebar.metric("Total Paid (to clients)", f"Rs. {total_paid:,.2f}")
        st.sidebar.metric("Total Client Expenses", f"Rs. {total_client_expenses:,.2f}")
        st.sidebar.metric("Net Balance", f"Rs. {net_balance:,.2f}")

    except Exception as e:
        st.sidebar.error(f"Error loading balances: {str(e)}")

# --- Tab-specific Functions ---
def add_transaction_tab(payments_df, people_df):
    """Logic for the 'Add Transaction' tab."""
    st.header("Add New Transaction")
    with st.form(key='add_transaction_form', clear_on_submit=st.session_state.reset_add_form):
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.add_date = st.date_input("Date", datetime.now().date(), key='add_date_input')
            transaction_options = ['i_paid', 'i_received']
            st.session_state.selected_transaction_type = st.radio("Transaction Type", transaction_options, key='add_type_input')
            person_options = ['Select a person'] + people_df['name'].tolist()
            st.session_state.selected_person = st.selectbox("Select Person", person_options, key='add_person_input')
            payment_methods = ['cash', 'cheque', 'bank_transfer', 'online']
            st.session_state.payment_method = st.selectbox("Payment Method", payment_methods, key='add_payment_method_input')
        with col2:
            st.session_state.add_amount = st.number_input("Amount (Rs.)", min_value=0.0, format="%.2f", key='add_amount_input')
            st.session_state.add_reference_number = st.text_input("Reference Number", key='add_ref_num_input')
            if st.session_state.payment_method == 'cheque':
                cheque_status_options = ['processing done', 'not deposited']
                st.session_state.add_cheque_status = st.selectbox("Cheque Status", cheque_status_options, key='add_cheque_status_input')
            else:
                st.session_state.add_cheque_status = ''
            status_options = ['completed', 'pending']
            st.session_state.add_status = st.selectbox("Status", status_options, key='add_status_input')
            st.session_state.add_description = st.text_area("Description", key='add_description_input')

        submit_button = st.form_submit_button(label='Add Transaction')
        
        if submit_button:
            if not st.session_state.add_amount or st.session_state.add_amount <= 0:
                st.error("Please enter a valid amount.")
            elif st.session_state.selected_person == 'Select a person':
                st.error("Please select a person.")
            else:
                # Sanitize inputs
                sanitized_ref_num = re.sub(r'[^a-zA-Z0-9\s-]', '', st.session_state.add_reference_number)
                sanitized_desc = re.sub(r'[^a-zA-Z0-9\s-.]', '', st.session_state.add_description)

                new_uuid = str(uuid.uuid4())
                new_transaction = {
                    'date': st.session_state.add_date.isoformat(),
                    'person': st.session_state.selected_person,
                    'amount': st.session_state.add_amount,
                    'type': st.session_state.selected_transaction_type,
                    'status': st.session_state.add_status,
                    'description': sanitized_desc,
                    'payment_method': st.session_state.payment_method,
                    'reference_number': sanitized_ref_num,
                    'cheque_status': st.session_state.add_cheque_status,
                    'uuid': new_uuid
                }
                new_df = pd.DataFrame([new_transaction])
                
                # Backup before write
                backup_file(CSV_FILE)
                
                payments_df = pd.concat([payments_df, new_df], ignore_index=True)
                payments_df.to_csv(CSV_FILE, index=False)
                st.success("Transaction added successfully!")
                st.session_state.reset_add_form = True
                push_to_git()
                st.experimental_rerun()
        else:
            st.session_state.reset_add_form = False

def view_transactions_tab(payments_df):
    """Logic for the 'View Transactions' tab."""
    st.header("View and Manage Transactions")
    # Performance Note: Filtering is done client-side, which is efficient for
    # small to medium datasets. For very large files, a database backend would be
    # more appropriate.
    with st.container():
        col1, col2, col3 = st.columns(3)
        with col1:
            person_filter_options = ['All'] + payments_df['person'].unique().tolist()
            st.session_state.view_person_filter = st.selectbox("Filter by Person", person_filter_options, key='view_person_filter_input')
        with col2:
            st.session_state.view_payments_start_date = st.date_input("Start Date", value=st.session_state.view_payments_start_date, key='view_payments_start_date_input')
        with col3:
            st.session_state.view_payments_end_date = st.date_input("End Date", value=st.session_state.view_payments_end_date, key='view_payments_end_date_input')
    
    st.session_state.payment_ref_num_search = st.text_input("Search by Reference Number", key='payment_ref_num_search_input')

    filtered_payments = payments_df.copy()
    if st.session_state.view_person_filter != 'All':
        filtered_payments = filtered_payments[filtered_payments['person'] == st.session_state.view_person_filter]
    if st.session_state.payment_ref_num_search:
        search_term = re.sub(r'[^a-zA-Z0-9\s-]', '', st.session_state.payment_ref_num_search)
        filtered_payments = filtered_payments[filtered_payments['reference_number'].str.contains(search_term, case=False, na=False)]
    
    filtered_payments['date'] = pd.to_datetime(filtered_payments['date'])
    start_date = pd.to_datetime(st.session_state.view_payments_start_date)
    end_date = pd.to_datetime(st.session_state.view_payments_end_date)
    filtered_payments = filtered_payments[
        (filtered_payments['date'].dt.date >= start_date.date()) &
        (filtered_payments['date'].dt.date <= end_date.date())
    ]
    
    if not filtered_payments.empty:
        st.dataframe(filtered_payments, use_container_width=True, hide_index=True)
        payment_options = [''] + [
            f"Date: {row['date'].strftime('%Y-%m-%d')} | Person: {row['person']} | Amount: {row['amount']:,.2f} | Ref: {row['reference_number']}"
            for _, row in filtered_payments.iterrows()
        ]
        selected_option = st.selectbox("Select Transaction to Edit/Delete", payment_options, key='payment_selector')

        if selected_option:
            selected_row = filtered_payments.iloc[payment_options.index(selected_option) - 1]
            index_to_edit = payments_df[payments_df['uuid'] == selected_row['uuid']].index[0]
            st.subheader(f"Editing Transaction: {selected_row['uuid']}")
            with st.form(key=f'edit_form'):
                col1, col2 = st.columns(2)
                with col1:
                    st.session_state.temp_edit_data = {}
                    st.session_state.temp_edit_data['date'] = st.date_input("Date", pd.to_datetime(selected_row['date']).date(), key=f'edit_date')
                    st.session_state.temp_edit_data['type'] = st.radio("Transaction Type", ['i_paid', 'i_received'], index=0 if selected_row['type'] == 'i_paid' else 1, key=f'edit_type')
                with col2:
                    st.session_state.temp_edit_data['amount'] = st.number_input("Amount", min_value=0.0, value=float(selected_row['amount']), format="%.2f", key=f'edit_amount')
                    st.session_state.temp_edit_data['status'] = st.selectbox("Status", ['completed', 'pending'], index=0 if selected_row['status'] == 'completed' else 1, key=f'edit_status')
                st.session_state.temp_edit_data['description'] = st.text_area("Description", value=selected_row['description'], key=f'edit_description')
                
                edit_col1, edit_col2 = st.columns(2)
                with edit_col1:
                    if st.form_submit_button("Save Changes"):
                        for key, value in st.session_state.temp_edit_data.items():
                            payments_df.loc[index_to_edit, key] = value
                        backup_file(CSV_FILE)
                        payments_df.to_csv(CSV_FILE, index=False)
                        st.success("Transaction updated successfully!")
                        push_to_git()
                        st.experimental_rerun()
                with edit_col2:
                    if st.form_submit_button("Delete Transaction"):
                        st.session_state.show_payment_delete_confirm = True
                        st.session_state.payment_to_delete_uuid = selected_row['uuid']
            
            if st.session_state.show_payment_delete_confirm and st.session_state.payment_to_delete_uuid == selected_row['uuid']:
                st.warning("Are you sure you want to delete this transaction? This action cannot be undone.")
                if st.button("Confirm Deletion", key='confirm_delete_payment'):
                    backup_file(CSV_FILE)
                    payments_df.drop(index_to_edit, inplace=True)
                    payments_df.to_csv(CSV_FILE, index=False)
                    st.success("Transaction deleted successfully!")
                    st.session_state.show_payment_delete_confirm = False
                    st.session_state.payment_to_delete_uuid = None
                    push_to_git()
                    st.experimental_rerun()
                if st.button("Cancel", key='cancel_delete_payment'):
                    st.session_state.show_payment_delete_confirm = False
                    st.session_state.payment_to_delete_uuid = None
                    st.experimental_rerun()

    else:
        st.info("No payments found for the selected filters.")

def client_expenses_tab(client_expenses_df, people_df):
    """Logic for the 'Client Expenses' tab."""
    st.header("Manage Client Expenses")
    
    # Add new client expense form
    with st.form(key='add_client_expense_form_tab3', clear_on_submit=st.session_state.reset_client_expense_form):
        st.subheader("Add New Client Expense")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.add_client_expense_date = st.date_input("Date", datetime.now().date(), key='add_client_expense_date_input_tab3')
            client_options = ['Select a client'] + people_df[people_df['type'] == 'client']['name'].tolist()
            st.session_state.selected_client_for_expense = st.selectbox("Select Client", client_options, key='add_client_expense_person_input_tab3')
        with col2:
            st.session_state.add_client_expense_amount = st.number_input("Amount (Rs.)", min_value=0.0, format="%.2f", key='add_client_expense_amount_input_tab3')
            st.session_state.add_client_expense_quantity = st.number_input("Quantity", min_value=1.0, format="%f", key='add_client_expense_quantity_input_tab3')
        
        st.session_state.add_client_expense_category = st.text_input("Category", key='add_client_expense_category_input_tab3')
        st.session_state.client_expense_ref_num_search = st.text_input("Reference Number (Optional)", key='add_client_expense_ref_num_input_tab3')
        st.session_state.add_client_expense_description = st.text_area("Description", key='add_client_expense_description_input_tab3')
        
        submit_client_expense_button = st.form_submit_button(label='Add Client Expense')
        
        if submit_client_expense_button:
            if not st.session_state.add_client_expense_amount or st.session_state.add_client_expense_amount <= 0:
                st.error("Please enter a valid amount.")
            elif st.session_state.selected_client_for_expense == 'Select a client':
                st.error("Please select a client.")
            else:
                # Sanitize inputs
                sanitized_ref_num = re.sub(r'[^a-zA-Z0-9\s-]', '', st.session_state.client_expense_ref_num_search)
                sanitized_desc = re.sub(r'[^a-zA-Z0-9\s-.]', '', st.session_state.add_client_expense_description)

                new_uuid = str(uuid.uuid4())
                new_expense = {
                    'reference_number': sanitized_ref_num,
                    'date': st.session_state.add_client_expense_date.isoformat(),
                    'person': st.session_state.selected_client_for_expense,
                    'category': st.session_state.add_client_expense_category,
                    'amount': st.session_state.add_client_expense_amount,
                    'quantity': st.session_state.add_client_expense_quantity,
                    'description': sanitized_desc,
                    'uuid': new_uuid
                }
                new_df = pd.DataFrame([new_expense])
                
                # Backup before write
                backup_file(CLIENT_EXPENSES_FILE)

                client_expenses_df = pd.concat([client_expenses_df, new_df], ignore_index=True)
                client_expenses_df.to_csv(CLIENT_EXPENSES_FILE, index=False)
                st.success("Client expense added successfully!")
                st.session_state.reset_client_expense_form = True
                push_to_git()
                st.experimental_rerun()
        else:
            st.session_state.reset_client_expense_form = False
    
    # View and manage client expenses
    st.subheader("View All Client Expenses")
    with st.container():
        col1, col2, col3 = st.columns(3)
        with col1:
            client_expense_filter_options = ['All'] + client_expenses_df['person'].unique().tolist()
            st.session_state.view_person_filter_client_expense = st.selectbox("Filter by Client", client_expense_filter_options, key='view_person_filter_client_expense_input')
        with col2:
            st.session_state.view_expenses_start_date = st.date_input("Start Date", value=st.session_state.view_expenses_start_date, key='view_expenses_start_date_input')
        with col3:
            st.session_state.view_expenses_end_date = st.date_input("End Date", value=st.session_state.view_expenses_end_date, key='view_expenses_end_date_input')
    
    st.session_state.client_expense_ref_num_search = st.text_input("Search by Reference Number", key='client_expense_ref_num_search_input_view')
        
    filtered_expenses = client_expenses_df.copy()
    if st.session_state.view_person_filter_client_expense != 'All':
        filtered_expenses = filtered_expenses[filtered_expenses['person'] == st.session_state.view_person_filter_client_expense]
    if st.session_state.client_expense_ref_num_search:
        search_term = re.sub(r'[^a-zA-Z0-9\s-]', '', st.session_state.client_expense_ref_num_search)
        filtered_expenses = filtered_expenses[filtered_expenses['reference_number'].str.contains(search_term, case=False, na=False)]
    
    filtered_expenses['date'] = pd.to_datetime(filtered_expenses['date'])
    start_date = pd.to_datetime(st.session_state.view_expenses_start_date)
    end_date = pd.to_datetime(st.session_state.view_expenses_end_date)
    filtered_expenses = filtered_expenses[
        (filtered_expenses['date'].dt.date >= start_date.date()) &
        (filtered_expenses['date'].dt.date <= end_date.date())
    ]

    if not filtered_expenses.empty:
        st.dataframe(filtered_expenses, use_container_width=True, hide_index=True)
        expense_options = [''] + [
            f"Date: {row['date'].strftime('%Y-%m-%d')} | Person: {row['person']} | Amount: {row['amount']:,.2f} | Desc: {row['description']}"
            for _, row in filtered_expenses.iterrows()
        ]
        selected_option = st.selectbox("Select Expense to Edit/Delete", expense_options, key='expense_selector')

        if selected_option:
            selected_row = filtered_expenses.iloc[expense_options.index(selected_option) - 1]
            index_to_edit = client_expenses_df[client_expenses_df['uuid'] == selected_row['uuid']].index[0]
            st.subheader(f"Editing Client Expense: {selected_row['uuid']}")
            with st.form(key=f'edit_client_expense_form'):
                col1, col2 = st.columns(2)
                with col1:
                    st.session_state.temp_edit_client_expense_data = {}
                    st.session_state.temp_edit_client_expense_data['date'] = st.date_input("Date", pd.to_datetime(selected_row['date']).date(), key=f'edit_client_expense_date')
                    st.session_state.temp_edit_client_expense_data['category'] = st.text_input("Category", value=selected_row['category'], key=f'edit_client_expense_category')
                with col2:
                    st.session_state.temp_edit_client_expense_data['amount'] = st.number_input("Amount", min_value=0.0, value=float(selected_row['amount']), format="%.2f", key=f'edit_client_expense_amount')
                    st.session_state.temp_edit_client_expense_data['quantity'] = st.number_input("Quantity", min_value=1.0, value=float(selected_row['quantity']), format="%f", key=f'edit_client_expense_quantity')
                st.session_state.temp_edit_client_expense_data['description'] = st.text_area("Description", value=selected_row['description'], key=f'edit_client_expense_description')
                
                edit_col1, edit_col2 = st.columns(2)
                with edit_col1:
                    if st.form_submit_button("Save Changes"):
                        for key, value in st.session_state.temp_edit_client_expense_data.items():
                            client_expenses_df.loc[index_to_edit, key] = value
                        backup_file(CLIENT_EXPENSES_FILE)
                        client_expenses_df.to_csv(CLIENT_EXPENSES_FILE, index=False)
                        st.success("Client expense updated successfully!")
                        push_to_git()
                        st.experimental_rerun()
                with edit_col2:
                    if st.form_submit_button("Delete Client Expense"):
                        st.session_state.show_expense_delete_confirm = True
                        st.session_state.expense_to_delete_uuid = selected_row['uuid']
            
            if st.session_state.show_expense_delete_confirm and st.session_state.expense_to_delete_uuid == selected_row['uuid']:
                st.warning("Are you sure you want to delete this expense? This action cannot be undone.")
                if st.button("Confirm Deletion", key='confirm_delete_expense'):
                    backup_file(CLIENT_EXPENSES_FILE)
                    client_expenses_df.drop(index_to_edit, inplace=True)
                    client_expenses_df.to_csv(CLIENT_EXPENSES_FILE, index=False)
                    st.success("Client expense deleted successfully!")
                    st.session_state.show_expense_delete_confirm = False
                    st.session_state.expense_to_delete_uuid = None
                    push_to_git()
                    st.experimental_rerun()
                if st.button("Cancel", key='cancel_delete_expense'):
                    st.session_state.show_expense_delete_confirm = False
                    st.session_state.expense_to_delete_uuid = None
                    st.experimental_rerun()
    else:
        st.info("No client expenses found for the selected filters.")

def invoice_report_tab(payments_df, client_expenses_df, people_df):
    """Logic for the 'Invoice/Report' tab."""
    st.header("Generate Invoice / Report")
    with st.form(key='generate_invoice_form'):
        col1, col2 = st.columns(2)
        with col1:
            client_options = ['Select a client'] + people_df[people_df['type'] == 'client']['name'].tolist()
            st.session_state.invoice_person_name = st.selectbox("Select Client", client_options, key='invoice_person_name_input')
        with col2:
            report_options_with_summary = {
                'Bill': 'Bill (Client Expenses only)',
                'Invoice': 'Invoice (Full Account Statement)',
                'Inquiry': 'Inquiry (My Payments to Client)'
            }
            report_display_options = ['Select a report type'] + list(report_options_with_summary.values())
            selected_report_display = st.selectbox("Select Report Type", report_display_options, key='report_type_input')
            
            st.session_state.report_type = next((key for key, value in report_options_with_summary.items() if value == selected_report_display), None)

        use_date_range = st.checkbox("Use Date Range Filter", value=False, key='use_date_range_checkbox')
        
        if use_date_range:
            col3, col4 = st.columns(2)
            with col3:
                st.session_state.invoice_start_date = st.date_input("Start Date", value=st.session_state.invoice_start_date or datetime.now().date(), key='invoice_start_date_input')
            with col4:
                st.session_state.invoice_end_date = st.date_input("End Date", value=st.session_state.invoice_end_date or datetime.now().date(), key='invoice_end_date_input')
        
        generate_button = st.form_submit_button("Generate Report")

    if st.session_state.invoice_person_name != 'Select a client' and st.session_state.report_type is not None:
        st.subheader("Report Preview")
        temp_payments_df = payments_df.copy()
        temp_expenses_df = client_expenses_df.copy()
        
        # Ensure date columns are datetime objects before filtering
        temp_payments_df['date'] = pd.to_datetime(temp_payments_df['date'])
        temp_expenses_df['date'] = pd.to_datetime(temp_expenses_df['date'])
        
        if use_date_range:
            person_payments = temp_payments_df[(temp_payments_df['person'] == st.session_state.invoice_person_name) & (temp_payments_df['date'].dt.date >= st.session_state.invoice_start_date) & (temp_payments_df['date'].dt.date <= st.session_state.invoice_end_date)]
            person_expenses = temp_expenses_df[(temp_expenses_df['person'] == st.session_state.invoice_person_name) & (temp_expenses_df['date'].dt.date >= st.session_state.invoice_start_date) & (temp_expenses_df['date'].dt.date <= st.session_state.invoice_end_date)]
        else:
            person_payments = temp_payments_df[temp_payments_df['person'] == st.session_state.invoice_person_name]
            person_expenses = temp_expenses_df[temp_expenses_df['person'] == st.session_state.invoice_person_name]
            
        if st.session_state.report_type in ['Invoice', 'Inquiry']:
            st.markdown("---")
            st.subheader("Payments (I Paid to Client)")
            if not person_payments.empty:
                st.dataframe(person_payments, use_container_width=True, hide_index=True)
            else:
                st.info("No payments found for this period.")

        if st.session_state.report_type in ['Invoice', 'Bill']:
            st.markdown("---")
            st.subheader("Client Expenses (Client Spent)")
            if not person_expenses.empty:
                st.dataframe(person_expenses, use_container_width=True, hide_index=True)
            else:
                st.info("No client expenses found for this period.")

        if st.session_state.report_type == 'Invoice':
            st.markdown("---")
            total_payments = person_payments['amount'].sum() if not person_payments.empty else 0
            total_expenses = person_expenses['amount'].sum() if not person_expenses.empty else 0
            net_balance = total_payments - total_expenses
            st.subheader(f"Total Payments: Rs. {total_payments:,.2f}")
            st.subheader(f"Total Client Expenses: Rs. {total_expenses:,.2f}")
            st.subheader(f"Net Balance: Rs. {net_balance:,.2f}")

    if generate_button:
        if st.session_state.invoice_person_name == 'Select a client':
            st.error("Please select a client to generate the report.")
        elif st.session_state.report_type is None:
            st.error("Please select a report type.")
        else:
            with st.spinner("Generating PDF..."):
                pdf_data = generate_report_pdf(
                    st.session_state.invoice_person_name,
                    st.session_state.report_type,
                    st.session_state.invoice_start_date,
                    st.session_state.invoice_end_date,
                    payments_df,
                    client_expenses_df,
                    use_date_range
                )
                
                # Create directories if they don't exist
                report_folder = os.path.join(REPORTS_DIR, st.session_state.report_type.lower())
                if not os.path.exists(report_folder):
                    os.makedirs(report_folder)
                
                # Save the file to the new folder structure
                sanitized_person_name = sanitize_filename(st.session_state.invoice_person_name)
                file_name = f"{st.session_state.report_type.lower()}_{sanitized_person_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                file_path = os.path.join(report_folder, file_name)
                with open(file_path, "wb") as f:
                    f.write(pdf_data)

                st.session_state.generated_pdf_data = bytes(pdf_data)
                st.session_state.generated_pdf_filename = file_name
                st.success(f"Report generated and saved to '{file_path}'!")
                push_to_git()
    
    if st.session_state.generated_pdf_data:
        st.download_button(
            label=f"Download {st.session_state.report_type} PDF",
            data=st.session_state.generated_pdf_data,
            file_name=st.session_state.generated_pdf_filename,
            mime="application/pdf",
            key="download_button_final"
        )

# --- Main App ---
def main():
    """Main Streamlit application function."""
    st.set_page_config(page_title="Payment & Expense Tracker", layout="wide")
    st.title("Payment & Expense Tracker")

    init_state()
    
    # Load dataframes once
    payments_df = load_data(CSV_FILE, ['date', 'person', 'amount', 'type', 'status', 'description', 'payment_method', 'reference_number', 'cheque_status', 'uuid'])
    people_df = load_people()
    client_expenses_df = load_data(CLIENT_EXPENSES_FILE, ['reference_number', 'date', 'person', 'category', 'amount', 'quantity', 'description', 'uuid'])
    
    if payments_df is None or people_df is None or client_expenses_df is None:
        st.error("Application could not start due to file errors.")
        return

    # Update HTML summary and sidebar on every run
    generate_html_summary(payments_df, client_expenses_df)
    update_balances_and_sidebar(payments_df, client_expenses_df)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Git Status")
    if 'commit_hash' in st.session_state and st.session_state.commit_hash:
        st.sidebar.markdown(f"Latest Commit: `{st.session_state.commit_hash[:7]}`")

    tab1, tab2, tab3, tab4 = st.tabs(["Add Transaction", "View Transactions", "Client Expenses", "Invoice/Report"])

    with tab1:
        add_transaction_tab(payments_df, people_df)

    with tab2:
        view_transactions_tab(payments_df)

    with tab3:
        client_expenses_tab(client_expenses_df, people_df)

    with tab4:
        invoice_report_tab(payments_df, client_expenses_df, people_df)

if __name__ == "__main__":
    main()
