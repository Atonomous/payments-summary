import streamlit as st
import pandas as pd
from datetime import datetime
import os
from git import Repo, GitCommandError
import numpy as np
import uuid
from fpdf import FPDF
import json # Used for serializing to JSON for the report

# --- Constants ---
# Moved file names to constants for easier management
CSV_FILE = 'payments.csv'
PEOPLE_FILE = 'people.csv'
CLIENT_EXPENSES_FILE = 'client_expenses.csv'
GIT_REPO_PATH = '.'  # Current directory
GIT_REMOTE_NAME = 'origin'
GIT_BRANCH_NAME = 'main'

# --- State Management ---
def init_state():
    """Initializes the session state variables if they don't already exist."""
    keys = [
        'selected_transaction_type', 'payment_method', 'editing_row_idx', 'selected_person', 'reset_add_form',
        'add_amount', 'add_date', 'add_reference_number', 'add_cheque_status', 'add_status', 'add_description',
        'temp_edit_data', 'invoice_person_name', 'invoice_type', 'invoice_start_date', 'invoice_end_date',
        'generated_invoice_pdf_path', 'show_download_button',
        'view_person_filter', 'view_reference_number_search', 'view_person_filter_client_expense',
        'selected_client_for_expense', 'add_client_expense_amount', 'add_client_expense_date',
        'add_client_expense_category', 'add_client_expense_description', 'reset_client_expense_form',
        'add_client_expense_quantity',
        'client_expense_ref_num_search',
        'editing_client_expense_idx',
        'temp_edit_client_expense_data',
        'client_expense_filter_start_date',
        'client_expense_filter_end_date',
        'payments_df',
        'people_df',
        'client_expenses_df',
        'html_summary_content',
        'temp_edit_data_people',
        'editing_people_idx'
    ]
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = None
    if st.session_state.reset_add_form is None:
        st.session_state.reset_add_form = True
    if st.session_state.reset_client_expense_form is None:
        st.session_state.reset_client_expense_form = True
    
    # Ensure date inputs are initialized to datetime objects
    if 'add_date' not in st.session_state or st.session_state.add_date is None:
        st.session_state.add_date = datetime.now().date()
    if 'add_client_expense_date' not in st.session_state or st.session_state.add_client_expense_date is None:
        st.session_state.add_client_expense_date = datetime.now().date()
    if 'invoice_start_date' not in st.session_state or st.session_state.invoice_start_date is None:
        st.session_state.invoice_start_date = datetime.now().date()
    if 'invoice_end_date' not in st.session_state or st.session_state.invoice_end_date is None:
        st.session_state.invoice_end_date = datetime.now().date()


# --- Helper Functions ---
def git_push(commit_message):
    """Commits and pushes changes to the remote git repository."""
    try:
        if not os.path.isdir(os.path.join(GIT_REPO_PATH, '.git')):
            st.error("Git repository not found. Please initialize a git repository in the app's directory.")
            return False

        repo = Repo(GIT_REPO_PATH)
        repo.git.add('.')
        repo.index.commit(commit_message)
        origin = repo.remote(name=GIT_REMOTE_NAME)
        origin.push(GIT_BRANCH_NAME)
        st.success("Changes committed and pushed to git successfully!")
        return True
    except GitCommandError as e:
        st.error(f"Git command failed: {e}")
        return False
    except Exception as e:
        st.error(f"An unexpected error occurred during git push: {e}")
        return False

