import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
from git import Repo
import numpy as np
import uuid
from fpdf import FPDF
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO
import zipfile

# --- Global Constants and Initialization ---
REPO_PATH = os.getcwd()
CSV_FILE = os.path.join(REPO_PATH, "payments.csv")
PEOPLE_FILE = os.path.join(REPO_PATH, "people.csv")
CLIENT_EXPENSES_FILE = os.path.join(REPO_PATH, "client_expenses.csv")
SUMMARY_FILE = os.path.join(REPO_PATH, "docs/index.html")
SUMMARY_URL = "https://atonomous.github.io/payments-summary/"
INVOICE_DIR = os.path.join(REPO_PATH, "docs", "invoices")
BILL_DIR = os.path.join(REPO_PATH, "docs", "bills")

# Create necessary directories
os.makedirs(INVOICE_DIR, exist_ok=True)
os.makedirs(BILL_DIR, exist_ok=True)
os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)

# Define valid data options
valid_cheque_statuses_lower = ["received/given", "processing", "bounced", "processing done"]
valid_transaction_statuses_lower = ["completed", "pending"]
valid_expense_categories = ["General", "Salaries", "Rent", "Utilities", "Supplies", "Travel", "Other"]
CLIENT_EXPENSE_COLUMNS = [
    'expense_uuid', 'original_transaction_ref_num', 'expense_person', 'expense_amount',
    'expense_quantity', 'expense_date', 'expense_category', 'expense_status',
    'expense_description', 'expense_created_by'
]

# --- Helper Functions for Data Loading/Saving ---
def load_data(file_path, **kwargs):
    """Loads data from a CSV file, handling empty or non-existent files gracefully."""
    # Check if the file exists and is not empty
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        # Return an empty DataFrame with expected columns if file doesn't exist
        if file_path == CSV_FILE:
            return pd.DataFrame(columns=[
                "date", "person", "amount", "type", "status",
                "description", "payment_method", "reference_number",
                "cheque_status", "transaction_status"
            ])
        elif file_path == PEOPLE_FILE:
            return pd.DataFrame(columns=["name", "category"])
        elif file_path == CLIENT_EXPENSES_FILE:
            return pd.DataFrame(columns=CLIENT_EXPENSE_COLUMNS)
        return pd.DataFrame()
    try:
        df = pd.read_csv(file_path, **kwargs)
        # Ensure all columns are treated as strings to avoid issues with mixed types
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str)
        return df
    except pd.errors.EmptyDataError:
        st.warning(f"The file {os.path.basename(file_path)} is empty. Returning an empty DataFrame.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading {os.path.basename(file_path)}: {e}")
        return pd.DataFrame()

def save_data(df, file_path):
    """Saves a DataFrame to a CSV file."""
    try:
        df.to_csv(file_path, index=False)
    except Exception as e:
        st.error(f"Error saving data to {os.path.basename(file_path)}: {e}")

# --- Data Cleaning and Initialization Functions ---
def clean_payments_data(df):
    """Cleans and standardizes payments DataFrame."""
    if df.empty:
        return df

    # Ensure all expected columns exist
    expected_cols = [
        "date", "person", "amount", "type", "status",
        "description", "payment_method", "reference_number",
        "cheque_status", "transaction_status"
    ]
    for col in expected_cols:
        if col not in df.columns:
            df[col] = ''

    # Clean string columns, replacing NaNs and 'None' with empty strings
    for col in ["payment_method", "cheque_status", "transaction_status", "reference_number", "description", "person", "type", "status"]:
        df[col] = df[col].astype(str).replace('nan', '').replace('None', '').str.strip().str.lower()

    # Convert to correct data types
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # Enforce valid statuses
    df['transaction_status'] = df['transaction_status'].apply(
        lambda x: x if x in valid_transaction_statuses_lower else 'completed'
    )
    df['cheque_status'] = df.apply(
        lambda row: row['cheque_status'] if row['payment_method'] == 'cheque' and row['cheque_status'] in valid_cheque_statuses_lower else '',
        axis=1
    )

    # Remove rows that are entirely empty
    df = df.dropna(subset=['date', 'person', 'amount'], how='all')
    return df

