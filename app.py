import streamlit as st
import pandas as pd
from datetime import datetime
import os
from git import Repo
import numpy as np
import uuid
from fpdf import FPDF
import base64
import json

# --- File Paths and Repository ---
CSV_FILE = 'payments.csv'
CLIENT_EXPENSES_FILE = 'client_expenses.csv'
PEOPLE_FILE = 'people.csv'
COMMIT_MESSAGE = "Updated data via Streamlit app"
REPO_PATH = '.' # Assuming the repo is in the same directory as the script

# --- FPDF Class for PDF Report Generation ---
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_font('Helvetica', '', 12)
        self.title_text = ''
    
    def set_title_text(self, text):
        self.title_text = text

    def header(self):
        self.set_font('Helvetica', 'B', 16)
        self.cell(0, 10, 'Transaction Report', 0, 1, 'C')
        self.set_font('Helvetica', '', 12)
        self.cell(0, 10, self.title_text, 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 6, title, 0, 1, 'L')
        self.ln(4)

    def add_table_with_summary(self, dataframe, title, amount_col, summary_text=""):
        self.chapter_title(title)
        
        # Handle cases where dataframe might be empty after filtering
        if dataframe.empty:
            self.cell(0, 10, 'No data available for this section.', 0, 1, 'C')
            self.ln(5)
            return

        # Prepare data for display
        display_df = dataframe.copy()
        display_df[amount_col] = display_df[amount_col].apply(lambda x: f"Rs. {x:,.2f}")
        
        # Table Header
        self.set_font('Helvetica', 'B', 10)
        col_width = self.w / (len(display_df.columns) + 1)
        for col in display_df.columns:
            self.cell(col_width, 7, str(col).replace('_', ' ').title(), 1, 0, 'C')
        self.ln()

        # Table Rows
        self.set_font('Helvetica', '', 10)
        for index, row in display_df.iterrows():
            for item in row:
                self.cell(col_width, 6, str(item), 1, 0, 'L')
            self.ln()
        
        # Summary
        if summary_text:
            self.ln(5)
            self.set_font('Helvetica', 'B', 12)
            self.multi_cell(0, 6, summary_text)
            self.ln(5)

def create_full_report_pdf(person_name, start_date, end_date):
    # Load and filter payments
    df_payments = load_data(CSV_FILE)
    df_payments['date'] = pd.to_datetime(df_payments['date'])
    df_payments_filtered = df_payments[(df_payments['person'] == person_name) & 
                                       (df_payments['date'] >= pd.to_datetime(start_date)) & 
                                       (df_payments['date'] <= pd.to_datetime(end_date))].copy()
    df_payments_filtered['amount'] = pd.to_numeric(df_payments_filtered['amount'], errors='coerce').fillna(0)

    # Load and filter client expenses
    df_client_expenses = load_data(CLIENT_EXPENSES_FILE)
    df_client_expenses['expense_date'] = pd.to_datetime(df_client_expenses['expense_date'])
    df_expenses_filtered = df_client_expenses[(df_client_expenses['expense_person'] == person_name) & 
                                              (df_client_expenses['expense_date'] >= pd.to_datetime(start_date)) & 
                                              (df_client_expenses['expense_date'] <= pd.to_datetime(end_date))].copy()
    df_expenses_filtered['expense_amount'] = pd.to_numeric(df_expenses_filtered['expense_amount'], errors='coerce').fillna(0)
    df_expenses_filtered['expense_quantity'] = pd.to_numeric(df_expenses_filtered['expense_quantity'], errors='coerce').fillna(1.0)


    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.set_title_text(f"for {person_name} from {start_date} to {end_date}")
    pdf.add_page()

    # Payments Report
    payments_received_df = df_payments_filtered[df_payments_filtered['type'] == 'paid_to_me'][['date', 'amount', 'payment_method', 'reference_number', 'description']]
    total_received = payments_received_df['amount'].sum()
    payments_received_df.rename(columns={'date': 'Date', 'amount': 'Amount', 'payment_method': 'Method', 'reference_number': 'Ref. No.', 'description': 'Description'}, inplace=True)
    pdf.add_table_with_summary(payments_received_df, "Payments Received (Credit)", "Amount", f"Total Payments Received: Rs. {total_received:,.2f}")
    
    # Payments Made Report
    payments_made_df = df_payments_filtered[df_payments_filtered['type'] == 'i_paid'][['date', 'amount', 'payment_method', 'reference_number', 'description']]
    total_paid = payments_made_df['amount'].sum()
    payments_made_df.rename(columns={'date': 'Date', 'amount': 'Amount', 'payment_method': 'Method', 'reference_number': 'Ref. No.', 'description': 'Description'}, inplace=True)
    pdf.add_table_with_summary(payments_made_df, "Payments Made (Debit)", "Amount", f"Total Payments Made: Rs. {total_paid:,.2f}")

    # Client Expenses Report
    expenses_df = df_expenses_filtered[['expense_date', 'expense_amount', 'expense_category', 'expense_quantity', 'expense_description']]
    total_expenses = (df_expenses_filtered['expense_amount'] * df_expenses_filtered['expense_quantity']).sum()
    expenses_df.rename(columns={'expense_date': 'Date', 'expense_amount': 'Amount', 'expense_category': 'Category', 'expense_quantity': 'Qty.', 'expense_description': 'Description'}, inplace=True)
    pdf.add_table_with_summary(expenses_df, "Client Expenses (Debit)", "Amount", f"Total Client Expenses: Rs. {total_expenses:,.2f}")

    # Final Summary
    pdf.ln(10)
    pdf.set_font('Helvetica', 'B', 14)
    net_balance = total_received - total_paid - total_expenses
    pdf.multi_cell(0, 10, f"Net Balance: Rs. {net_balance:,.2f}")
    
    pdf_bytes = pdf.output(dest='S').encode('latin1')
    return pdf_bytes