def load_data():
    """
    Loads all data from CSV files and stores them in session state.
    This prevents redundant file reads and makes the app more efficient.
    Handles FileNotFoundError and EmptyDataError gracefully by creating
    new, empty DataFrames with the correct columns.
    """
    # Define a consistent schema for all dataframes
    payments_cols = ['uuid', 'person', 'type', 'amount', 'date', 'description', 'reference_number', 'cheque_status', 'status', 'payment_method']
    people_cols = ['name', 'contact', 'type']
    client_expenses_cols = ['uuid', 'person', 'date', 'description', 'category', 'amount', 'quantity', 'reference_number']

    # Load payments data
    try:
        df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
        # Drop the original 'status' column and rename 'transaction_status' to 'status'
        if 'status' in df.columns and 'transaction_status' in df.columns:
            df = df.drop(columns=['status'])
            df = df.rename(columns={'transaction_status': 'status'})
        # Standardize other column names
        df = df.rename(columns={
            'date': 'date',
            'person': 'person',
            'amount': 'amount',
            'type': 'type',
            'description': 'description',
            'payment_method': 'payment_method',
            'reference_number': 'reference_number',
            'cheque_status': 'cheque_status'
        })
        # Add a UUID column if it doesn't exist
        if 'uuid' not in df.columns:
            df['uuid'] = [str(uuid.uuid4()) for _ in range(len(df))]
        st.session_state.payments_df = df
    except (FileNotFoundError, pd.errors.EmptyDataError):
        st.session_state.payments_df = pd.DataFrame(columns=payments_cols)
    st.session_state.payments_df.to_csv(CSV_FILE, index=False)


    # Load people data
    try:
        st.session_state.people_df = pd.read_csv(PEOPLE_FILE, keep_default_na=False)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        st.session_state.people_df = pd.DataFrame(columns=people_cols)
    st.session_state.people_df.to_csv(PEOPLE_FILE, index=False)

    # Load client expenses data
    try:
        df = pd.read_csv(CLIENT_EXPENSES_FILE, dtype={'original_transaction_ref_num': str}, keep_default_na=False)
        # Standardize column names from the provided CSV
        df = df.rename(columns={
            'expense_date': 'date',
            'expense_person': 'person',
            'expense_category': 'category',
            'expense_amount': 'amount',
            'expense_quantity': 'quantity',
            'expense_description': 'description',
            'original_transaction_ref_num': 'reference_number',
        })
        # Add a UUID column if it doesn't exist
        if 'uuid' not in df.columns:
            df['uuid'] = [str(uuid.uuid4()) for _ in range(len(df))]
        st.session_state.client_expenses_df = df
    except (FileNotFoundError, pd.errors.EmptyDataError):
        st.session_state.client_expenses_df = pd.DataFrame(columns=client_expenses_cols)
    st.session_state.client_expenses_df.to_csv(CLIENT_EXPENSES_FILE, index=False)


def update_people_list(person_name):
    """
    Checks if a person exists in the people list and adds them if not.
    """
    if person_name not in st.session_state.people_df['name'].values:
        new_person = pd.DataFrame([{'name': person_name, 'contact': '', 'type': 'Client'}])
        st.session_state.people_df = pd.concat([st.session_state.people_df, new_person], ignore_index=True)
        st.session_state.people_df.to_csv(PEOPLE_FILE, index=False)

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Invoice', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, title, 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, body):
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, body)
        self.ln()

    def add_table(self, data, headers):
        self.set_font('Arial', 'B', 10)
        col_widths = [self.w / (len(headers) + 1)] * len(headers)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, str(header), 1, 0, 'C')
        self.ln()
        self.set_font('Arial', '', 10)
        for row in data:
            for i, item in enumerate(row):
                self.cell(col_widths[i], 7, str(item), 1, 0, 'C')
            self.ln()