def clean_expenses_data(df):
    """Cleans and standardizes client expenses DataFrame."""
    if df.empty:
        return df

    for col in CLIENT_EXPENSE_COLUMNS:
        if col not in df.columns:
            df[col] = ''

    df['expense_uuid'] = df['expense_uuid'].apply(
        lambda x: str(uuid.uuid4()) if pd.isna(x) or str(x).strip().lower() == 'nan' or not x else x
    )
    df['original_transaction_ref_num'] = df['original_transaction_ref_num'].astype(str).replace('nan', '').replace('None', '').str.strip()
    df['expense_amount'] = pd.to_numeric(df['expense_amount'], errors='coerce').fillna(0.0)
    df['expense_quantity'] = pd.to_numeric(df['expense_quantity'], errors='coerce').fillna(1.0)
    df['expense_date'] = pd.to_datetime(df['expense_date'], errors='coerce')
    df['expense_category'] = df['expense_category'].apply(lambda x: x if x in valid_expense_categories else 'General')
    df['expense_status'] = df['expense_status'].apply(lambda x: x if x in valid_transaction_statuses_lower else 'completed')
    df['total_line_amount'] = df['expense_amount'] * df['expense_quantity']

    df = df[CLIENT_EXPENSE_COLUMNS + ['total_line_amount']]
    return df

