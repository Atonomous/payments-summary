import streamlit as st
import pandas as pd
from datetime import datetime
import os
from git import Repo
import numpy as np
import uuid
from fpdf import FPDF
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import zipfile

# --- Git and CSV File Configuration ---
# File paths
CSV_FILE = "payments.csv"
CLIENTS_FILE = "clients.csv"
CLIENT_EXPENSES_FILE = "client_expenses.csv"
PEOPLE_FILE = "people.csv"

# Check if we're in a Git repository
try:
    repo = Repo('.')
    st.session_state.is_git_repo = True
except:
    st.session_state.is_git_repo = False

# --- Data Initialization and State Management ---
def init_state():
    """Initializes Streamlit session state variables."""
    keys = [
        'selected_transaction_type', 'payment_method', 'editing_row_idx', 'selected_person', 'reset_add_form',
        'add_amount', 'add_date', 'add_reference_number', 'add_cheque_status', 'add_status', 'add_description',
        'temp_edit_data', 'invoice_person_name', 'invoice_type', 'invoice_start_date', 'invoice_end_date',
        'generated_invoice_pdf_path', 'show_download_button',
        'view_person_filter', 'view_reference_number_search',
        'selected_client_for_expense', 'add_client_expense_amount', 'add_client_expense_date',
        'add_client_expense_category', 'add_client_expense_description', 'reset_client_expense_form',
        'add_client_expense_quantity', 'client_expense_ref_num_search',
        'editing_client_expense_idx', 'temp_edit_client_expense_data',
        'client_expense_filter_start_date', 'client_expense_filter_end_date',
        'add_client_expense_status',
        'is_git_repo', 'people_df', 'selected_person_to_add', 'current_tab',
        'selected_per_person_report_person', 'per_person_report_start_date', 'per_person_report_end_date',
        'selected_per_person_report_tab',
        # New keys for the expense bill feature
        'bill_client_name', 'bill_start_date', 'bill_end_date', 'generated_bill_pdf_path', 'show_bill_download_button'
    ]
    for key in keys:
        if key not in st.session_state:
            st.session_state[key] = None

    if 'current_tab' not in st.session_state or st.session_state.current_tab is None:
        st.session_state.current_tab = "Home"