# --- Helper Functions ---
def get_repo():
    try:
        repo = Repo(REPO_PATH)
        return repo
    except:
        return None

def add_and_commit(files, message):
    repo = get_repo()
    if repo:
        try:
            repo.index.add(files)
            repo.index.commit(message)
            return True, None
        except Exception as e:
            return False, f"Error committing to repository: {e}"
    return False, "Git repository not found. Please initialize a repository in this folder."

def init_state():
    keys = [
        'selected_transaction_type', 'payment_method', 'editing_row_idx', 'selected_person', 'reset_add_form',
        'add_amount', 'add_date', 'add_reference_number', 'add_cheque_status', 'add_status', 'add_description',
        'temp_edit_data', 'invoice_person_name', 'invoice_type', 'invoice_start_date', 'invoice_end_date',
        'generated_invoice_pdf_path', 'show_download_button', 'view_person_filter', 'view_reference_number_search',
        'selected_client_for_expense', 'add_client_expense_amount', 'add_client_expense_date',
        'add_client_expense_category', 'add_client_expense_description', 'reset_client_expense_form',
        'add_client_expense_quantity', 'report_person_name', 'report_start_date', 'report_end_date',
        'editing_expense_row_idx', 'temp_edit_expense_data', 'view_expense_person_filter', 
        'view_expense_reference_number_search', 'view_payment_method_filter', 'view_start_date_filter', 'view_end_date_filter',
        'view_expense_category_filter', 'view_expense_start_date_filter', 'view_expense_end_date_filter',
        'add_cheque_status'
    ]
    today = datetime.today().date()
    start_of_year = today.replace(month=1, day=1)
    
    defaults = {
        'selected_transaction_type': 'Paid to Me', 'payment_method': 'cash', 'editing_row_idx': None,
        'selected_person': "Select...", 'reset_add_form': False, 'add_amount': None, 'add_date': None,
        'add_reference_number': '', 'add_cheque_status': 'N/A', 'add_status': 'completed',
        'add_description': '', 'temp_edit_data': {}, 'invoice_person_name': 'Select...',
        'invoice_type': 'payments_paid', 'invoice_start_date': start_of_year,
        'invoice_end_date': today, 'generated_invoice_pdf_path': None, 'show_download_button': False,
        'view_person_filter': 'All', 'view_reference_number_search': '', 'selected_client_for_expense': 'Select...',
        'add_client_expense_amount': 0.0, 'add_client_expense_date': today,
        'add_client_expense_category': 'General', 'add_client_expense_description': '',
        'reset_client_expense_form': False, 'add_client_expense_quantity': 1.0,
        'report_person_name': 'Select...', 'report_start_date': start_of_year,
        'report_end_date': today,
        'editing_expense_row_idx': None, 'temp_edit_expense_data': {},
        'view_expense_person_filter': 'All', 'view_expense_reference_number_search': '',
        'view_payment_method_filter': 'All', 'view_start_date_filter': start_of_year, 'view_end_date_filter': today,
        'view_expense_category_filter': 'All', 'view_expense_start_date_filter': start_of_year, 'view_expense_end_date_filter': today
    }
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