def init_files():
    """Initializes all necessary CSV files on app start."""
    try:
        # Initialize payments.csv
        payments_df = load_data(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
        payments_df = clean_payments_data(payments_df)
        save_data(payments_df, CSV_FILE)

        # Initialize people.csv
        people_df = load_data(PEOPLE_FILE)
        if 'category' not in people_df.columns:
            people_df['category'] = 'client'
        save_data(people_df, PEOPLE_FILE)

        # Initialize client_expenses.csv
        expenses_df = load_data(CLIENT_EXPENSES_FILE, keep_default_na=False)
        expenses_df = clean_expenses_data(expenses_df)
        save_data(expenses_df, CLIENT_EXPENSES_FILE)

    except Exception as e:
        st.error(f"Error during file initialization: {e}")

# --- Session State Management ---
def init_state():
    """Initializes session state variables for the app."""
    defaults = {
        'current_tab': 'Home',
        'editing_row_idx': None,
        'temp_edit_data': {},
        'editing_client_expense_idx': None,
        'temp_edit_client_expense_data': {},
        'people_df': pd.DataFrame(columns=["name", "category"]),
        'view_person_filter': "All",
        'selected_per_person_report_person': "Select...",
        'per_person_report_start_date': date.today().replace(day=1),
        'per_person_report_end_date': date.today(),
        'selected_per_person_report_tab': 'Transactions',
        'invoice_person_name': "Select...",
        'invoice_start_date': date.today().replace(day=1),
        'invoice_end_date': date.today(),
        'generated_invoice_pdf_path': None,
        'show_download_button': False,
        'bill_client_name': "Select...",
        'bill_start_date': date.today().replace(day=1),
        'bill_end_date': date.today(),
        'generated_bill_pdf_path': None,
        'show_bill_download_button': False,
        'client_expense_filter_person': "All",
        'client_expense_filter_category': "All"
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# --- Git Integration ---
def git_push():
    """Commits and pushes changes to GitHub."""
    try:
        repo = Repo(REPO_PATH)
        if repo.is_dirty(untracked_files=True):
            repo.git.add(update=True)
            repo.git.add(all=True)
        if repo.index.diff("HEAD"):
            repo.index.commit("Automated update: financial records")
        else:
            st.info("No changes to commit.")
            return True
        origin = repo.remote(name='origin')
        origin.push()
        st.success("GitHub updated successfully!")
        return True
    except Exception as e:
        st.error(f"Error updating GitHub: {e}")
        return False

# --- PDF Generation Functions ---
class PDF(FPDF):
    """Custom FPDF class for report generation."""
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, self.title, 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def chapter_title(self, title_str):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 6, title_str, 0, 1, 'L')
        self.ln(4)

    def chapter_body(self, data, total_label=None):
        self.set_font('Arial', '', 10)
        if data.empty:
            self.cell(0, 10, "No data available for this section.", 0, 1)
            self.ln(4)
            return

        col_widths = [self.w / (len(data.columns) + 1)] * len(data.columns)

        # Table Header
        self.set_fill_color(200, 220, 255)
        self.set_font('Arial', 'B', 10)
        for header in data.columns:
            self.cell(col_widths[0], 7, str(header), 1, 0, 'C', 1)
        self.ln()

        # Table Rows
        self.set_font('Arial', '', 10)
        for row in data.itertuples(index=False):
            for item in row:
                self.cell(col_widths[0], 6, str(item), 1, 0, 'L')
            self.ln()
        self.ln(2)

        # Total
        if total_label and ('amount' in data.columns or 'total_line_amount' in data.columns):
            total_col = 'amount' if 'amount' in data.columns else 'total_line_amount'
            total = data[total_col].sum()
            self.set_font('Arial', 'B', 10)
            self.cell(0, 6, f'{total_label}: Rs. {total:,.2f}', 0, 1, 'R')
        self.ln(5)

def generate_pdf(title, header_text, sections, file_path):
    """
    Generates a PDF report with multiple sections.
    sections is a list of tuples: (section_title, dataframe, total_label)
    """
    pdf = PDF('P', 'mm', 'A4')
    pdf.set_title(title)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('Arial', '', 12)
    pdf.multi_cell(0, 8, header_text)
    pdf.ln(10)

    for section_title, df_section, total_label in sections:
        df_section_display = df_section.copy()
        if 'date' in df_section_display.columns:
            df_section_display['date'] = df_section_display['date'].dt.strftime('%Y-%m-%d')
        if 'expense_date' in df_section_display.columns:
            df_section_display['expense_date'] = df_section_display['expense_date'].dt.strftime('%Y-%m-%d')
        if 'amount' in df_section_display.columns:
            df_section_display['amount'] = df_section_display['amount'].apply(lambda x: f"Rs. {x:,.2f}")
        if 'total_line_amount' in df_section_display.columns:
             df_section_display['total_line_amount'] = df_section_display['total_line_amount'].apply(lambda x: f"Rs. {x:,.2f}")

        pdf.chapter_title(section_title)
        pdf.chapter_body(df_section_display, total_label)

    pdf.output(file_path)

def generate_invoice_pdf(payments_df, expenses_df, person_name, start_date, end_date):
    """Generates a PDF invoice for a specific person within a date range."""
    file_path = os.path.join(INVOICE_DIR, f"invoice_{person_name}_{uuid.uuid4().hex}.pdf")
    
    # Filter payments and expenses for the invoice
    payments = payments_df[
        (payments_df['person'] == person_name) &
        (payments_df['date'] >= pd.to_datetime(start_date)) &
        (payments_df['date'] <= pd.to_datetime(end_date))
    ]
    expenses = expenses_df[
        (expenses_df['expense_person'] == person_name) &
        (expenses_df['expense_date'] >= pd.to_datetime(start_date)) &
        (expenses_df['expense_date'] <= pd.to_datetime(end_date))
    ]

    received_payments = payments[payments['type'] == 'paid_to_me']
    paid_payments = payments[payments['type'] == 'i_paid']
    
    # Calculate totals
    total_received = received_payments['amount'].sum()
    total_paid = paid_payments['amount'].sum()
    total_expenses = expenses['total_line_amount'].sum()
    net_balance = total_received - (total_paid + total_expenses)

    header_text = f"This invoice summarizes the financial transactions for {person_name} from {start_date} to {end_date}.\n\n"
    header_text += f"Total Received from {person_name}: Rs. {total_received:,.2f}\n"
    header_text += f"Total Paid to {person_name}: Rs. {total_paid:,.2f}\n"
    header_text += f"Total Expenses by {person_name}: Rs. {total_expenses:,.2f}\n"
    header_text += f"Net Balance: Rs. {net_balance:,.2f}"

    sections = [
        ('Received Payments', received_payments[['date', 'description', 'amount', 'reference_number']], 'Total Received'),
        ('Payments to Person', paid_payments[['date', 'description', 'amount', 'reference_number']], 'Total Paid'),
        ('Client Expenses', expenses[['expense_date', 'expense_category', 'expense_description', 'expense_amount', 'expense_quantity', 'total_line_amount']], 'Total Expenses')
    ]
    
    generate_pdf(f"Invoice for {person_name}", header_text, sections, file_path)
    return file_path

def generate_bill_pdf(expenses_df, client_name, start_date, end_date):
    """Generates a PDF bill for a specific client within a date range."""
    file_path = os.path.join(BILL_DIR, f"bill_{client_name}_{uuid.uuid4().hex}.pdf")
    
    expenses = expenses_df[
        (expenses_df['expense_person'] == client_name) &
        (expenses_df['expense_date'] >= pd.to_datetime(start_date)) &
        (expenses_df['expense_date'] <= pd.to_datetime(end_date))
    ]
    
    total_bill_amount = expenses['total_line_amount'].sum()

    header_text = f"This bill details all expenses incurred for client {client_name} from {start_date} to {end_date}.\n\n"
    header_text += f"Total Bill Amount: Rs. {total_bill_amount:,.2f}"

    sections = [
        ('Expenses for Client', expenses[['expense_date', 'expense_category', 'expense_description', 'expense_amount', 'expense_quantity', 'total_line_amount']], 'Total Bill Amount')
    ]
    
    generate_pdf(f"Bill for {client_name}", header_text, sections, file_path)
    return file_path

# --- Report and Summary Generation ---
def generate_per_person_report(payments_df, expenses_df, person_name, start_date, end_date, tab):
    """Generates and displays a detailed report for a single person."""
    st.subheader(f"Report for {person_name}")
    st.markdown(f"**Date Range:** {start_date} to {end_date}")

    filtered_payments = payments_df[
        (payments_df['person'] == person_name) &
        (payments_df['date'] >= pd.to_datetime(start_date)) &
        (payments_df['date'] <= pd.to_datetime(end_date))
    ]

    filtered_expenses = expenses_df[
        (expenses_df['expense_person'] == person_name) &
        (expenses_df['expense_date'] >= pd.to_datetime(start_date)) &
        (expenses_df['expense_date'] <= pd.to_datetime(end_date))
    ]

    if not filtered_payments.empty or not filtered_expenses.empty:
        # Calculate overall totals
        total_received_overall = filtered_payments[filtered_payments['type'] == 'paid_to_me']['amount'].sum()
        total_paid_overall = filtered_payments[filtered_payments['type'] == 'i_paid']['amount'].sum()
        total_expenses_overall = filtered_expenses['total_line_amount'].sum()
        
        net_balance = total_received_overall - (total_paid_overall + total_expenses_overall)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Received", f"Rs. {total_received_overall:,.2f}")
        col2.metric("Total Paid", f"Rs. {total_paid_overall:,.2f}")
        col3.metric("Total Expenses", f"Rs. {total_expenses_overall:,.2f}")
        col4.metric("Net Balance", f"Rs. {net_balance:,.2f}")

        st.markdown("---")

        if tab == 'Transactions':
            st.subheader("Transaction Details")
            if not filtered_payments.empty:
                st.dataframe(filtered_payments[['date', 'type', 'amount', 'payment_method', 'description', 'reference_number']])
            else:
                st.info("No payment transactions found in this date range.")

        elif tab == 'Client Expenses':
            st.subheader("Client Expense Details")
            if not filtered_expenses.empty:
                st.dataframe(filtered_expenses[['expense_date', 'expense_category', 'expense_description', 'expense_amount', 'expense_quantity', 'total_line_amount']])
            else:
                st.info("No client expenses found in this date range.")
    else:
        st.info("No financial data available for this person in the selected date range.")

def generate_html_summary(df):
    """Generates an HTML summary page and saves it."""
    try:
        # Calculate totals
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
        df['type'] = df['type'].astype(str).str.lower()
        df['transaction_status'] = df['transaction_status'].astype(str).str.lower()

        total_received = df[df['type'] == 'paid_to_me']['amount'].sum()
        total_paid = df[df['type'] == 'i_paid']['amount'].sum()
        net_balance = total_received - total_paid

        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Financial Summary</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; padding: 20px; color: #333; }}
                .container {{ max-width: 900px; margin: auto; background: #f9f9f9; padding: 20px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
                h1, h2 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                .card {{ background: #fff; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); margin-bottom: 15px; }}
                .card h3 {{ margin-top: 0; color: #34495e; }}
                .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #ecf0f1; }}
                .positive {{ color: #27ae60; }}
                .negative {{ color: #c0392b; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Overall Financial Summary</h1>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

                <h2>Key Metrics</h2>
                <div class="summary-grid">
                    <div class="card">
                        <h3>Total Received</h3>
                        <p><strong>Rs. {total_received:,.2f}</strong></p>
                    </div>
                    <div class="card">
                        <h3>Total Paid</h3>
                        <p><strong>Rs. {total_paid:,.2f}</strong></p>
                    </div>
                    <div class="card">
                        <h3>Net Balance</h3>
                        <p><strong class="{'positive' if net_balance >= 0 else 'negative'}">Rs. {net_balance:,.2f}</strong></p>
                    </div>
                </div>

                <h2>Summary by Person</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Person</th>
                            <th>Total Received</th>
                            <th>Total Paid</th>
                            <th>Net Position</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        # Group by person to show a summary table
        person_summary = df.groupby('person').agg(
            total_received=('amount', lambda x: x[df['type'] == 'paid_to_me'].sum()),
            total_paid=('amount', lambda x: x[df['type'] == 'i_paid'].sum())
        ).fillna(0)
        person_summary['net_position'] = person_summary['total_received'] - person_summary['total_paid']

        for person, row in person_summary.iterrows():
            html_content += f"""
                        <tr>
                            <td>{person}</td>
                            <td>Rs. {row['total_received']:,.2f}</td>
                            <td>Rs. {row['total_paid']:,.2f}</td>
                            <td class="{'positive' if row['net_position'] >= 0 else 'negative'}">Rs. {row['net_position']:,.2f}</td>
                        </tr>
            """
        html_content += """
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """

        with open(SUMMARY_FILE, "w") as f:
            f.write(html_content)
        st.success(f"HTML summary generated at {SUMMARY_FILE}")

    except Exception as e:
        st.error(f"Error generating HTML summary: {e}")

# --- Main Streamlit App ---
def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(
        page_title="Financial Tracker",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    init_state()
    init_files()

    st.title("Financial Tracker")
    st.sidebar.title("Navigation")
    st.session_state['current_tab'] = st.sidebar.radio("Go to", ["Home", "Add Transaction", "View/Edit Transactions", "Reports", "People", "Client Expenses"])

    payments_df_raw = load_data(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
    payments_df = clean_payments_data(payments_df_raw)
    
    people_df = load_data(PEOPLE_FILE)
    st.session_state['people_df'] = people_df
    
    client_expenses_df = load_data(CLIENT_EXPENSES_FILE, keep_default_na=False)
    client_expenses_df = clean_expenses_data(client_expenses_df)

    if st.session_state['current_tab'] == 'Home':
        st.header("Home")
        st.write("Welcome to your financial tracker. Use the navigation on the left to manage your transactions and reports.")
        
        st.subheader("Financial Summary")
        total_received = payments_df[payments_df['type'] == 'paid_to_me']['amount'].sum()
        total_paid = payments_df[payments_df['type'] == 'i_paid']['amount'].sum()
        net_balance = total_received - total_paid

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Received", f"Rs. {total_received:,.2f}")
        col2.metric("Total Paid", f"Rs. {total_paid:,.2f}")
        col3.metric("Net Balance", f"Rs. {net_balance:,.2f}", delta_color="inverse")

        st.markdown("---")
        
        st.subheader("HTML Summary")
        if st.button("Generate HTML Summary"):
            generate_html_summary(payments_df)
            st.markdown(f"[View HTML Summary]({SUMMARY_URL})")
            
        st.subheader("Git Integration")
        if st.button("Push to GitHub"):
            git_push()

    elif st.session_state['current_tab'] == 'Add Transaction':
        st.header("Add New Transaction")
        
        people_list = sorted(people_df['name'].unique().tolist())
        people_list_with_placeholder = ["Select..."] + people_list
        
        with st.form("add_transaction_form", clear_on_submit=True):
            selected_transaction_type = st.radio("Transaction Type", ('Paid to Me', 'I Paid'))
            selected_person = st.selectbox("Person", people_list_with_placeholder)
            add_amount = st.number_input("Amount", min_value=0.0, format="%.2f")
            add_date = st.date_input("Date")
            add_description = st.text_area("Description", "")
            payment_method = st.radio("Payment Method", ('cash', 'cheque'))
            
            add_cheque_status = ''
            add_reference_number = ''
            add_status = ''
            
            if payment_method == 'cheque':
                add_cheque_status = st.selectbox("Cheque Status", valid_cheque_statuses_lower, key='cheque_status_add')
            
            add_status = st.selectbox("Transaction Status", valid_transaction_statuses_lower, key='trans_status_add')
            add_reference_number = st.text_input("Reference Number", key='ref_num_add')
            
            submitted = st.form_submit_button("Add Transaction")
            
            if submitted:
                if selected_person == "Select..." or not add_amount or not add_date:
                    st.error("Please fill in all required fields (Person, Amount, Date).")
                else:
                    new_row = {
                        "date": add_date,
                        "person": selected_person,
                        "amount": add_amount,
                        "type": 'paid_to_me' if selected_transaction_type == 'Paid to Me' else 'i_paid',
                        "status": add_status,
                        "description": add_description,
                        "payment_method": payment_method,
                        "reference_number": add_reference_number,
                        "cheque_status": add_cheque_status,
                        "transaction_status": add_status
                    }
                    new_payments_df = pd.concat([payments_df, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(new_payments_df, CSV_FILE)
                    st.success("Transaction added successfully!")
                    st.experimental_rerun()

    elif st.session_state['current_tab'] == 'View/Edit Transactions':
        st.header("View and Edit Transactions")
        
        people_list = sorted(payments_df['person'].unique().tolist())
        people_list_with_all = ["All"] + people_list
        
        st.session_state['view_person_filter'] = st.selectbox("Filter by Person", people_list_with_all)
        
        if st.session_state['view_person_filter'] != "All":
            filtered_df = payments_df[payments_df['person'] == st.session_state['view_person_filter']].reset_index(drop=True)
        else:
            filtered_df = payments_df.copy().reset_index(drop=True)
            
        filtered_df = filtered_df.sort_values('date', ascending=False).reset_index(drop=True)

        if not filtered_df.empty:
            for idx, row in filtered_df.iterrows():
                expander_title = f"Transaction {idx + 1}: {row['person']} - {row['date'].strftime('%Y-%m-%d')} - Rs. {row['amount']:,.2f}"
                with st.expander(expander_title):
                    if st.button(f"Edit ##{idx}", key=f"edit_btn_{idx}"):
                        st.session_state['editing_row_idx'] = idx
                        st.session_state['temp_edit_data'] = row.to_dict()
                    
                    if st.button(f"Delete ##{idx}", key=f"delete_btn_{idx}"):
                        payments_df.drop(filtered_df.index[idx], inplace=True)
                        save_data(payments_df, CSV_FILE)
                        st.success("Transaction deleted.")
                        st.session_state['editing_row_idx'] = None
                        st.experimental_rerun()
                        
                    st.json(row.to_dict(), expanded=False)
                    
            if st.session_state['editing_row_idx'] is not None:
                st.subheader(f"Editing Transaction {st.session_state['editing_row_idx'] + 1}")
                edit_idx = st.session_state['editing_row_idx']
                edit_data = st.session_state['temp_edit_data']

                with st.form("edit_form"):
                    edit_data['person'] = st.selectbox("Person", people_list, index=people_list.index(edit_data['person']), key='edit_person')
                    edit_data['amount'] = st.number_input("Amount", value=edit_data['amount'], min_value=0.0, format="%.2f", key='edit_amount')
                    edit_data['date'] = st.date_input("Date", value=pd.to_datetime(edit_data['date']).date(), key='edit_date')
                    edit_data['description'] = st.text_area("Description", value=edit_data['description'], key='edit_desc')
                    edit_data['type'] = st.radio("Transaction Type", ('paid_to_me', 'i_paid'), index=0 if edit_data['type'] == 'paid_to_me' else 1, key='edit_type')
                    edit_data['payment_method'] = st.radio("Payment Method", ('cash', 'cheque'), index=0 if edit_data['payment_method'] == 'cash' else 1, key='edit_method')
                    edit_data['transaction_status'] = st.selectbox("Status", valid_transaction_statuses_lower, index=valid_transaction_statuses_lower.index(edit_data['transaction_status']), key='edit_status')
                    
                    if edit_data['payment_method'] == 'cheque':
                        edit_data['cheque_status'] = st.selectbox("Cheque Status", valid_cheque_statuses_lower, index=valid_cheque_statuses_lower.index(edit_data['cheque_status']), key='edit_cheque_status')
                    else:
                        edit_data['cheque_status'] = ''

                    edit_data['reference_number'] = st.text_input("Reference Number", value=edit_data['reference_number'], key='edit_ref_num')

                    if st.form_submit_button("Update Transaction"):
                        payments_df.loc[payments_df.index[edit_idx]] = edit_data
                        save_data(payments_df, CSV_FILE)
                        st.success("Transaction updated.")
                        st.session_state['editing_row_idx'] = None
                        st.experimental_rerun()
        else:
            st.info("No transactions to display.")

    elif st.session_state['current_tab'] == 'Reports':
        st.header("Reports & Invoices")

        report_options = ['Summary Report', 'Per Person Report', 'Generate Invoice', 'Generate Bill']
        selected_report = st.selectbox("Select Report Type", report_options)

        if selected_report == 'Summary Report':
            st.subheader("Summary Report")
            total_received = payments_df[payments_df['type'] == 'paid_to_me']['amount'].sum()
            total_paid = payments_df[payments_df['type'] == 'i_paid']['amount'].sum()
            net_balance = total_received - total_paid

            st.metric("Total Received", f"Rs. {total_received:,.2f}")
            st.metric("Total Paid", f"Rs. {total_paid:,.2f}")
            st.metric("Net Balance", f"Rs. {net_balance:,.2f}")

            st.subheader("Summary by Person")
            if not payments_df.empty:
                person_summary = payments_df.groupby('person').agg(
                    total_received=('amount', lambda x: x[payments_df.loc[x.index, 'type'] == 'paid_to_me'].sum()),
                    total_paid=('amount', lambda x: x[payments_df.loc[x.index, 'type'] == 'i_paid'].sum())
                ).fillna(0)
                person_summary['net_position'] = person_summary['total_received'] - person_summary['total_paid']
                st.dataframe(person_summary)
            else:
                st.info("No payments to summarize.")

        elif selected_report == 'Per Person Report':
            st.subheader("Per Person Report")
            people_list = sorted(people_df['name'].unique().tolist())
            people_list_with_placeholder = ["Select..."] + people_list

            st.session_state['selected_per_person_report_person'] = st.selectbox("Select a person", people_list_with_placeholder)
            
            col1, col2 = st.columns(2)
            with col1:
                st.session_state['per_person_report_start_date'] = st.date_input("Start Date", value=st.session_state['per_person_report_start_date'])
            with col2:
                st.session_state['per_person_report_end_date'] = st.date_input("End Date", value=st.session_state['per_person_report_end_date'])

            st.session_state['selected_per_person_report_tab'] = st.radio("View", ['Transactions', 'Client Expenses'])

            if st.session_state['selected_per_person_report_person'] != "Select...":
                generate_per_person_report(
                    payments_df,
                    client_expenses_df,
                    st.session_state['selected_per_person_report_person'],
                    st.session_state['per_person_report_start_date'],
                    st.session_state['per_person_report_end_date'],
                    st.session_state['selected_per_person_report_tab']
                )

        elif selected_report == 'Generate Invoice':
            st.subheader("Generate Invoice PDF")
            people_list = sorted(people_df['name'].unique().tolist())
            people_list_with_placeholder = ["Select..."] + people_list

            st.session_state['invoice_person_name'] = st.selectbox("Select Person for Invoice", people_list_with_placeholder)
            col1, col2 = st.columns(2)
            with col1:
                st.session_state['invoice_start_date'] = st.date_input("Start Date", value=st.session_state['invoice_start_date'], key='invoice_start')
            with col2:
                st.session_state['invoice_end_date'] = st.date_input("End Date", value=st.session_state['invoice_end_date'], key='invoice_end')
            
            if st.button("Generate Invoice"):
                if st.session_state['invoice_person_name'] != "Select...":
                    pdf_path = generate_invoice_pdf(
                        payments_df,
                        client_expenses_df,
                        st.session_state['invoice_person_name'],
                        st.session_state['invoice_start_date'],
                        st.session_state['invoice_end_date']
                    )
                    st.session_state['generated_invoice_pdf_path'] = pdf_path
                    st.session_state['show_download_button'] = True
                    st.success(f"Invoice generated for {st.session_state['invoice_person_name']}.")
                else:
                    st.error("Please select a person.")

            if st.session_state['show_download_button'] and st.session_state['generated_invoice_pdf_path']:
                with open(st.session_state['generated_invoice_pdf_path'], "rb") as pdf_file:
                    st.download_button(
                        label="Download Invoice PDF",
                        data=pdf_file,
                        file_name=os.path.basename(st.session_state['generated_invoice_pdf_path']),
                        mime="application/pdf"
                    )

        elif selected_report == 'Generate Bill':
            st.subheader("Generate Bill PDF")
            client_list = sorted(client_expenses_df['expense_person'].unique().tolist())
            client_list_with_placeholder = ["Select..."] + client_list

            st.session_state['bill_client_name'] = st.selectbox("Select Client for Bill", client_list_with_placeholder)
            col1, col2 = st.columns(2)
            with col1:
                st.session_state['bill_start_date'] = st.date_input("Start Date", value=st.session_state['bill_start_date'], key='bill_start')
            with col2:
                st.session_state['bill_end_date'] = st.date_input("End Date", value=st.session_state['bill_end_date'], key='bill_end')

            if st.button("Generate Bill"):
                if st.session_state['bill_client_name'] != "Select...":
                    pdf_path = generate_bill_pdf(
                        client_expenses_df,
                        st.session_state['bill_client_name'],
                        st.session_state['bill_start_date'],
                        st.session_state['bill_end_date']
                    )
                    st.session_state['generated_bill_pdf_path'] = pdf_path
                    st.session_state['show_bill_download_button'] = True
                    st.success(f"Bill generated for {st.session_state['bill_client_name']}.")
                else:
                    st.error("Please select a client.")

            if st.session_state['show_bill_download_button'] and st.session_state['generated_bill_pdf_path']:
                with open(st.session_state['generated_bill_pdf_path'], "rb") as pdf_file:
                    st.download_button(
                        label="Download Bill PDF",
                        data=pdf_file,
                        file_name=os.path.basename(st.session_state['generated_bill_pdf_path']),
                        mime="application/pdf"
                    )

    elif st.session_state['current_tab'] == 'People':
        st.header("Manage People")
        st.write("Add and view people (clients/vendors) involved in your transactions.")
        
        with st.form("add_person_form"):
            selected_person_to_add = st.text_input("Person's Name", "")
            selected_person_category = st.selectbox("Category", ['client', 'vendor'])
            submitted = st.form_submit_button("Add Person")
            
            if submitted and selected_person_to_add:
                if selected_person_to_add in people_df['name'].values:
                    st.error("This person already exists.")
                else:
                    new_person = {"name": selected_person_to_add, "category": selected_person_category}
                    new_people_df = pd.concat([people_df, pd.DataFrame([new_person])], ignore_index=True)
                    save_data(new_people_df, PEOPLE_FILE)
                    st.success(f"Added new person: {selected_person_to_add}")
                    st.experimental_rerun()

        st.subheader("List of People")
        st.dataframe(people_df)

    elif st.session_state['current_tab'] == 'Client Expenses':
        st.header("Client Expenses")
        st.write("Manage expenses incurred for clients.")

        expenses_tab, add_expense_tab = st.tabs(["View/Edit Expenses", "Add Expense"])

        with expenses_tab:
            st.subheader("View Client Expenses")
            client_list = sorted(client_expenses_df['expense_person'].unique().tolist())
            client_list_with_all = ["All"] + client_list
            st.session_state['client_expense_filter_person'] = st.selectbox("Filter by Client", client_list_with_all, key='expense_filter_person')

            category_list = sorted(client_expenses_df['expense_category'].unique().tolist())
            category_list_with_all = ["All"] + category_list
            st.session_state['client_expense_filter_category'] = st.selectbox("Filter by Category", category_list_with_all, key='expense_filter_category')

            filtered_expenses = client_expenses_df.copy()
            if st.session_state['client_expense_filter_person'] != "All":
                filtered_expenses = filtered_expenses[filtered_expenses['expense_person'] == st.session_state['client_expense_filter_person']]
            if st.session_state['client_expense_filter_category'] != "All":
                filtered_expenses = filtered_expenses[filtered_expenses['expense_category'] == st.session_state['client_expense_filter_category']]

            if not filtered_expenses.empty:
                st.dataframe(filtered_expenses.sort_values('expense_date', ascending=False))
            else:
                st.info("No expenses found for the selected filters.")

        with add_expense_tab:
            st.subheader("Add New Client Expense")
            client_list = sorted(people_df['name'].unique().tolist())
            client_list_with_placeholder = ["Select..."] + client_list

            with st.form("add_client_expense_form", clear_on_submit=True):
                selected_client_for_expense = st.selectbox("Client", client_list_with_placeholder, key='expense_client_add')
                add_client_expense_amount = st.number_input("Amount (per unit)", min_value=0.0, format="%.2f")
                add_client_expense_quantity = st.number_input("Quantity", min_value=1.0, format="%.2f", value=1.0)
                add_client_expense_date = st.date_input("Date")
                add_client_expense_category = st.selectbox("Category", valid_expense_categories, key='expense_category_add')
                add_client_expense_description = st.text_area("Description", "")
                add_client_expense_status = st.selectbox("Status", valid_transaction_statuses_lower, key='expense_status_add')
                add_client_expense_created_by = st.text_input("Created By", "")
                add_client_expense_ref_num = st.text_input("Original Transaction Ref. Number", "")
                
                submitted = st.form_submit_button("Add Expense")
                if submitted:
                    if selected_client_for_expense == "Select..." or not add_client_expense_amount:
                        st.error("Please fill in all required fields (Client, Amount).")
                    else:
                        new_expense = {
                            'expense_uuid': str(uuid.uuid4()),
                            'original_transaction_ref_num': add_client_expense_ref_num,
                            'expense_person': selected_client_for_expense,
                            'expense_amount': add_client_expense_amount,
                            'expense_quantity': add_client_expense_quantity,
                            'expense_date': add_client_expense_date,
                            'expense_category': add_client_expense_category,
                            'expense_status': add_client_expense_status,
                            'expense_description': add_client_expense_description,
                            'expense_created_by': add_client_expense_created_by
                        }
                        new_expenses_df = pd.concat([client_expenses_df, pd.DataFrame([new_expense])], ignore_index=True)
                        save_data(new_expenses_df, CLIENT_EXPENSES_FILE)
                        st.success("Client expense added successfully!")
                        st.experimental_rerun()

if __name__ == "__main__":
    main()