def init_files():
    """Initializes CSV files if they don't exist."""
    # Ensure `payments.csv` exists with correct columns
    if not os.path.exists(CSV_FILE):
        df = pd.DataFrame(columns=[
            'transaction_uuid', 'transaction_type', 'person', 'payment_method', 'amount', 'date',
            'reference_number', 'status', 'description', 'cheque_status'
        ])
        df.to_csv(CSV_FILE, index=False)
        st.info("`payments.csv` file created.")
    else:
        # Load and sanitize existing payments data
        df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
        df['reference_number'] = df['reference_number'].apply(lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' else str(x).strip())
        df['transaction_uuid'] = df['transaction_uuid'].apply(lambda x: str(uuid.uuid4()) if pd.isna(x) or str(x).strip().lower() == 'nan' else x)
        # Ensure all columns exist, add if missing
        required_cols = ['transaction_uuid', 'transaction_type', 'person', 'payment_method', 'amount', 'date',
                         'reference_number', 'status', 'description', 'cheque_status']
        for col in required_cols:
            if col not in df.columns:
                df[col] = ''
        df.to_csv(CSV_FILE, index=False)

    # Ensure `clients.csv` exists with correct columns
    if not os.path.exists(CLIENTS_FILE):
        df_clients = pd.DataFrame(columns=['name'])
        df_clients.to_csv(CLIENTS_FILE, index=False)
        st.info("`clients.csv` file created.")

    # Ensure `people.csv` exists with correct columns
    if not os.path.exists(PEOPLE_FILE):
        df_people = pd.DataFrame(columns=['name', 'person_type'])
        df_people.to_csv(PEOPLE_FILE, index=False)
        st.info("`people.csv` file created.")
    else:
        # Load and sanitize existing people data
        df_people = pd.read_csv(PEOPLE_FILE, keep_default_na=False)
        if 'person_type' not in df_people.columns:
            df_people['person_type'] = 'client'
        df_people.to_csv(PEOPLE_FILE, index=False)

    # Ensure `client_expenses.csv` exists with correct columns
    if not os.path.exists(CLIENT_EXPENSES_FILE):
        df_exp = pd.DataFrame(columns=[
            'expense_uuid', 'original_transaction_ref_num', 'expense_person', 'expense_amount',
            'expense_quantity', 'expense_date', 'expense_category', 'expense_status',
            'expense_description', 'expense_created_by'
        ])
        df_exp.to_csv(CLIENT_EXPENSES_FILE, index=False)
        st.info("`client_expenses.csv` file created.")
    else:
        # Load and sanitize existing client expenses data
        df_exp = pd.read_csv(CLIENT_EXPENSES_FILE,
                             dtype={'original_transaction_ref_num': str, 'expense_person': str},
                             keep_default_na=False)
        df_exp['expense_amount'] = pd.to_numeric(df_exp['expense_amount'], errors='coerce').fillna(0.0)
        df_exp['expense_quantity'] = pd.to_numeric(df_exp['expense_quantity'], errors='coerce').fillna(0.0)
        df_exp['expense_uuid'] = df_exp['expense_uuid'].apply(lambda x: str(uuid.uuid4()) if pd.isna(x) or str(x).strip().lower() == 'nan' else x)
        required_exp_cols = [
            'expense_uuid', 'original_transaction_ref_num', 'expense_person', 'expense_amount',
            'expense_quantity', 'expense_date', 'expense_category', 'expense_status',
            'expense_description', 'expense_created_by'
        ]
        for col in required_exp_cols:
            if col not in df_exp.columns:
                df_exp[col] = ''
        df_exp.to_csv(CLIENT_EXPENSES_FILE, index=False)


# --- Data Management Functions ---
def save_data(df, file_path):
    """Saves a DataFrame to a CSV file and commits to Git if enabled."""
    df.to_csv(file_path, index=False)
    if st.session_state.get('is_git_repo', False):
        try:
            repo.index.add([file_path])
            repo.index.commit(f"Updated {file_path}")
        except Exception as e:
            st.error(f"Error committing to Git: {e}")


def load_data(file_path, dtype=None):
    """Loads a DataFrame from a CSV file, handling potential errors."""
    if os.path.exists(file_path):
        try:
            return pd.read_csv(file_path, dtype=dtype, keep_default_na=False)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Error loading data from {file_path}: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


def get_people():
    """Loads and returns the people DataFrame."""
    init_files()  # Ensure files exist before loading
    df_people = load_data(PEOPLE_FILE)
    if not df_people.empty:
        if 'person_type' not in df_people.columns:
            df_people['person_type'] = 'client'
        df_people = df_people.sort_values(by=['person_type', 'name']).reset_index(drop=True)
    return df_people


# --- App UI & Logic ---
def create_app():
    """Main Streamlit application function."""
    st.set_page_config(
        page_title="Fin-Tracker",
        page_icon="💸",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Initialize state and files
    init_state()
    init_files()
    df_people = get_people()
    st.session_state.people_df = df_people

    st.title("Fin-Tracker")

    # Sidebar with a logo and an info box
    with st.sidebar:
        st.subheader("Fin-Tracker")
        st.write("---")

        try:
            if os.path.exists(CSV_FILE):
                df_payments = load_data(CSV_FILE, dtype={'reference_number': str})
                if not df_payments.empty:
                    df_payments['amount'] = pd.to_numeric(df_payments['amount'], errors='coerce').fillna(0.0)

                    paid = df_payments[df_payments['transaction_type'] == 'Paid']['amount'].sum()
                    received = df_payments[df_payments['transaction_type'] == 'Received']['amount'].sum()
                    net_balance = received - paid

                    cash_rec = df_payments[(df_payments['transaction_type'] == 'Received') & (df_payments['payment_method'] == 'Cash')]['amount'].sum()
                    cheque_rec = df_payments[(df_payments['transaction_type'] == 'Received') & (df_payments['payment_method'] == 'Cheque')]['amount'].sum()
                    cash_paid = df_payments[(df_payments['transaction_type'] == 'Paid') & (df_payments['payment_method'] == 'Cash')]['amount'].sum()
                    cheque_paid = df_payments[(df_payments['transaction_type'] == 'Paid') & (df_payments['payment_method'] == 'Cheque')]['amount'].sum()

                    if os.path.exists(CLIENT_EXPENSES_FILE):
                        df_client_expenses = load_data(CLIENT_EXPENSES_FILE)
                        if not df_client_expenses.empty:
                            df_client_expenses['expense_amount'] = pd.to_numeric(df_client_expenses['expense_amount'], errors='coerce').fillna(0.0)
                            total_client_expenses_for_sidebar = df_client_expenses['expense_amount'].sum()
                            st.sidebar.metric("Total Client Expenses", f"Rs. {total_client_expenses_for_sidebar:,.2f}")
                        else:
                            total_client_expenses_for_sidebar = 0
                    else:
                        total_client_expenses_for_sidebar = 0

                    st.sidebar.metric("Total Received", f"Rs. {received:,.2f}", delta_color="normal")
                    st.sidebar.metric("Total Paid", f"Rs. {paid:,.2f}", delta_color="inverse")
                    st.sidebar.metric("Net Balance (Received - Paid)", f"Rs. {net_balance:,.2f}", delta_color="inverse")

                    with st.sidebar.expander("Payment Methods"):
                        st.write("---")
                        st.write("### Received")
                        st.write(f"**Cash:** Rs. {cash_rec:,.2f}")
                        st.write(f"**Cheque:** Rs. {cheque_rec:,.2f}")
                        st.write("### Paid")
                        st.write(f"**Cash:** Rs. {cash_paid:,.2f}")
                        st.write(f"**Cheque:** Rs. {cheque_paid:,.2f}")
                else:
                    st.sidebar.info("No transactions yet.")
            else:
                st.sidebar.info("Transaction database not found. Add a transaction to create it.")
        except Exception as e:
            st.sidebar.error(f"Error loading balances: {str(e)}")

        st.write("---")
        st.subheader("Manage Data")
        if st.button("Download all data"):
            download_zip_archive()
        if st.button("Load Mock Data"):
            load_mock_data()
            st.success("Mock data loaded. You may need to refresh the page.")

    # --- Tabbed Interface ---
    tab_names = ["Home", "Add Transaction", "View/Edit Transactions", "Add Client Expense", "Client Expense Summary", "Manage People", "Generate Invoice", "Generate Expense Bill", "Per Person Report"]
    home_tab, add_transaction_tab, view_edit_tab, add_client_expense_tab, client_expense_summary_tab, manage_people_tab, invoice_tab, bill_tab, report_tab = st.tabs(tab_names)

    with home_tab:
        st.session_state.current_tab = "Home"
        render_home_tab(df_people)

    with add_transaction_tab:
        st.session_state.current_tab = "Add Transaction"
        render_add_transaction_form(df_people)

    with view_edit_tab:
        st.session_state.current_tab = "View/Edit Transactions"
        render_view_edit_transactions_tab(df_people)

    with add_client_expense_tab:
        st.session_state.current_tab = "Add Client Expense"
        render_add_client_expense_form(df_people)

    with client_expense_summary_tab:
        st.session_state.current_tab = "Client Expense Summary"
        render_client_expense_summary_tab(df_people)

    with manage_people_tab:
        st.session_state.current_tab = "Manage People"
        render_manage_people_tab(df_people)

    with invoice_tab:
        st.session_state.current_tab = "Generate Invoice"
        render_generate_invoice_tab(df_people)

    with bill_tab:
        st.session_state.current_tab = "Generate Expense Bill"
        render_generate_bill_tab(df_people)

    with report_tab:
        st.session_state.current_tab = "Per Person Report"
        render_per_person_report_tab(df_people)

def render_home_tab(df_people):
    """Renders the Home tab with an overview."""
    st.header("Dashboard Overview")
    try:
        if os.path.exists(CSV_FILE):
            df = load_data(CSV_FILE, dtype={'reference_number': str})
            df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
            if not df.empty:
                total_paid = df[df['transaction_type'] == 'Paid']['amount'].sum()
                total_received = df[df['transaction_type'] == 'Received']['amount'].sum()
                net_balance = total_received - total_paid

                col1, col2, col3 = st.columns(3)
                col1.metric("Total Received", f"Rs. {total_received:,.2f}")
                col2.metric("Total Paid", f"Rs. {total_paid:,.2f}")
                col3.metric("Net Balance", f"Rs. {net_balance:,.2f}", delta_color="inverse")

                st.subheader("Transaction Summary")
                st.write(df.style.format({'amount': 'Rs. {:, .2f}'}))

                st.subheader("Payments by Person (Top 10)")
                person_summary = df.groupby('person')['amount'].sum().sort_values(ascending=False).head(10)
                fig, ax = plt.subplots()
                person_summary.plot(kind='bar', ax=ax)
                plt.ylabel("Total Amount")
                st.pyplot(fig)
                plt.close(fig)

                st.subheader("Payments by Type")
                type_summary = df.groupby('transaction_type')['amount'].sum()
                fig, ax = plt.subplots()
                type_summary.plot(kind='pie', autopct='%1.1f%%', ax=ax)
                plt.ylabel('')
                st.pyplot(fig)
                plt.close(fig)
            else:
                st.info("No transactions to display. Add some transactions to see the dashboard.")
        else:
            st.info("No transaction data found. Add your first transaction to get started.")

    except Exception as e:
        st.error(f"An error occurred while generating the dashboard: {e}")


def render_add_transaction_form(df_people):
    """Renders the form to add a new transaction."""
    st.header("Add New Transaction")
    try:
        with st.form("add_transaction_form", clear_on_submit=st.session_state.reset_add_form):
            st.session_state.reset_add_form = False

            col1, col2 = st.columns(2)
            with col1:
                st.session_state.selected_person = st.selectbox(
                    "Person",
                    options=sorted(df_people['name'].unique().tolist()),
                    key="add_person_selectbox"
                )
                st.session_state.add_amount = st.number_input(
                    "Amount (Rs.)", min_value=0.0, format="%.2f", key="add_amount_input"
                )
                st.session_state.add_reference_number = st.text_input(
                    "Reference Number", key="add_reference_number_input"
                )
                st.session_state.add_description = st.text_area(
                    "Description", key="add_description_input"
                )
            with col2:
                st.session_state.selected_transaction_type = st.radio(
                    "Transaction Type",
                    options=["Paid", "Received"],
                    key="add_transaction_type_radio"
                )
                st.session_state.payment_method = st.radio(
                    "Payment Method",
                    options=["Cash", "Cheque"],
                    key="add_payment_method_radio"
                )
                st.session_state.add_cheque_status = st.selectbox(
                    "Cheque Status",
                    options=["N/A", "Cleared", "Pending", "Bounced"],
                    disabled=st.session_state.payment_method == "Cash",
                    key="add_cheque_status_selectbox"
                )
                st.session_state.add_status = st.selectbox(
                    "Transaction Status",
                    options=["Completed", "Pending"],
                    key="add_status_selectbox"
                )
                st.session_state.add_date = st.date_input(
                    "Date", value=datetime.today(), key="add_date_input"
                )

            submitted = st.form_submit_button("Add Transaction")
            if submitted:
                add_transaction_logic(df_people)

    except Exception as e:
        st.error(f"Error rendering add transaction form: {e}")

def add_transaction_logic(df_people):
    """Handles the logic for adding a new transaction."""
    if st.session_state.add_amount <= 0:
        st.error("Amount must be greater than zero.")
        return

    try:
        df = load_data(CSV_FILE)
        new_row = pd.DataFrame([{
            'transaction_uuid': str(uuid.uuid4()),
            'transaction_type': st.session_state.selected_transaction_type,
            'person': st.session_state.selected_person,
            'payment_method': st.session_state.payment_method,
            'amount': st.session_state.add_amount,
            'date': st.session_state.add_date.isoformat(),
            'reference_number': st.session_state.add_reference_number,
            'status': st.session_state.add_status,
            'description': st.session_state.add_description,
            'cheque_status': st.session_state.add_cheque_status
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        save_data(df, CSV_FILE)
        st.success("Transaction added successfully!")
        st.session_state.reset_add_form = True
        st.experimental_rerun()
    except Exception as e:
        st.error(f"An error occurred while adding the transaction: {e}")

def render_view_edit_transactions_tab(df_people):
    """Renders the view and edit transactions tab."""
    st.header("View and Edit Transactions")
    try:
        df = load_data(CSV_FILE, dtype={'reference_number': str})
        if df.empty:
            st.info("No transactions found.")
            return

        col1, col2, col3 = st.columns([1, 1, 2])
        with col1:
            all_people_options = ['All'] + sorted(df_people['name'].unique().tolist())
            st.session_state.view_person_filter = st.selectbox("Filter by Person", options=all_people_options, key="view_person_filter_box")
        with col2:
            all_transaction_types = ['All'] + sorted(df['transaction_type'].unique().tolist())
            selected_type = st.selectbox("Filter by Type", options=all_transaction_types)
        with col3:
            st.session_state.view_reference_number_search = st.text_input("Search by Reference Number", key="view_ref_num_search_input")

        filtered_df = df.copy()
        if st.session_state.view_person_filter and st.session_state.view_person_filter != 'All':
            filtered_df = filtered_df[filtered_df['person'] == st.session_state.view_person_filter]
        if selected_type and selected_type != 'All':
            filtered_df = filtered_df[filtered_df['transaction_type'] == selected_type]
        if st.session_state.view_reference_number_search:
            search_text = st.session_state.view_reference_number_search.lower()
            filtered_df = filtered_df[
                filtered_df['reference_number'].str.lower().str.contains(search_text, na=False)
            ]

        if 'date' in filtered_df.columns:
            filtered_df['date'] = pd.to_datetime(filtered_df['date'], errors='coerce')
            filtered_df = filtered_df.sort_values(by='date', ascending=False)
        else:
            st.warning("Date column not found in data.")

        st.subheader("Transactions")
        transactions_to_display = filtered_df.drop(columns=['transaction_uuid'], errors='ignore')
        st.dataframe(transactions_to_display.style.format({'amount': 'Rs. {:, .2f}'}))

        st.subheader("Edit or Delete Transaction")
        transaction_indices = filtered_df.index.tolist()
        if not transaction_indices:
            st.info("No transactions match the selected filters.")
            return

        row_to_edit_idx = st.selectbox(
            "Select a row to edit or delete",
            options=transaction_indices,
            format_func=lambda idx: (
                f"{filtered_df.loc[idx, 'date'].strftime('%Y-%m-%d')} - "
                f"{filtered_df.loc[idx, 'person']} - "
                f"Rs. {filtered_df.loc[idx, 'amount']:,.2f} "
                f"({filtered_df.loc[idx, 'transaction_type']})"
            ),
            key="edit_select_box"
        )
        row_to_edit = filtered_df.loc[row_to_edit_idx]

        with st.form("edit_transaction_form"):
            col1, col2 = st.columns(2)
            with col1:
                edited_person = st.selectbox("Person", options=sorted(df_people['name'].unique().tolist()), index=sorted(df_people['name'].unique().tolist()).index(row_to_edit['person']))
                edited_amount = st.number_input("Amount (Rs.)", min_value=0.0, value=float(row_to_edit['amount']), format="%.2f")
                edited_ref_num = st.text_input("Reference Number", value=row_to_edit['reference_number'])
                edited_description = st.text_area("Description", value=row_to_edit['description'])
            with col2:
                edited_type = st.radio("Transaction Type", options=["Paid", "Received"], index=0 if row_to_edit['transaction_type'] == "Paid" else 1)
                edited_method = st.radio("Payment Method", options=["Cash", "Cheque"], index=0 if row_to_edit['payment_method'] == "Cash" else 1)
                cheque_status_options = ["N/A", "Cleared", "Pending", "Bounced"]
                edited_cheque_status = st.selectbox("Cheque Status", options=cheque_status_options, index=cheque_status_options.index(row_to_edit['cheque_status']), disabled=edited_method == "Cash")
                status_options = ["Completed", "Pending"]
                edited_status = st.selectbox("Transaction Status", options=status_options, index=status_options.index(row_to_edit['status']))
                edited_date = st.date_input("Date", value=pd.to_datetime(row_to_edit['date']).date())

            col_buttons = st.columns(2)
            with col_buttons[0]:
                edit_submitted = st.form_submit_button("Save Changes")
            with col_buttons[1]:
                delete_submitted = st.form_submit_button("Delete Transaction")

            if edit_submitted:
                df.loc[row_to_edit_idx, 'person'] = edited_person
                df.loc[row_to_edit_idx, 'amount'] = edited_amount
                df.loc[row_to_edit_idx, 'reference_number'] = edited_ref_num
                df.loc[row_to_edit_idx, 'description'] = edited_description
                df.loc[row_to_edit_idx, 'transaction_type'] = edited_type
                df.loc[row_to_edit_idx, 'payment_method'] = edited_method
                df.loc[row_to_edit_idx, 'cheque_status'] = edited_cheque_status
                df.loc[row_to_edit_idx, 'status'] = edited_status
                df.loc[row_to_edit_idx, 'date'] = edited_date.isoformat()
                save_data(df, CSV_FILE)
                st.success("Transaction updated successfully!")
                st.experimental_rerun()
            elif delete_submitted:
                df = df.drop(index=row_to_edit_idx).reset_index(drop=True)
                save_data(df, CSV_FILE)
                st.success("Transaction deleted successfully!")
                st.experimental_rerun()
    except Exception as e:
        st.error(f"Error rendering view/edit transactions tab: {e}")


def render_add_client_expense_form(df_people):
    """Renders the form to add a new client expense."""
    st.header("Add New Client Expense")
    try:
        client_names = df_people[df_people['person_type'] == 'client']['name'].tolist()
        if not client_names:
            st.warning("Please add at least one client in the 'Manage People' tab before adding expenses.")
            return

        with st.form("add_client_expense_form", clear_on_submit=st.session_state.reset_client_expense_form):
            st.session_state.reset_client_expense_form = False

            col1, col2 = st.columns(2)
            with col1:
                st.session_state.selected_client_for_expense = st.selectbox(
                    "Client", options=sorted(client_names), key="add_expense_client_selectbox"
                )
                st.session_state.add_client_expense_amount = st.number_input(
                    "Amount (Rs.)", min_value=0.0, format="%.2f", key="add_expense_amount_input"
                )
                st.session_state.add_client_expense_quantity = st.number_input(
                    "Quantity", min_value=0.0, format="%.2f", key="add_expense_quantity_input"
                )
                st.session_state.add_client_expense_description = st.text_area(
                    "Description", key="add_expense_description_input"
                )
            with col2:
                st.session_state.add_client_expense_category = st.text_input(
                    "Category", key="add_expense_category_input"
                )
                st.session_state.add_client_expense_status = st.selectbox(
                    "Expense Status", options=["Completed", "Pending"], key="add_expense_status_selectbox"
                )
                st.session_state.add_client_expense_date = st.date_input(
                    "Date", value=datetime.today(), key="add_expense_date_input"
                )
                st.session_state.add_client_expense_ref_num = st.text_input(
                    "Reference Number (Optional)", key="add_expense_ref_num_input"
                )

            submitted = st.form_submit_button("Add Client Expense")
            if submitted:
                add_client_expense_logic()

    except Exception as e:
        st.error(f"Error rendering add client expense form: {e}")

def add_client_expense_logic():
    """Handles the logic for adding a new client expense."""
    if st.session_state.add_client_expense_amount <= 0:
        st.error("Amount must be greater than zero.")
        return
    if not st.session_state.add_client_expense_category:
        st.error("Category cannot be empty.")
        return

    try:
        df_exp = load_data(CLIENT_EXPENSES_FILE)
        new_row = pd.DataFrame([{
            'expense_uuid': str(uuid.uuid4()),
            'original_transaction_ref_num': st.session_state.add_client_expense_ref_num,
            'expense_person': st.session_state.selected_client_for_expense,
            'expense_amount': st.session_state.add_client_expense_amount,
            'expense_quantity': st.session_state.add_client_expense_quantity,
            'expense_date': st.session_state.add_client_expense_date.isoformat(),
            'expense_category': st.session_state.add_client_expense_category,
            'expense_status': st.session_state.add_client_expense_status,
            'expense_description': st.session_state.add_client_expense_description,
            'expense_created_by': 'Admin' # Placeholder, can be replaced with a logged-in user
        }])
        df_exp = pd.concat([df_exp, new_row], ignore_index=True)
        save_data(df_exp, CLIENT_EXPENSES_FILE)
        st.success("Client expense added successfully!")
        st.session_state.reset_client_expense_form = True
        st.experimental_rerun()
    except Exception as e:
        st.error(f"An error occurred while adding the client expense: {e}")

def render_client_expense_summary_tab(df_people):
    """Renders the summary and management for client expenses."""
    st.header("Client Expenses Summary")
    try:
        df_exp = load_data(CLIENT_EXPENSES_FILE)
        if df_exp.empty:
            st.info("No client expenses found.")
            return

        filtered_client_expenses_for_display = pd.DataFrame()

        with st.expander("Filter Client Expenses"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                client_options = ['All'] + sorted(df_people[df_people['person_type'] == 'client']['name'].unique().tolist())
                selected_client = st.selectbox("Client", options=client_options, key="exp_sum_client_filter")
            with col2:
                category_options = ['All'] + sorted(df_exp['expense_category'].unique().tolist())
                selected_category = st.selectbox("Category", options=category_options, key="exp_sum_cat_filter")
            with col3:
                status_options = ['All'] + sorted(df_exp['expense_status'].unique().tolist())
                selected_status = st.selectbox("Status", options=status_options, key="exp_sum_status_filter")
            with col4:
                ref_num_search = st.text_input("Search Ref Number", key="exp_sum_ref_num_search")

            col5, col6 = st.columns(2)
            with col5:
                start_date_filter = st.date_input("Start Date", value=datetime.today() - pd.DateOffset(months=1), key="exp_sum_start_date")
            with col6:
                end_date_filter = st.date_input("End Date", value=datetime.today(), key="exp_sum_end_date")

        filtered_df_exp = df_exp.copy()

        if selected_client != 'All':
            filtered_df_exp = filtered_df_exp[filtered_df_exp['expense_person'] == selected_client]
        if selected_category != 'All':
            filtered_df_exp = filtered_df_exp[filtered_df_exp['expense_category'] == selected_category]
        if selected_status != 'All':
            filtered_df_exp = filtered_df_exp[filtered_df_exp['expense_status'] == selected_status]
        if ref_num_search:
            filtered_df_exp = filtered_df_exp[
                filtered_df_exp['original_transaction_ref_num'].str.contains(ref_num_search, case=False, na=False)
            ]

        filtered_df_exp['expense_date'] = pd.to_datetime(filtered_df_exp['expense_date'])
        filtered_df_exp = filtered_df_exp[
            (filtered_df_exp['expense_date'].dt.date >= start_date_filter) &
            (filtered_df_exp['expense_date'].dt.date <= end_date_filter)
        ]
        filtered_df_exp = filtered_df_exp.sort_values(by='expense_date', ascending=False)

        filtered_client_expenses_for_display = filtered_df_exp.drop(columns=['expense_uuid'], errors='ignore')
        st.subheader("Client Expenses")
        st.dataframe(filtered_client_expenses_for_display.style.format({
            'expense_amount': 'Rs. {:, .2f}',
            'expense_quantity': '{:, .2f}'
        }))

        if not filtered_client_expenses_for_display.empty:
            total_expenses = filtered_client_expenses_for_display['expense_amount'].sum()
            st.metric("Total Expenses in View", f"Rs. {total_expenses:,.2f}")

            st.subheader("Expenses by Category")
            category_summary = filtered_client_expenses_for_display.groupby('expense_category')['expense_amount'].sum().sort_values(ascending=False)
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.barplot(x=category_summary.index, y=category_summary.values, ax=ax)
            ax.set_title("Total Expenses by Category")
            ax.set_ylabel("Total Amount (Rs.)")
            ax.set_xlabel("Category")
            plt.xticks(rotation=45)
            st.pyplot(fig)
            plt.close(fig)

            st.subheader("Edit or Delete Client Expense")
            expense_indices = filtered_df_exp.index.tolist()
            if not expense_indices:
                st.info("No expenses match the selected filters.")
                return

            row_to_edit_idx = st.selectbox(
                "Select a row to edit or delete",
                options=expense_indices,
                format_func=lambda idx: (
                    f"{filtered_df_exp.loc[idx, 'expense_date'].strftime('%Y-%m-%d')} - "
                    f"{filtered_df_exp.loc[idx, 'expense_person']} - "
                    f"Rs. {filtered_df_exp.loc[idx, 'expense_amount']:,.2f} "
                    f"({filtered_df_exp.loc[idx, 'expense_category']})"
                ),
                key="edit_expense_select_box"
            )
            row_to_edit = filtered_df_exp.loc[row_to_edit_idx]

            with st.form("edit_client_expense_form"):
                col1, col2 = st.columns(2)
                with col1:
                    edited_client = st.selectbox("Client", options=client_options[1:], index=client_options[1:].index(row_to_edit['expense_person']))
                    edited_amount = st.number_input("Amount (Rs.)", min_value=0.0, value=float(row_to_edit['expense_amount']), format="%.2f")
                    edited_quantity = st.number_input("Quantity", min_value=0.0, value=float(row_to_edit['expense_quantity']), format="%.2f")
                    edited_description = st.text_area("Description", value=row_to_edit['expense_description'])
                with col2:
                    edited_category = st.text_input("Category", value=row_to_edit['expense_category'])
                    status_options = ["Completed", "Pending"]
                    edited_status = st.selectbox("Status", options=status_options, index=status_options.index(row_to_edit['expense_status']))
                    edited_date = st.date_input("Date", value=pd.to_datetime(row_to_edit['expense_date']).date())
                    edited_ref_num = st.text_input("Reference Number (Optional)", value=row_to_edit['original_transaction_ref_num'])

                col_buttons = st.columns(2)
                with col_buttons[0]:
                    edit_submitted = st.form_submit_button("Save Changes")
                with col_buttons[1]:
                    delete_submitted = st.form_submit_button("Delete Expense")

                if edit_submitted:
                    df_exp.loc[row_to_edit_idx, 'expense_person'] = edited_client
                    df_exp.loc[row_to_edit_idx, 'expense_amount'] = edited_amount
                    df_exp.loc[row_to_edit_idx, 'expense_quantity'] = edited_quantity
                    df_exp.loc[row_to_edit_idx, 'expense_description'] = edited_description
                    df_exp.loc[row_to_edit_idx, 'expense_category'] = edited_category
                    df_exp.loc[row_to_edit_idx, 'expense_status'] = edited_status
                    df_exp.loc[row_to_edit_idx, 'expense_date'] = edited_date.isoformat()
                    df_exp.loc[row_to_edit_idx, 'original_transaction_ref_num'] = edited_ref_num
                    save_data(df_exp, CLIENT_EXPENSES_FILE)
                    st.success("Client expense updated successfully!")
                    st.experimental_rerun()
                elif delete_submitted:
                    df_exp = df_exp.drop(index=row_to_edit_idx).reset_index(drop=True)
                    save_data(df_exp, CLIENT_EXPENSES_FILE)
                    st.success("Client expense deleted successfully!")
                    st.experimental_rerun()
    except Exception as e:
        st.error(f"Error loading client expenses summary: {e}")


def render_manage_people_tab(df_people):
    """Renders the tab to manage clients and other people."""
    st.header("Manage People")
    st.write("Add or remove people (clients, partners, etc.) involved in transactions.")

    if not df_people.empty:
        st.subheader("Existing People")
        df_people_display = df_people.sort_values(by=['person_type', 'name']).reset_index(drop=True)
        st.dataframe(df_people_display)

    st.subheader("Add New Person")
    with st.form("add_person_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            person_name = st.text_input("Person's Name", key="new_person_name")
        with col2:
            person_type = st.selectbox("Person Type", options=["client", "vendor", "other"], key="new_person_type")

        submitted = st.form_submit_button("Add Person")
        if submitted:
            if person_name:
                add_person_logic(person_name, person_type, df_people)
            else:
                st.error("Person's name cannot be empty.")

    if not df_people.empty:
        st.subheader("Remove Person")
        with st.form("remove_person_form"):
            person_to_remove = st.selectbox(
                "Select a person to remove",
                options=df_people['name'].unique().tolist(),
                key="remove_person_selectbox"
            )
            remove_submitted = st.form_submit_button("Remove Person")
            if remove_submitted:
                remove_person_logic(person_to_remove, df_people)


def add_person_logic(person_name, person_type, df_people):
    """Handles the logic for adding a new person."""
    if person_name in df_people['name'].values:
        st.error(f"A person named '{person_name}' already exists.")
    else:
        new_person = pd.DataFrame([{'name': person_name, 'person_type': person_type}])
        updated_df = pd.concat([df_people, new_person], ignore_index=True)
        save_data(updated_df, PEOPLE_FILE)
        st.success(f"Person '{person_name}' added successfully as a {person_type}.")
        st.experimental_rerun()

def remove_person_logic(person_to_remove, df_people):
    """Handles the logic for removing a person."""
    try:
        updated_df = df_people[df_people['name'] != person_to_remove].reset_index(drop=True)
        save_data(updated_df, PEOPLE_FILE)
        st.success(f"Person '{person_to_remove}' removed successfully.")
        st.experimental_rerun()
    except Exception as e:
        st.error(f"An error occurred while removing the person: {e}")

def render_generate_invoice_tab(df_people):
    """Renders the tab to generate a PDF invoice."""
    st.header("Generate Invoice")
    st.write("Create a PDF invoice for a client based on transactions and expenses within a date range.")
    try:
        with st.form("invoice_form"):
            client_names = df_people[df_people['person_type'] == 'client']['name'].unique().tolist()
            if not client_names:
                st.warning("Please add at least one client in the 'Manage People' tab.")
                return

            st.session_state.invoice_person_name = st.selectbox("Client Name", options=sorted(client_names))
            st.session_state.invoice_type = st.radio("Invoice Type", options=["All", "Received", "Paid"])
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.invoice_start_date = st.date_input("Start Date", value=datetime.today() - pd.DateOffset(months=1))
            with col2:
                st.session_state.invoice_end_date = st.date_input("End Date", value=datetime.today())

            generate_button = st.form_submit_button("Generate Invoice")

            if generate_button:
                df_payments = load_data(CSV_FILE)
                df_expenses = load_data(CLIENT_EXPENSES_FILE)

                df_payments['date'] = pd.to_datetime(df_payments['date']).dt.date
                filtered_payments = df_payments[
                    (df_payments['person'] == st.session_state.invoice_person_name) &
                    (df_payments['date'] >= st.session_state.invoice_start_date) &
                    (df_payments['date'] <= st.session_state.invoice_end_date)
                ]
                if st.session_state.invoice_type != "All":
                    filtered_payments = filtered_payments[
                        filtered_payments['transaction_type'] == st.session_state.invoice_type
                    ]

                df_expenses['expense_date'] = pd.to_datetime(df_expenses['expense_date']).dt.date
                filtered_expenses = df_expenses[
                    (df_expenses['expense_person'] == st.session_state.invoice_person_name) &
                    (df_expenses['expense_date'] >= st.session_state.invoice_start_date) &
                    (df_expenses['expense_date'] <= st.session_state.invoice_end_date)
                ]

                if not filtered_payments.empty or not filtered_expenses.empty:
                    pdf_output = create_invoice_pdf(
                        st.session_state.invoice_person_name,
                        st.session_state.invoice_start_date,
                        st.session_state.invoice_end_date,
                        filtered_payments,
                        filtered_expenses
                    )
                    st.session_state.generated_invoice_pdf_path = pdf_output
                    st.session_state.show_download_button = True
                else:
                    st.warning("No transactions or expenses found for the selected criteria.")
                    st.session_state.show_download_button = False

        if st.session_state.show_download_button and st.session_state.generated_invoice_pdf_path:
            with open(st.session_state.generated_invoice_pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="Download Invoice PDF",
                    data=pdf_file,
                    file_name=os.path.basename(st.session_state.generated_invoice_pdf_path),
                    mime="application/pdf"
                )
    except Exception as e:
        st.error(f"Error generating invoice: {e}")

def create_invoice_pdf(client_name, start_date, end_date, payments_df, expenses_df):
    """Creates a PDF invoice and saves it to a temporary file."""
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Fin-Tracker Invoice', 0, 1, 'C')
            self.ln(10)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    pdf = PDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Invoice for: {client_name}", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f"Period: {start_date} to {end_date}", 0, 1)
    pdf.ln(5)

    if not payments_df.empty:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Transactions", 0, 1)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(30, 7, 'Date', 1)
        pdf.cell(20, 7, 'Type', 1)
        pdf.cell(30, 7, 'Amount', 1)
        pdf.cell(70, 7, 'Description', 1)
        pdf.cell(30, 7, 'Status', 1)
        pdf.ln()

        pdf.set_font('Arial', '', 10)
        for index, row in payments_df.iterrows():
            pdf.cell(30, 7, str(row['date']), 1)
            pdf.cell(20, 7, row['transaction_type'], 1)
            pdf.cell(30, 7, f"Rs. {float(row['amount']):,.2f}", 1)
            pdf.cell(70, 7, row['description'], 1, align='L')
            pdf.cell(30, 7, row['status'], 1)
            pdf.ln()
        pdf.ln(5)

    if not expenses_df.empty:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Client Expenses", 0, 1)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(30, 7, 'Date', 1)
        pdf.cell(30, 7, 'Category', 1)
        pdf.cell(30, 7, 'Amount', 1)
        pdf.cell(30, 7, 'Quantity', 1)
        pdf.cell(60, 7, 'Description', 1)
        pdf.ln()

        pdf.set_font('Arial', '', 10)
        for index, row in expenses_df.iterrows():
            pdf.cell(30, 7, str(row['expense_date']), 1)
            pdf.cell(30, 7, row['expense_category'], 1)
            pdf.cell(30, 7, f"Rs. {float(row['expense_amount']):,.2f}", 1)
            pdf.cell(30, 7, str(row['expense_quantity']), 1)
            pdf.cell(60, 7, row['expense_description'], 1, align='L')
            pdf.ln()
        pdf.ln(5)

    total_received = payments_df[payments_df['transaction_type'] == 'Received']['amount'].sum() if not payments_df.empty else 0
    total_paid = payments_df[payments_df['transaction_type'] == 'Paid']['amount'].sum() if not payments_df.empty else 0
    total_expenses = expenses_df['expense_amount'].sum() if not expenses_df.empty else 0
    net_balance = total_received - total_paid - total_expenses

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "Summary", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 7, f"Total Received: Rs. {total_received:,.2f}", 0, 1)
    pdf.cell(0, 7, f"Total Paid: Rs. {total_paid:,.2f}", 0, 1)
    pdf.cell(0, 7, f"Total Client Expenses: Rs. {total_expenses:,.2f}", 0, 1)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 7, f"Net Balance: Rs. {net_balance:,.2f}", 0, 1)

    temp_file = f"invoice_{client_name}_{uuid.uuid4()}.pdf"
    pdf.output(temp_file)
    return temp_file

# --- New Function for Bill Generation ---
def render_generate_bill_tab(df_people):
    """Renders the tab to generate a bill for client expenses."""
    st.header("Generate Expense Bill")
    st.write("Create a bill for a client based *only* on their tracked expenses within a date range.")
    try:
        client_names = df_people[df_people['person_type'] == 'client']['name'].unique().tolist()
        if not client_names:
            st.warning("Please add at least one client in the 'Manage People' tab.")
            return

        with st.form("bill_form"):
            st.session_state.bill_client_name = st.selectbox("Client Name", options=sorted(client_names))
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.bill_start_date = st.date_input("Start Date", value=datetime.today() - pd.DateOffset(months=1))
            with col2:
                st.session_state.bill_end_date = st.date_input("End Date", value=datetime.today())
            
            generate_button = st.form_submit_button("Generate Bill")

            if generate_button:
                df_expenses = load_data(CLIENT_EXPENSES_FILE)

                df_expenses['expense_date'] = pd.to_datetime(df_expenses['expense_date']).dt.date
                filtered_expenses = df_expenses[
                    (df_expenses['expense_person'] == st.session_state.bill_client_name) &
                    (df_expenses['expense_date'] >= st.session_state.bill_start_date) &
                    (df_expenses['expense_date'] <= st.session_state.bill_end_date)
                ]

                if not filtered_expenses.empty:
                    pdf_output = create_expense_bill_pdf(
                        st.session_state.bill_client_name,
                        st.session_state.bill_start_date,
                        st.session_state.bill_end_date,
                        filtered_expenses
                    )
                    st.session_state.generated_bill_pdf_path = pdf_output
                    st.session_state.show_bill_download_button = True
                else:
                    st.warning("No client expenses found for the selected criteria.")
                    st.session_state.show_bill_download_button = False

        if st.session_state.show_bill_download_button and st.session_state.generated_bill_pdf_path:
            with open(st.session_state.generated_bill_pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="Download Expense Bill PDF",
                    data=pdf_file,
                    file_name=os.path.basename(st.session_state.generated_bill_pdf_path),
                    mime="application/pdf"
                )
    except Exception as e:
        st.error(f"Error generating expense bill: {e}")

def create_expense_bill_pdf(client_name, start_date, end_date, expenses_df):
    """Creates a PDF bill for client expenses and saves it to a temporary file."""
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 15)
            self.cell(0, 10, 'Client Expense Bill', 0, 1, 'C')
            self.ln(10)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

    pdf = PDF('P', 'mm', 'A4')
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Bill for: {client_name}", 0, 1)
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, f"Period: {start_date} to {end_date}", 0, 1)
    pdf.ln(5)

    if not expenses_df.empty:
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, "Client Expenses", 0, 1)
        pdf.set_font('Arial', 'B', 10)
        pdf.cell(30, 7, 'Date', 1)
        pdf.cell(30, 7, 'Category', 1)
        pdf.cell(30, 7, 'Amount', 1)
        pdf.cell(30, 7, 'Quantity', 1)
        pdf.cell(60, 7, 'Description', 1)
        pdf.ln()

        pdf.set_font('Arial', '', 10)
        for index, row in expenses_df.iterrows():
            pdf.cell(30, 7, str(row['expense_date']), 1)
            pdf.cell(30, 7, row['expense_category'], 1)
            pdf.cell(30, 7, f"Rs. {float(row['expense_amount']):,.2f}", 1)
            pdf.cell(30, 7, str(row['expense_quantity']), 1)
            pdf.cell(60, 7, row['expense_description'], 1, align='L')
            pdf.ln()
        pdf.ln(5)
    else:
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 10, "No expenses found for this client in the selected period.", 0, 1)
        pdf.ln(5)


    total_expenses = expenses_df['expense_amount'].sum() if not expenses_df.empty else 0

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "Summary", 0, 1)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 7, f"Total Amount Due: Rs. {total_expenses:,.2f}", 0, 1)

    temp_file = f"bill_{client_name}_{uuid.uuid4()}.pdf"
    pdf.output(temp_file)
    return temp_file