def load_data(file_path):
    if not os.path.exists(file_path):
        return pd.DataFrame()
    df = pd.read_csv(file_path, keep_default_na=False)

    # Robust UUID Management
    if 'uuid' not in df.columns:
        df['uuid'] = '' # Create a new column if it doesn't exist

    # Reassign UUIDs to missing entries and check for duplicates
    missing_uuids = df['uuid'].apply(lambda x: str(x).strip() == '' or pd.isna(x)).sum()
    if missing_uuids > 0:
        df.loc[df['uuid'].apply(lambda x: str(x).strip() == '' or pd.isna(x)), 'uuid'] = [str(uuid.uuid4()) for _ in range(missing_uuids)]
        st.warning(f"Found and assigned {missing_uuids} new UUIDs to records in {file_path}. Please re-add these files to git and then commit them.")

    if not df.empty and df['uuid'].duplicated().any():
        st.error(f"Duplicate UUIDs found in {file_path}. This may cause editing/deleting issues. Please fix the source CSV file.")

    return df

def save_data(df, file_path):
    df.to_csv(file_path, index=False)

def add_payment(df, person, amount, type, status, description, payment_method, reference_number, cheque_status, date):
    new_row = {
        'date': date.strftime('%Y-%m-%d'),
        'person': person,
        'amount': amount,
        'type': type,
        'status': status,
        'description': description,
        'payment_method': payment_method,
        'reference_number': reference_number,
        'cheque_status': cheque_status,
        'transaction_status': 'completed',
        'uuid': str(uuid.uuid4())
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

def update_payment(df, uuid_to_update, person, amount, type, status, description, payment_method, reference_number, cheque_status, date):
    idx = df[df['uuid'] == uuid_to_update].index[0]
    df.loc[idx, 'date'] = date.strftime('%Y-%m-%d')
    df.loc[idx, 'person'] = person
    df.loc[idx, 'amount'] = amount
    df.loc[idx, 'type'] = type
    df.loc[idx, 'status'] = status
    df.loc[idx, 'description'] = description
    df.loc[idx, 'payment_method'] = payment_method
    df.loc[idx, 'reference_number'] = reference_number
    df.loc[idx, 'cheque_status'] = cheque_status
    return df

def delete_payment(df, uuid_to_delete):
    return df[df['uuid'] != uuid_to_delete].reset_index(drop=True)

def add_client_expense(df, person, amount, category, description, quantity, date):
    new_row = {
        'original_transaction_ref_num': '',
        'expense_date': date.strftime('%Y-%m-%d'),
        'expense_person': person,
        'expense_category': category,
        'expense_amount': amount,
        'expense_quantity': quantity,
        'expense_description': description,
        'uuid': str(uuid.uuid4())
    }
    return pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

def update_client_expense(df, uuid_to_update, person, amount, category, description, quantity, date):
    idx = df[df['uuid'] == uuid_to_update].index[0]
    df.loc[idx, 'expense_date'] = date.strftime('%Y-%m-%d')
    df.loc[idx, 'expense_person'] = person
    df.loc[idx, 'expense_amount'] = amount
    df.loc[idx, 'expense_category'] = category
    df.loc[idx, 'expense_description'] = description
    df.loc[idx, 'expense_quantity'] = quantity
    return df

def delete_client_expense(df, uuid_to_delete):
    return df[df['uuid'] != uuid_to_delete].reset_index(drop=True)

# --- App Layout and Logic ---
st.set_page_config(layout="wide", page_title="Finance Manager", page_icon="💰")
st.title("💰 Finance Manager")

init_state()

# --- Load Data and Ensure UUIDs Exist ---
try:
    df_payments = load_data(CSV_FILE)
    df_client_expenses = load_data(CLIENT_EXPENSES_FILE)
    df_people = load_data(PEOPLE_FILE)
    
except Exception as e:
    st.error(f"Error loading data files. Please ensure {CSV_FILE}, {CLIENT_EXPENSES_FILE}, and {PEOPLE_FILE} exist and are valid CSV files. Error: {e}")
    st.stop()

# --- People Data Validation ---
if df_people.empty or 'name' not in df_people.columns or 'category' not in df_people.columns:
    st.error("The 'people.csv' file is missing or has an invalid format. Please ensure it exists and has 'name' and 'category' columns.")
    st.stop()
    
people_list = df_people['name'].unique().tolist()
client_list = df_people[df_people['category'] == 'client']['name'].unique().tolist()
if not people_list:
    st.warning("The 'people.csv' file contains no people. Please add people to enable transactions.")
if not client_list:
    st.warning("The 'people.csv' file contains no clients. Please add clients to enable client expenses and reports.")

# --- Sidebar ---
st.sidebar.header("Account Balances")
st.sidebar.markdown(
    "[Go to Payments Summary](https://atonomous.github.io/payments-summary/)"
)

if not df_payments.empty:
    df_payments['amount'] = pd.to_numeric(df_payments['amount'], errors='coerce').fillna(0)
    paid_to_me = df_payments[df_payments['type'] == 'paid_to_me']['amount'].sum()
    i_paid = df_payments[df_payments['type'] == 'i_paid']['amount'].sum()
    
    st.sidebar.metric("Total Payments Received", f"Rs. {paid_to_me:,.2f}")
    st.sidebar.metric("Total Payments Made", f"Rs. {i_paid:,.2f}")
    st.sidebar.metric("Overall Balance", f"Rs. {paid_to_me - i_paid:,.2f}", delta_color="inverse")
else:
    st.sidebar.info("No payments data available.")

if not df_client_expenses.empty:
    df_client_expenses['expense_amount'] = pd.to_numeric(df_client_expenses['expense_amount'], errors='coerce').fillna(0)
    total_client_expenses = (df_client_expenses['expense_amount'] * df_client_expenses['expense_quantity']).sum()
    st.sidebar.metric("Total Client Expenses", f"Rs. {total_client_expenses:,.2f}")
else:
    st.sidebar.info("No client expenses data available.")

# --- Main Content with Navigation Tabs ---
page = st.radio("Navigation", ["Dashboard", "Add Transaction", "View/Edit Payments", "Add Client Expenses", "View/Edit Client Expenses", "Generate Reports"], horizontal=True)

if page == "Dashboard":
    st.header("Dashboard")
    st.write("Welcome to the Finance Manager Dashboard.")

    if st.button("Create Backup"):
        success, message = add_and_commit([CSV_FILE, CLIENT_EXPENSES_FILE, PEOPLE_FILE], "Manual backup via Streamlit app")
        if success:
            st.success("Backup created successfully!")
        else:
            st.error(f"Failed to create backup: {message}")
            
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Total Received")
        st.metric("Payments", f"Rs. {df_payments[df_payments['type'] == 'paid_to_me']['amount'].sum():,.2f}")
    with col2:
        st.subheader("Total Paid")
        st.metric("Payments", f"Rs. {df_payments[df_payments['type'] == 'i_paid']['amount'].sum():,.2f}")
    with col3:
        st.subheader("Total Expenses")
        st.metric("Client Expenses", f"Rs. {df_client_expenses['expense_amount'].sum():,.2f}")

    st.subheader("Recent Payments")
    if not df_payments.empty:
        st.dataframe(df_payments.tail(5).drop(columns=['uuid'], errors='ignore'), use_container_width=True)
    else:
        st.info("No recent payments found.")

    st.subheader("Recent Client Expenses")
    if not df_client_expenses.empty:
        st.dataframe(df_client_expenses.tail(5).drop(columns=['uuid'], errors='ignore'), use_container_width=True)
    else:
        st.info("No recent client expenses found.")

elif page == "Add Transaction":
    st.header("Add New Payment Transaction")
    if not people_list:
        st.warning("No people found. Please add people to the 'people.csv' file.")
    else:
        with st.form("add_payment_form", clear_on_submit=st.session_state.reset_add_form):
            col1, col2 = st.columns(2)
            with col1:
                selected_type = st.radio("Transaction Type", ['Paid to Me', 'I Paid'], key='selected_transaction_type')
            with col2:
                selected_person = st.selectbox("Person", ["Select..."] + people_list, key='selected_person')
            
            col3, col4 = st.columns(2)
            with col3:
                add_amount = st.number_input("Amount (Rs.)", min_value=0.0, format="%.2f", key='add_amount')
            with col4:
                add_date = st.date_input("Date", datetime.today().date(), key='add_date')

            add_description = st.text_area("Description", key='add_description')

            col5, col6 = st.columns(2)
            with col5:
                payment_method = st.radio("Payment Method", ['cash', 'cheque'], key='payment_method')
            with col6:
                add_reference_number = st.text_input("Reference Number", key='add_reference_number')

            add_cheque_status = 'N/A'
            if payment_method == 'cheque':
                add_cheque_status = st.radio("Cheque Status", ['processing done', 'not cleared'], key='add_cheque_status')
            
            add_status = st.radio("Transaction Status", ['completed', 'pending'], key='add_status')

            submitted = st.form_submit_button("Add Transaction")
            if submitted:
                if selected_person == "Select...":
                    st.error("Please select a person.")
                elif not add_amount or add_amount <= 0:
                    st.error("Please enter a valid amount greater than zero.")
                elif payment_method == 'cheque' and not add_reference_number:
                    st.error("Please provide a reference number for cheque payments.")
                else:
                    new_df_payments = add_payment(
                        df_payments,
                        selected_person,
                        add_amount,
                        'paid_to_me' if selected_type == 'Paid to Me' else 'i_paid',
                        add_status,
                        add_description,
                        payment_method,
                        add_reference_number,
                        add_cheque_status,
                        add_date
                    )
                    save_data(new_df_payments, CSV_FILE)
                    success, message = add_and_commit([CSV_FILE], f"Added new transaction: {selected_type} for {selected_person}")
                    if success:
                        st.success("Transaction added successfully!")
                        st.session_state.reset_add_form = True
                        st.rerun()
                    else:
                        st.error(f"Transaction added, but failed to commit to Git: {message}")

elif page == "View/Edit Payments":
    st.header("View and Edit Payments")
    
    if df_payments.empty:
        st.info("No payments data available.")
    else:
        # --- Filters ---
        st.subheader("Filter Payments")
        
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            st.selectbox("Filter by Person", options=['All'] + people_list, key='view_person_filter')
        with col_filter2:
            st.selectbox("Filter by Payment Method", options=['All', 'cash', 'cheque'], key='view_payment_method_filter')
        
        col_filter3, col_filter4 = st.columns(2)
        with col_filter3:
            st.date_input("Start Date", value=st.session_state.view_start_date_filter, key='view_start_date_filter')
        with col_filter4:
            st.date_input("End Date", value=st.session_state.view_end_date_filter, key='view_end_date_filter')

        st.text_input("Search by Reference Number", key='view_reference_number_search')

        # Apply filters
        df_filtered_payments = df_payments.copy()
        df_filtered_payments['date'] = pd.to_datetime(df_filtered_payments['date'])

        if st.session_state.view_person_filter != 'All':
            df_filtered_payments = df_filtered_payments[df_filtered_payments['person'] == st.session_state.view_person_filter]
        
        if st.session_state.view_payment_method_filter != 'All':
            df_filtered_payments = df_filtered_payments[df_filtered_payments['payment_method'] == st.session_state.view_payment_method_filter]

        df_filtered_payments = df_filtered_payments[
            (df_filtered_payments['date'] >= pd.to_datetime(st.session_state.view_start_date_filter)) &
            (df_filtered_payments['date'] <= pd.to_datetime(st.session_state.view_end_date_filter))
        ]

        if st.session_state.view_reference_number_search:
            df_filtered_payments = df_filtered_payments[
                df_filtered_payments['reference_number'].str.contains(st.session_state.view_reference_number_search, case=False, na=False)
            ]
        
        st.subheader("Filtered Payments")
        st.dataframe(df_filtered_payments.drop(columns=['uuid'], errors='ignore'), use_container_width=True)

        # --- Edit Payments Dropdown ---
        st.subheader("Edit a Payment")
        
        if not df_filtered_payments.empty:
            df_filtered_payments['display_str'] = (df_filtered_payments['date'].astype(str) + ' | ' + 
                                                   df_filtered_payments['person'] + ' | ' + 
                                                   df_filtered_payments['amount'].astype(str) + ' | ' +
                                                   df_filtered_payments['type'])
            
            transaction_to_edit_uuid = st.selectbox(
                "Select a payment to edit",
                options=['Select a payment...'] + df_filtered_payments['uuid'].tolist(),
                format_func=lambda x: df_filtered_payments[df_filtered_payments['uuid'] == x]['display_str'].iloc[0] if x != 'Select a payment...' else x,
                key='edit_payments_dropdown'
            )

            if transaction_to_edit_uuid != 'Select a payment...':
                row_to_edit = df_payments[df_payments['uuid'] == transaction_to_edit_uuid].iloc[0]
                
                with st.form("edit_payment_form"):
                    st.subheader(f"Editing Payment from {row_to_edit['person']}")
                    
                    edit_col1, edit_col2 = st.columns(2)
                    with edit_col1:
                        edit_person = st.selectbox("Person", people_list, index=people_list.index(row_to_edit['person']))
                    with edit_col2:
                        edit_type = st.radio("Payment Type", ['Paid to Me', 'I Paid'], 
                                             index=['paid_to_me', 'i_paid'].index(row_to_edit['type']))
                        edit_type = 'paid_to_me' if edit_type == 'Paid to Me' else 'i_paid'

                    edit_col3, edit_col4 = st.columns(2)
                    with edit_col3:
                        edit_amount = st.number_input("Amount (Rs.)", min_value=0.0, value=float(row_to_edit['amount']), format="%.2f")
                    with edit_col4:
                        edit_date = st.date_input("Date", datetime.strptime(row_to_edit['date'], '%Y-%m-%d').date())

                    edit_description = st.text_area("Description", value=row_to_edit['description'])
                    
                    edit_col5, edit_col6 = st.columns(2)
                    with edit_col5:
                        edit_payment_method = st.radio("Payment Method", ['cash', 'cheque'], 
                                                       index=['cash', 'cheque'].index(row_to_edit['payment_method']))
                    with edit_col6:
                        edit_reference_number = st.text_input("Reference Number", value=row_to_edit['reference_number'])
                    
                    edit_cheque_status = 'N/A'
                    if edit_payment_method == 'cheque':
                        edit_cheque_status = st.radio("Cheque Status", ['processing done', 'not cleared'], 
                                                      index=['processing done', 'not cleared'].index(row_to_edit['cheque_status']))
                    
                    edit_status = st.radio("Payment Status", ['completed', 'pending'], 
                                           index=['completed', 'pending'].index(row_to_edit['status']))

                    col_edit_buttons = st.columns(3)
                    with col_edit_buttons[0]:
                        if st.form_submit_button("Update Payment"):
                            if edit_amount <= 0:
                                st.error("Please enter a valid amount greater than zero.")
                            elif edit_payment_method == 'cheque' and not edit_reference_number:
                                st.error("Please provide a reference number for cheque payments.")
                            else:
                                updated_df = update_payment(
                                    df_payments,
                                    transaction_to_edit_uuid,
                                    edit_person,
                                    edit_amount,
                                    edit_type,
                                    edit_status,
                                    edit_description,
                                    edit_payment_method,
                                    edit_reference_number,
                                    edit_cheque_status,
                                    edit_date
                                )
                                save_data(updated_df, CSV_FILE)
                                success, message = add_and_commit([CSV_FILE], f"Updated transaction for {edit_person}")
                                if success:
                                    st.success("Payment updated successfully!")
                                    st.rerun()
                                else:
                                    st.error(f"Payment updated, but failed to commit to Git: {message}")
                    with col_edit_buttons[1]:
                        if st.form_submit_button("Cancel Edit"):
                            st.rerun()
                    with col_edit_buttons[2]:
                        if st.form_submit_button("Delete Payment"):
                            updated_df = delete_payment(df_payments, transaction_to_edit_uuid)
                            save_data(updated_df, CSV_FILE)
                            success, message = add_and_commit([CSV_FILE], f"Deleted transaction for {row_to_edit['person']}")
                            if success:
                                st.success("Payment deleted successfully!")
                                st.rerun()
                            else:
                                st.error(f"Payment deleted, but failed to commit to Git: {message}")

elif page == "Add Client Expenses":
    st.header("Add New Client Expense")
    if not client_list:
        st.warning("No clients found. Please add clients to the 'people.csv' file.")
    else:
        with st.form("add_client_expense_form", clear_on_submit=st.session_state.reset_client_expense_form):
            selected_client_for_expense = st.selectbox("Client", ["Select..."] + client_list, key='selected_client_for_expense')
            
            col1, col2 = st.columns(2)
            with col1:
                add_client_expense_amount = st.number_input("Expense Amount (Rs.)", min_value=0.0, format="%.2f", key='add_client_expense_amount')
            with col2:
                add_client_expense_quantity = st.number_input("Quantity", min_value=1.0, format="%.1f", key='add_client_expense_quantity')
            
            add_client_expense_date = st.date_input("Date", datetime.today().date(), key='add_client_expense_date')
            add_client_expense_category = st.selectbox("Category", ['General', 'Travel', 'Labour', 'Material'], key='add_client_expense_category')
            add_client_expense_description = st.text_area("Description", key='add_client_expense_description')

            submitted = st.form_submit_button("Add Expense")
            if submitted:
                if selected_client_for_expense == "Select...":
                    st.error("Please select a client.")
                elif not add_client_expense_amount or add_client_expense_amount <= 0:
                    st.error("Please enter a valid expense amount greater than zero.")
                elif not add_client_expense_quantity or add_client_expense_quantity <= 0:
                    st.error("Please enter a valid quantity greater than zero.")
                else:
                    new_df_expenses = add_client_expense(
                        df_client_expenses,
                        selected_client_for_expense,
                        add_client_expense_amount,
                        add_client_expense_category,
                        add_client_expense_description,
                        add_client_expense_quantity,
                        add_client_expense_date
                    )
                    save_data(new_df_expenses, CLIENT_EXPENSES_FILE)
                    success, message = add_and_commit([CLIENT_EXPENSES_FILE], f"Added new client expense for {selected_client_for_expense}")
                    if success:
                        st.success("Client expense added successfully!")
                        st.session_state.reset_client_expense_form = True
                        st.rerun()
                    else:
                        st.error(f"Client expense added, but failed to commit to Git: {message}")

elif page == "View/Edit Client Expenses":
    st.header("View and Edit Client Expenses")
    
    if df_client_expenses.empty:
        st.info("No client expenses data available.")
    else:
        # --- Filters ---
        st.subheader("Filter Client Expenses")
        
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            st.selectbox("Filter by Client", options=['All'] + client_list, key='view_expense_person_filter')
        with col_filter2:
            st.selectbox("Filter by Category", options=['All', 'General', 'Travel', 'Labour', 'Material'], key='view_expense_category_filter')

        col_filter3, col_filter4 = st.columns(2)
        with col_filter3:
            st.date_input("Start Date", value=st.session_state.view_expense_start_date_filter, key='view_expense_start_date_filter')
        with col_filter4:
            st.date_input("End Date", value=st.session_state.view_expense_end_date_filter, key='view_expense_end_date_filter')

        st.text_input("Search by Description", key='view_expense_reference_number_search')

        # Apply filters
        df_filtered_expenses = df_client_expenses.copy()
        df_filtered_expenses['expense_date'] = pd.to_datetime(df_filtered_expenses['expense_date'])

        if st.session_state.view_expense_person_filter != 'All':
            df_filtered_expenses = df_filtered_expenses[df_filtered_expenses['expense_person'] == st.session_state.view_expense_person_filter]
        
        if st.session_state.view_expense_category_filter != 'All':
            df_filtered_expenses = df_filtered_expenses[df_filtered_expenses['expense_category'] == st.session_state.view_expense_category_filter]

        df_filtered_expenses = df_filtered_expenses[
            (df_filtered_expenses['expense_date'] >= pd.to_datetime(st.session_state.view_expense_start_date_filter)) &
            (df_filtered_expenses['expense_date'] <= pd.to_datetime(st.session_state.view_expense_end_date_filter))
        ]
        
        if st.session_state.view_expense_reference_number_search:
            df_filtered_expenses = df_filtered_expenses[
                df_filtered_expenses['expense_description'].str.contains(st.session_state.view_expense_reference_number_search, case=False, na=False)
            ]

        st.subheader("Filtered Client Expenses")
        st.dataframe(df_filtered_expenses.drop(columns=['uuid'], errors='ignore'), use_container_width=True)
            
        # --- Edit Client Expenses Dropdown ---
        st.subheader("Edit a Client Expense")
        
        if not df_filtered_expenses.empty:
            df_filtered_expenses['display_str'] = (df_filtered_expenses['expense_date'].astype(str) + ' | ' + 
                                                 df_filtered_expenses['expense_person'] + ' | ' + 
                                                 df_filtered_expenses['expense_amount'].astype(str) + ' | ' +
                                                 df_filtered_expenses['expense_category'])

            expense_to_edit_uuid = st.selectbox(
                "Select an expense to edit",
                options=['Select an expense...'] + df_filtered_expenses['uuid'].tolist(),
                format_func=lambda x: df_filtered_expenses[df_filtered_expenses['uuid'] == x]['display_str'].iloc[0] if x != 'Select an expense...' else x,
                key='edit_expenses_dropdown'
            )

            if expense_to_edit_uuid != 'Select an expense...':
                row_to_edit = df_client_expenses[df_client_expenses['uuid'] == expense_to_edit_uuid].iloc[0]
                
                with st.form("edit_client_expense_form"):
                    st.subheader(f"Editing Expense for {row_to_edit['expense_person']}")
                    
                    edit_person = st.selectbox("Client", client_list, index=client_list.index(row_to_edit['expense_person']))
                    edit_col1, edit_col2 = st.columns(2)
                    with edit_col1:
                        edit_amount = st.number_input("Expense Amount (Rs.)", min_value=0.0, value=float(row_to_edit['expense_amount']), format="%.2f")
                    with edit_col2:
                        edit_quantity = st.number_input("Quantity", min_value=1.0, value=float(row_to_edit['expense_quantity']), format="%.1f")
                    
                    edit_date = st.date_input("Date", datetime.strptime(row_to_edit['expense_date'], '%Y-%m-%d').date())
                    edit_category = st.selectbox("Category", ['General', 'Travel', 'Labour', 'Material'], index=['General', 'Travel', 'Labour', 'Material'].index(row_to_edit['expense_category']))
                    edit_description = st.text_area("Description", value=row_to_edit['expense_description'])
                    
                    col_edit_buttons = st.columns(3)
                    with col_edit_buttons[0]:
                        if st.form_submit_button("Update Expense"):
                            if edit_amount <= 0:
                                st.error("Please enter a valid expense amount greater than zero.")
                            elif edit_quantity <= 0:
                                st.error("Please enter a valid quantity greater than zero.")
                            else:
                                updated_df = update_client_expense(
                                    df_client_expenses,
                                    expense_to_edit_uuid,
                                    edit_person,
                                    edit_amount,
                                    edit_category,
                                    edit_description,
                                    edit_quantity,
                                    edit_date
                                )
                                save_data(updated_df, CLIENT_EXPENSES_FILE)
                                success, message = add_and_commit([CLIENT_EXPENSES_FILE], f"Updated client expense for {edit_person}")
                                if success:
                                    st.success("Client expense updated successfully!")
                                    st.rerun()
                                else:
                                    st.error(f"Client expense updated, but failed to commit to Git: {message}")
                    with col_edit_buttons[1]:
                        if st.form_submit_button("Cancel Edit"):
                            st.rerun()
                    with col_edit_buttons[2]:
                        if st.form_submit_button("Delete Expense"):
                            updated_df = delete_client_expense(df_client_expenses, expense_to_edit_uuid)
                            save_data(updated_df, CLIENT_EXPENSES_FILE)
                            success, message = add_and_commit([CLIENT_EXPENSES_FILE], f"Deleted client expense for {row_to_edit['expense_person']}")
                            if success:
                                st.success("Client expense deleted successfully!")
                                st.rerun()
                            else:
                                st.error(f"Client expense deleted, but failed to commit to Git: {message}")
            
elif page == "Generate Reports":
    st.header("Generate Comprehensive Reports")
    if not client_list:
        st.warning("No clients found to generate reports for. Please add clients to the 'people.csv' file.")
    else:
        with st.form("generate_report_form"):
            report_person_name = st.selectbox("Select Client", ["Select..."] + client_list, key='report_person_name')
            report_start_date = st.date_input("Start Date", st.session_state.report_start_date, key='report_start_date')
            report_end_date = st.date_input("End Date", st.session_state.report_end_date, key='report_end_date')
            
            submitted = st.form_submit_button("Generate Report")

            if submitted:
                if report_person_name == 'Select...':
                    st.error("Please select a client.")
                elif report_start_date > report_end_date:
                    st.error("Start date cannot be after end date.")
                else:
                    try:
                        pdf_bytes = create_full_report_pdf(
                            report_person_name,
                            report_start_date,
                            report_end_date
                        )
                        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
                        download_link = f'<a href="data:application/octet-stream;base64,{pdf_base64}" download="report_{report_person_name.replace(" ", "_")}_{report_start_date}_{report_end_date}.pdf">Download PDF Report</a>'
                        st.markdown(download_link, unsafe_allow_html=True)
                        st.success("Report generated and ready for download.")
                    except Exception as e:
                        st.error(f"Error generating PDF: {e}")