def generate_invoice_pdf(person, invoice_type, start_date, end_date):
    """Generates a PDF invoice for a given person and date range."""
    payments_df = st.session_state.payments_df
    client_expenses_df = st.session_state.client_expenses_df

    if invoice_type == 'Payments':
        data = payments_df[
            (payments_df['person'] == person) &
            (pd.to_datetime(payments_df['date']) >= pd.to_datetime(start_date)) &
            (pd.to_datetime(payments_df['date']) <= pd.to_datetime(end_date))
        ]
        total_amount = data['amount'].sum()
        headers = ['Date', 'Type', 'Amount', 'Description']
        table_data = data[['date', 'type', 'amount', 'description']].values.tolist()
    else:  # Client Expenses
        data = client_expenses_df[
            (client_expenses_df['person'] == person) &
            (pd.to_datetime(client_expenses_df['date']) >= pd.to_datetime(start_date)) &
            (pd.to_datetime(client_expenses_df['date']) <= pd.to_datetime(end_date))
        ]
        total_amount = data['amount'].sum()
        headers = ['Date', 'Category', 'Description', 'Amount', 'Quantity']
        table_data = data[['date', 'category', 'description', 'amount', 'quantity']].values.tolist()

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.chapter_title(f'Invoice for {person}')
    pdf.chapter_body(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    pdf.chapter_body(f"Total {invoice_type}: Rs. {total_amount:,.2f}")
    if not data.empty:
      pdf.add_table(table_data, headers)
    else:
      pdf.chapter_body("No data found for this period.")

    invoice_filename = f"invoice_{person}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
    pdf_output_path = os.path.join(".", invoice_filename)
    pdf.output(pdf_output_path)
    return pdf_output_path

# --- Main App ---
st.set_page_config(layout="wide")
st.title("Payments & Client Expenses Management System")

# Initialize session state first thing
init_state()

# Load data into session state at the beginning of every run
# This is the key fix to prevent NoneType errors.
load_data()

# Use the dataframes from session state throughout the app
payments_df = st.session_state.payments_df
people_df = st.session_state.people_df
client_expenses_df = st.session_state.client_expenses_df

# --- Sidebar ---
st.sidebar.header("Balances Summary")

try:
    if not payments_df.empty:
        paid = payments_df[payments_df['type'] == 'Paid']['amount'].sum()
        received = payments_df[payments_df['type'] == 'Received']['amount'].sum()
        net_balance = received - paid

        st.sidebar.metric("Total Received", f"Rs. {received:,.2f}")
        st.sidebar.metric("Total Paid", f"Rs. {paid:,.2f}")
        st.sidebar.metric("Net Balance", f"Rs. {net_balance:,.2f}")
    else:
        st.sidebar.info("No transactions yet.")
except KeyError as e:
    st.sidebar.error(f"Dataframe is missing a column: {str(e)}. Please check the CSV files for correct headers.")
except Exception as e:
    st.sidebar.error(f"Error loading balances: {str(e)}")

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Add Transaction", "View Payments", "Add Client Expense", "View Client Expenses", "Manage People", "Reports & Invoice"])

# --- Tab 1: Add Transaction ---
with tab1:
    st.header("Add New Transaction")
    if st.session_state.reset_add_form:
        st.session_state.add_amount = None
        st.session_state.add_date = datetime.now().date()
        st.session_state.add_reference_number = ''
        st.session_state.add_cheque_status = 'Pending'
        st.session_state.add_description = ''
        st.session_state.selected_transaction_type = 'Paid'
        st.session_state.payment_method = 'Cash'
        st.session_state.selected_person = 'Select a person'

    with st.form("add_transaction_form", clear_on_submit=True):
        st.session_state.selected_transaction_type = st.radio(
            "Transaction Type",
            ['Paid', 'Received'],
            horizontal=True,
            index=0 if st.session_state.selected_transaction_type == 'Paid' else 1
        )
        
        people_options = ['Select a person'] + people_df['name'].tolist()
        st.session_state.selected_person = st.selectbox(
            "Person/Client",
            options=people_options,
            index=people_options.index(st.session_state.selected_person) if st.session_state.selected_person in people_options else 0
        )
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.add_amount = st.number_input("Amount", min_value=0.01, format="%.2f", key="add_amount_input", value=st.session_state.add_amount)
        with col2:
            st.session_state.add_date = st.date_input("Date", key="add_date_input", value=st.session_state.add_date)
        
        st.session_state.payment_method = st.radio(
            "Payment Method",
            ['Cash', 'Cheque'],
            horizontal=True,
            index=0 if st.session_state.payment_method == 'Cash' else 1
        )
        if st.session_state.payment_method == 'Cheque':
            st.session_state.add_reference_number = st.text_input("Cheque Number", key="add_ref_num_input", value=st.session_state.add_reference_number)
            st.session_state.add_cheque_status = st.selectbox(
                "Cheque Status",
                ['Pending', 'Cleared', 'Bounced'],
                index=['Pending', 'Cleared', 'Bounced'].index(st.session_state.add_cheque_status) if st.session_state.add_cheque_status in ['Pending', 'Cleared', 'Bounced'] else 0
            )
        else:
            st.session_state.add_reference_number = st.text_input("Reference Number (Optional)", key="add_ref_num_input_cash", value=st.session_state.add_reference_number)

        st.session_state.add_description = st.text_area("Description", key="add_description_input", value=st.session_state.add_description)

        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            if st.session_state.selected_person == 'Select a person':
                st.error("Please select a person/client.")
            elif st.session_state.add_amount is None or st.session_state.add_amount <= 0:
                st.error("Please enter a valid amount.")
            else:
                if st.session_state.selected_person not in people_df['name'].values:
                    update_people_list(st.session_state.selected_person)
                    people_df = st.session_state.people_df

                new_row = {
                    'uuid': str(uuid.uuid4()),
                    'person': st.session_state.selected_person,
                    'type': st.session_state.selected_transaction_type,
                    'amount': st.session_state.add_amount,
                    'date': st.session_state.add_date.strftime('%Y-%m-%d'),
                    'description': st.session_state.add_description,
                    'reference_number': st.session_state.add_reference_number,
                    'cheque_status': st.session_state.add_cheque_status if st.session_state.payment_method == 'Cheque' else '',
                    'status': 'Completed',
                    'payment_method': st.session_state.payment_method
                }
                
                st.session_state.payments_df = pd.concat([st.session_state.payments_df, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.payments_df.to_csv(CSV_FILE, index=False)
                st.success(f"Successfully added {st.session_state.selected_transaction_type} transaction!")
                st.session_state.reset_add_form = True
                st.rerun()

# --- Tab 2: View Payments ---
with tab2:
    st.header("View and Edit Payments")
    st.info("Remember to click 'Save Payments' to save any changes you make in the table.")
    
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        filter_people_options = ['All'] + st.session_state.people_df['name'].tolist()
        st.session_state.view_person_filter = st.selectbox(
            "Filter by Person",
            options=filter_people_options,
            index=filter_people_options.index(st.session_state.view_person_filter) if st.session_state.view_person_filter in filter_people_options else 0,
            key='view_person_filter_payments'
        )
    with filter_col2:
        st.session_state.view_reference_number_search = st.text_input(
            "Search by Reference Number",
            value=st.session_state.view_reference_number_search,
            key='ref_num_search_payments'
        )

    filtered_payments_df = payments_df.copy()
    if st.session_state.view_person_filter != 'All':
        filtered_payments_df = filtered_payments_df[filtered_payments_df['person'] == st.session_state.view_person_filter]
    if st.session_state.view_reference_number_search:
        filtered_payments_df = filtered_payments_df[
            filtered_payments_df['reference_number'].str.contains(st.session_state.view_reference_number_search, case=False, na=False)
        ]
    
    if not filtered_payments_df.empty:
      filtered_payments_df['date'] = pd.to_datetime(filtered_payments_df['date'])
      filtered_payments_df = filtered_payments_df.sort_values(by='date', ascending=False)
      filtered_payments_df['date'] = filtered_payments_df['date'].dt.strftime('%Y-%m-%d')
    
    st.subheader("Payment Transactions")
    edited_df = st.data_editor(
        filtered_payments_df,
        key='payments_data_editor',
        use_container_width=True,
        num_rows="dynamic",
        column_order=('person', 'type', 'amount', 'date', 'description', 'reference_number', 'payment_method', 'cheque_status', 'status')
    )
    
    if st.button("Save Payments", key="save_payments_button"):
        st.session_state.payments_df = edited_df
        st.session_state.payments_df.to_csv(CSV_FILE, index=False)
        git_push("Updated payments data.")
        st.success("Payments updated and saved successfully!")
        st.rerun()

# --- Tab 3: Add Client Expense ---
with tab3:
    st.header("Add New Client Expense")
    if st.session_state.reset_client_expense_form:
        st.session_state.add_client_expense_amount = None
        st.session_state.add_client_expense_date = datetime.now().date()
        st.session_state.add_client_expense_description = ''
        st.session_state.add_client_expense_category = 'Material'
        st.session_state.add_client_expense_quantity = None
        st.session_state.selected_client_for_expense = 'Select a client'
        st.session_state.client_expense_ref_num_search = ''

    with st.form("add_client_expense_form", clear_on_submit=True):
        client_options = ['Select a client'] + people_df['name'].tolist()
        st.session_state.selected_client_for_expense = st.selectbox(
            "Client",
            options=client_options,
            index=client_options.index(st.session_state.selected_client_for_expense) if st.session_state.selected_client_for_expense in client_options else 0
        )
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.add_client_expense_amount = st.number_input("Amount", min_value=0.01, format="%.2f", key="add_expense_amount_input", value=st.session_state.add_client_expense_amount)
        with col2:
            st.session_state.add_client_expense_date = st.date_input("Date", key="add_expense_date_input", value=st.session_state.add_client_expense_date)
        
        st.session_state.add_client_expense_category = st.text_input("Category", value=st.session_state.add_client_expense_category)
        st.session_state.add_client_expense_quantity = st.number_input("Quantity", min_value=1, format="%d", value=st.session_state.add_client_expense_quantity or 1)
        st.session_state.add_client_expense_description = st.text_area("Description", value=st.session_state.add_client_expense_description)

        submitted_expense = st.form_submit_button("Add Client Expense")
        if submitted_expense:
            if st.session_state.selected_client_for_expense == 'Select a client':
                st.error("Please select a client.")
            elif st.session_state.add_client_expense_amount is None or st.session_state.add_client_expense_amount <= 0:
                st.error("Please enter a valid amount.")
            else:
                if st.session_state.selected_client_for_expense not in people_df['name'].values:
                    update_people_list(st.session_state.selected_client_for_expense)
                    people_df = st.session_state.people_df

                new_expense_row = {
                    'uuid': str(uuid.uuid4()),
                    'person': st.session_state.selected_client_for_expense,
                    'date': st.session_state.add_client_expense_date.strftime('%Y-%m-%d'),
                    'description': st.session_state.add_client_expense_description,
                    'category': st.session_state.add_client_expense_category,
                    'amount': st.session_state.add_client_expense_amount,
                    'quantity': st.session_state.add_client_expense_quantity,
                    'reference_number': st.session_state.client_expense_ref_num_search
                }
                
                st.session_state.client_expenses_df = pd.concat([st.session_state.client_expenses_df, pd.DataFrame([new_expense_row])], ignore_index=True)
                st.session_state.client_expenses_df.to_csv(CLIENT_EXPENSES_FILE, index=False)
                st.success("Successfully added client expense!")
                st.session_state.reset_client_expense_form = True
                st.rerun()

# --- Tab 4: View Client Expenses ---
with tab4:
    st.header("View and Edit Client Expenses")
    st.info("Remember to click 'Save Client Expenses' to save any changes you make in the table.")
    
    filter_exp_col1, filter_exp_col2 = st.columns(2)
    with filter_exp_col1:
        filter_people_options = ['All'] + st.session_state.people_df['name'].tolist()
        st.session_state.view_person_filter_client_expense = st.selectbox(
            "Filter by Person",
            options=filter_people_options,
            index=filter_people_options.index(st.session_state.view_person_filter_client_expense) if st.session_state.view_person_filter_client_expense in filter_people_options else 0,
            key='view_person_filter_client_expense_editor'
        )
    with filter_exp_col2:
        st.session_state.client_expense_ref_num_search = st.text_input(
            "Search by Reference Number",
            value=st.session_state.client_expense_ref_num_search,
            key='ref_num_search_client_expense'
        )

    filtered_client_expenses_df = client_expenses_df.copy()
    if st.session_state.view_person_filter_client_expense != 'All':
        filtered_client_expenses_df = filtered_client_expenses_df[filtered_client_expenses_df['person'] == st.session_state.view_person_filter_client_expense]
    if st.session_state.client_expense_ref_num_search:
        filtered_client_expenses_df = filtered_client_expenses_df[
            filtered_client_expenses_df['reference_number'].str.contains(st.session_state.client_expense_ref_num_search, case=False, na=False)
        ]
        
    if not filtered_client_expenses_df.empty:
      filtered_client_expenses_df['date'] = pd.to_datetime(filtered_client_expenses_df['date'])
      filtered_client_expenses_df = filtered_client_expenses_df.sort_values(by='date', ascending=False)
      filtered_client_expenses_df['date'] = filtered_client_expenses_df['date'].dt.strftime('%Y-%m-%d')
    
    st.subheader("Client Expenses")
    edited_client_expenses_df = st.data_editor(
        filtered_client_expenses_df,
        key='client_expenses_data_editor',
        use_container_width=True,
        num_rows="dynamic",
        column_order=('person', 'date', 'description', 'category', 'amount', 'quantity', 'reference_number')
    )
    
    if st.button("Save Client Expenses", key="save_client_expenses_button"):
        st.session_state.client_expenses_df = edited_client_expenses_df
        st.session_state.client_expenses_df.to_csv(CLIENT_EXPENSES_FILE, index=False)
        git_push("Updated client expenses data.")
        st.success("Client expenses updated and saved successfully!")
        st.rerun()

# --- Tab 5: Manage People (New Tab) ---
with tab5:
    st.header("Manage People")
    st.subheader("Add New Person")
    with st.form("add_person_form", clear_on_submit=True):
        new_person_name = st.text_input("Name")
        new_person_contact = st.text_input("Contact Details (Optional)")
        new_person_type = st.radio("Type", ['Client', 'Vendor', 'Other'], horizontal=True)
        if st.form_submit_button("Add Person"):
            if new_person_name:
                if new_person_name not in people_df['name'].values:
                    new_person = pd.DataFrame([{'name': new_person_name, 'contact': new_person_contact, 'type': new_person_type}])
                    st.session_state.people_df = pd.concat([st.session_state.people_df, new_person], ignore_index=True)
                    st.session_state.people_df.to_csv(PEOPLE_FILE, index=False)
                    st.success(f"Person '{new_person_name}' added successfully!")
                    st.rerun()
                else:
                    st.error(f"A person with the name '{new_person_name}' already exists.")
            else:
                st.error("Please enter a name.")
    
    st.subheader("View and Edit People")
    st.info("You can delete a person by selecting the row and pressing the 'Delete' key. Saving will also remove all associated payments and expenses for that person.")
    
    # Display the people table
    edited_people_df = st.data_editor(
        people_df,
        key='people_data_editor',
        use_container_width=True,
        num_rows="dynamic",
        column_order=('name', 'contact', 'type')
    )
    
    if st.button("Save People", key="save_people_button"):
        # Get the list of people who were in the old dataframe but are not in the new one
        deleted_people = people_df[~people_df['name'].isin(edited_people_df['name'])]['name'].tolist()
        
        if deleted_people:
            # Filter out all payments and client expenses for the deleted people
            st.session_state.payments_df = st.session_state.payments_df[~st.session_state.payments_df['person'].isin(deleted_people)]
            st.session_state.client_expenses_df = st.session_state.client_expenses_df[~st.session_state.client_expenses_df['person'].isin(deleted_people)]
            
            # Save the updated payments and client expenses dataframes
            st.session_state.payments_df.to_csv(CSV_FILE, index=False)
            st.session_state.client_expenses_df.to_csv(CLIENT_EXPENSES_FILE, index=False)
            st.warning(f"Deleted data for: {', '.join(deleted_people)}")

        # Save the updated people list
        st.session_state.people_df = edited_people_df
        st.session_state.people_df.to_csv(PEOPLE_FILE, index=False)
        
        git_push("Updated people data and deleted associated records.")
        st.success("People list and associated data updated and saved successfully!")
        st.rerun()

# --- Tab 6: Reports & Invoice ---
with tab6:
    st.header("Reports & Invoice")

    total_received = payments_df[payments_df['type'] == 'Received']['amount'].sum()
    total_paid = payments_df[payments_df['type'] == 'Paid']['amount'].sum()
    net_balance = total_received - total_paid

    st.subheader("Financial Summary")
    
    summary_cols = st.columns(3)
    summary_cols[0].metric("Total Received", f"Rs. {total_received:,.2f}")
    summary_cols[1].metric("Total Paid", f"Rs. {total_paid:,.2f}")
    summary_cols[2].metric("Net Balance", f"Rs. {net_balance:,.2f}")

    if not client_expenses_df.empty:
        total_client_expenses = client_expenses_df['amount'].sum()
        st.metric("Total Client Expenses", f"Rs. {total_client_expenses:,.2f}")
        st.metric("Net Balance (Received - Spent)", f"Rs. {total_received - total_client_expenses:,.2f}")

    st.subheader("Spending Overview by Client")
    if not client_expenses_df.empty:
        client_expenses_summary = client_expenses_df.groupby('person')['amount'].sum().sort_values(ascending=False)
        st.bar_chart(client_expenses_summary)
        st.write("Top spending clients:")
        st.write(client_expenses_summary)
    else:
        st.info("No client expenses to show.")

    st.subheader("Generate Invoice")
    
    with st.form("invoice_form"):
        invoice_person_options = ['Select a client'] + people_df['name'].tolist()
        st.session_state.invoice_person_name = st.selectbox(
            "Select Person/Client",
            options=invoice_person_options,
            index=invoice_person_options.index(st.session_state.invoice_person_name) if st.session_state.invoice_person_name in invoice_person_options else 0
        )
        st.session_state.invoice_type = st.radio("Invoice Type", ['Payments', 'Client Expenses'], horizontal=True)

        col1, col2 = st.columns(2)
        with col1:
            st.session_state.invoice_start_date = st.date_input("Start Date", value=st.session_state.invoice_start_date or datetime.now().date())
        with col2:
            st.session_state.invoice_end_date = st.date_input("End Date", value=st.session_state.invoice_end_date or datetime.now().date())
        
        generate_button = st.form_submit_button("Generate Invoice PDF")
        if generate_button:
            if st.session_state.invoice_person_name == 'Select a client':
                st.error("Please select a client to generate an invoice.")
            else:
                with st.spinner("Generating PDF..."):
                    pdf_path = generate_invoice_pdf(
                        st.session_state.invoice_person_name,
                        st.session_state.invoice_type,
                        st.session_state.invoice_start_date,
                        st.session_state.invoice_end_date
                    )
                    st.session_state.generated_invoice_pdf_path = pdf_path
                    st.session_state.show_download_button = True
                    st.success("Invoice generated successfully!")

    if st.session_state.show_download_button and st.session_state.generated_invoice_pdf_path:
        with open(st.session_state.generated_invoice_pdf_path, "rb") as pdf_file:
            st.download_button(
                label="Download Invoice PDF",
                data=pdf_file,
                file_name=os.path.basename(st.session_state.generated_invoice_pdf_path),
                mime="application/pdf"
            )

try:
    current_payments_df = st.session_state.payments_df.copy()
    if not current_payments_df.empty:
      current_payments_df['reference_number'] = current_payments_df['reference_number'].apply(
          lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' else str(x)
      )

      paid = current_payments_df[current_payments_df['type'] == 'Paid']['amount'].sum()
      received = current_payments_df[current_payments_df['type'] == 'Received']['amount'].sum()
    else:
      paid = 0
      received = 0

    html_summary = f"""
    <html>
    <head>
    <style>
        body {{ font-family: sans-serif; }}
        h3 {{ color: #004d40; }}
        .metric {{
            background-color: #e0f7fa;
            border: 1px solid #00acc1;
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 10px;
        }}
    </style>
    </head>
    <body>
        <h3>Financial Summary</h3>
        <div class="metric">
            <strong>Total Received:</strong> Rs. {received:,.2f}
        </div>
        <div class="metric">
            <strong>Total Paid:</strong> Rs. {paid:,.2f}
        </div>
        <div class="metric">
            <strong>Net Balance:</strong> Rs. {received - paid:,.2f}
        </div>
    </body>
    </html>
    """
    
    st.session_state.html_summary_content = html_summary

except (FileNotFoundError, pd.errors.EmptyDataError):
    st.session_state.html_summary_content = "<html><body><h3>Financial Summary</h3><p>No transactions found.</p></body></html>"
except Exception as e:
    st.session_state.html_summary_content = f"<html><body><h3>Financial Summary</h3><p>Error loading summary: {str(e)}</p></body></html>"