def render_per_person_report_tab(df_people):
    """Renders a detailed report for a selected person."""
    st.header("Per Person Report")
    st.write("Generate a detailed financial report for a specific person, including transactions and client expenses.")
    try:
        client_names = df_people['name'].unique().tolist()
        if not client_names:
            st.warning("Please add at least one person in the 'Manage People' tab.")
            return

        with st.form("per_person_report_form"):
            st.session_state.selected_per_person_report_person = st.selectbox(
                "Select Person",
                options=sorted(client_names),
                key="report_person_selectbox"
            )
            col1, col2 = st.columns(2)
            with col1:
                st.session_state.per_person_report_start_date = st.date_input(
                    "Start Date",
                    value=datetime.today() - pd.DateOffset(months=1),
                    key="report_start_date"
                )
            with col2:
                st.session_state.per_person_report_end_date = st.date_input(
                    "End Date",
                    value=datetime.today(),
                    key="report_end_date"
                )

            generate_report_button = st.form_submit_button("Generate Report")

        if generate_report_button:
            df_payments = load_data(CSV_FILE)
            df_expenses = load_data(CLIENT_EXPENSES_FILE)

            person = st.session_state.selected_per_person_report_person
            start_date = st.session_state.per_person_report_start_date
            end_date = st.session_state.per_person_report_end_date

            filtered_payments = df_payments[
                (df_payments['person'] == person) &
                (pd.to_datetime(df_payments['date']).dt.date >= start_date) &
                (pd.to_datetime(df_payments['date']).dt.date <= end_date)
            ].copy()
            filtered_payments['amount'] = pd.to_numeric(filtered_payments['amount'], errors='coerce').fillna(0.0)

            filtered_expenses = df_expenses[
                (df_expenses['expense_person'] == person) &
                (pd.to_datetime(df_expenses['expense_date']).dt.date >= start_date) &
                (pd.to_datetime(df_expenses['expense_date']).dt.date <= end_date)
            ].copy()
            filtered_expenses['expense_amount'] = pd.to_numeric(filtered_expenses['expense_amount'], errors='coerce').fillna(0.0)

            st.subheader(f"Report for {person} from {start_date} to {end_date}")

            if not filtered_payments.empty:
                st.subheader("Transactions")
                st.dataframe(filtered_payments)
                total_received = filtered_payments[filtered_payments['transaction_type'] == 'Received']['amount'].sum()
                total_paid = filtered_payments[filtered_payments['transaction_type'] == 'Paid']['amount'].sum()
                st.metric("Total Received", f"Rs. {total_received:,.2f}")
                st.metric("Total Paid", f"Rs. {total_paid:,.2f}")
            else:
                st.info("No transactions found for this person in the selected date range.")

            if not filtered_expenses.empty:
                st.subheader("Client Expenses")
                st.dataframe(filtered_expenses)
                total_expenses = filtered_expenses['expense_amount'].sum()
                st.metric("Total Client Expenses", f"Rs. {total_expenses:,.2f}")
            else:
                st.info("No client expenses found for this person in the selected date range.")

            if not filtered_payments.empty or not filtered_expenses.empty:
                st.subheader("Financial Summary")
                total_received = filtered_payments['amount'].sum() if not filtered_payments.empty else 0
                total_expenses = filtered_expenses['expense_amount'].sum() if not filtered_expenses.empty else 0
                net_balance = total_received - total_expenses
                st.metric("Net Financial Position", f"Rs. {net_balance:,.2f}", delta_color="inverse")
    except Exception as e:
        st.error(f"Error generating per person report: {e}")

def download_zip_archive():
    """Compresses all CSV files into a zip archive and provides a download link."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED) as zip_file:
        for file_name in [CSV_FILE, CLIENTS_FILE, CLIENT_EXPENSES_FILE, PEOPLE_FILE]:
            if os.path.exists(file_name):
                zip_file.write(file_name, arcname=os.path.basename(file_name))
    zip_buffer.seek(0)
    st.download_button(
        label="Download All Data as ZIP",
        data=zip_buffer,
        file_name="fin_tracker_data.zip",
        mime="application/zip"
    )

def load_mock_data():
    """Generates and saves mock data for testing purposes."""
    from faker import Faker
    fake = Faker('en_PK')
    num_entries = 50

    people = [fake.name() for _ in range(10)]
    person_types = ['client'] * 5 + ['vendor'] * 3 + ['other'] * 2
    mock_people_df = pd.DataFrame({'name': people, 'person_type': person_types})
    save_data(mock_people_df, PEOPLE_FILE)

    mock_payments = []
    for _ in range(num_entries):
        transaction_type = np.random.choice(['Received', 'Paid'])
        person = np.random.choice(people)
        payment_method = np.random.choice(['Cash', 'Cheque'])
        amount = round(np.random.uniform(1000, 50000), 2)
        date = fake.date_between(start_date='-60d', end_date='today').isoformat()
        ref_num = fake.bothify(text='??-####-####') if np.random.rand() > 0.5 else ''
        status = np.random.choice(['Completed', 'Pending'])
        description = fake.sentence(nb_words=5)
        cheque_status = 'N/A'
        if payment_method == 'Cheque':
            cheque_status = np.random.choice(['Cleared', 'Pending', 'Bounced'])

        mock_payments.append({
            'transaction_uuid': str(uuid.uuid4()),
            'transaction_type': transaction_type,
            'person': person,
            'payment_method': payment_method,
            'amount': amount,
            'date': date,
            'reference_number': ref_num,
            'status': status,
            'description': description,
            'cheque_status': cheque_status
        })
    mock_payments_df = pd.DataFrame(mock_payments)
    save_data(mock_payments_df, CSV_FILE)

    client_names = mock_people_df[mock_people_df['person_type'] == 'client']['name'].unique().tolist()
    expense_categories = ['Travel', 'Materials', 'Labor', 'Subcontractor', 'Miscellaneous']
    mock_expenses = []
    for _ in range(num_entries // 2):
        person = np.random.choice(client_names)
        amount = round(np.random.uniform(500, 10000), 2)
        quantity = round(np.random.uniform(1, 10), 2)
        date = fake.date_between(start_date='-60d', end_date='today').isoformat()
        category = np.random.choice(expense_categories)
        status = np.random.choice(['Completed', 'Pending'])
        description = fake.sentence(nb_words=5)
        ref_num = fake.bothify(text='EXP-##-####') if np.random.rand() > 0.5 else ''
        mock_expenses.append({
            'expense_uuid': str(uuid.uuid4()),
            'original_transaction_ref_num': ref_num,
            'expense_person': person,
            'expense_amount': amount,
            'expense_quantity': quantity,
            'expense_date': date,
            'expense_category': category,
            'expense_status': status,
            'expense_description': description,
            'expense_created_by': 'Admin'
        })
    mock_expenses_df = pd.DataFrame(mock_expenses)
    save_data(mock_expenses_df, CLIENT_EXPENSES_FILE)

    st.success("Mock data generated and saved.")


if __name__ == '__main__':
    create_app()
