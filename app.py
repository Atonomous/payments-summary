import streamlit as st
import pandas as pd
from datetime import datetime
import os
from git import Repo
import numpy as np # Import numpy for nan check

# Session State Initialization - MUST BE AT THE VERY TOP
def init_state():
    """
    Initializes all necessary session state variables with default values.
    This function is called at the very beginning of the script to ensure
    all keys are present before widgets attempt to access them.
    """
    keys = [
        'selected_transaction_type', 'payment_method', 'editing_row_idx', 'selected_person', 'reset_add_form',
        'add_amount', 'add_date', 'add_reference_number', 'add_cheque_status', 'add_status', 'add_description',
        'temp_edit_data' # Ensure temp_edit_data is initialized
    ]
    defaults = {
        'selected_transaction_type': 'Paid to Me',
        'payment_method': 'cash',
        'editing_row_idx': None,
        'selected_person': "Select...",
        'reset_add_form': False,
        'add_amount': None,
        'add_date': None,
        'add_reference_number': '',
        'add_cheque_status': 'received/given',
        'add_status': 'completed',
        'add_description': '',
        'temp_edit_data': {} # Initialize as empty dict
    }
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = defaults[k]

init_state() # Call init_state here, before any st. commands that might trigger a rerun or widget creation.


# Configuration (kept here as they are global constants)
REPO_PATH = os.getcwd()
CSV_FILE = os.path.join(REPO_PATH, "payments.csv")
PEOPLE_FILE = os.path.join(REPO_PATH, "people.csv")
SUMMARY_FILE = os.path.join(REPO_PATH, "docs/index.html")
SUMMARY_URL = "https://atonomous.github.io/payments-summary/"

# Define valid status lists globally so they are accessible everywhere
valid_cheque_statuses_lower = ["received/given", "processing", "bounced", "processing done"]
valid_transaction_statuses_lower = ["completed", "pending"]

def clean_payments_data(df):
    """
    Cleans and normalizes the payments DataFrame to ensure data consistency.
    This function modifies the DataFrame in memory.
    It handles common data entry errors and type mismatches.
    """
    if df.empty:
        return df

    # Ensure all relevant columns exist and are strings, replacing NaN/None
    cols_to_check = ["payment_method", "cheque_status", "transaction_status", "reference_number", "date", "amount", "person", "type", "status", "description"]
    for col in cols_to_check:
        if col not in df.columns:
            df[col] = '' # Add missing column with empty string default
        # Ensure these columns are always strings and strip whitespace
        df[col] = df[col].astype(str).replace('nan', '').replace('None', '').str.strip()

    # Convert amount to numeric, coercing errors to NaN, then fill with 0.0
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)

    # Convert date to YYYY-MM-DD format, coercing errors to NaT
    df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')

    # Rule 1: If payment_method is 'cash', cheque_status must be empty
    cash_payments_mask = df['payment_method'].str.lower() == 'cash'
    df.loc[cash_payments_mask, 'cheque_status'] = '' # Set to empty string for cash payments

    # Iterate through rows to apply more complex cleaning rules
    for index, row in df.iterrows():
        ref_num_lower = str(row['reference_number']).lower()
        trans_status_current_lower = str(row['transaction_status']).lower()
        cheque_status_current_lower = str(row['cheque_status']).lower()
        payment_method_lower = str(row['payment_method']).lower()

        # Prioritize moving valid statuses from reference_number if applicable
        # This ensures that if a status was mistakenly put in reference_number, it gets moved.
        if ref_num_lower in valid_transaction_statuses_lower:
            if trans_status_current_lower not in valid_transaction_statuses_lower:
                df.loc[index, 'transaction_status'] = ref_num_lower
            df.loc[index, 'reference_number'] = '' # Clear reference_number after moving
        elif ref_num_lower in valid_cheque_statuses_lower and payment_method_lower == 'cheque':
            if cheque_status_current_lower not in valid_cheque_statuses_lower:
                df.loc[index, 'cheque_status'] = ref_num_lower
            df.loc[index, 'reference_number'] = '' # Clear reference_number after moving

        # Rule 3: Ensure transaction_status is valid, default to 'completed' if invalid/empty
        if df.loc[index, 'transaction_status'].lower() not in valid_transaction_statuses_lower:
            df.loc[index, 'transaction_status'] = 'completed' # Default to completed

        # Rule 4: Ensure cheque_status is valid for cheque payments, default to 'processing' if invalid/empty
        if payment_method_lower == 'cheque':
            if df.loc[index, 'cheque_status'].lower() not in valid_cheque_statuses_lower:
                df.loc[index, 'cheque_status'] = 'processing' # Default to 'processing' for invalid cheque status
        else: # For cash payments, ensure cheque_status is empty
            df.loc[index, 'cheque_status'] = ''

    # The reference_number column should always be treated as a string,
    # so no float conversion is needed here.
    # The initial read with dtype={'reference_number': str} and the apply
    # for 'nan'/'None' should be sufficient.

    # Remove rows where 'date', 'person', 'amount' are all empty/zero after cleaning
    df = df[~((df['date'] == '') & (df['person'] == '') & (df['amount'] == 0.0))]

    return df


def init_files():
    """
    Initializes payments.csv and people.csv if they don't exist.
    Also handles migration of old column names and ensures 'category' in people.csv.
    Crucially, it now cleans the payments data upon load.
    """
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
            # CRITICAL FIX: Force reference_number to be read as string and handle NA values aggressively
            # This is key to preventing Pandas from inferring it as a number or float
            df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
            # Ensure any 'nan' strings or actual np.nan values are converted to empty strings immediately
            df['reference_number'] = df['reference_number'].apply(
                lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
            )

            # Handle migration from old format to new format if needed
            if 'receipt_number' in df.columns or 'cheque_number' in df.columns:
                df['reference_number'] = df.apply(
                    lambda row: row['receipt_number'] if row['payment_method'] == 'cash'
                    else (row['cheque_number'] if row['payment_method'] == 'cheque' else ''),
                    axis=1
                ).fillna('')
                df = df.drop(columns=['receipt_number', 'cheque_number'], errors='ignore')
                st.toast("Migrated old reference number columns.")
            
            # CRITICAL: Clean data on load and save back
            df = clean_payments_data(df)
            df.to_csv(CSV_FILE, index=False) # Save the cleaned data back to CSV
            st.toast("Payments data cleaned and saved.")

        # Initialize people.csv if it doesn't exist
        if not os.path.exists(PEOPLE_FILE):
            pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)
            st.toast(f"Created new {PEOPLE_FILE}")
        else:
            df = pd.read_csv(PEOPLE_FILE)
            if 'category' not in df.columns:
                df['category'] = 'client' # Default category
                df.to_csv(PEOPLE_FILE, index=False)
            df['name'] = df['name'].astype(str) # Ensure name is string
            df.to_csv(PEOPLE_FILE, index=False) # Save back
    except Exception as e:
        st.error(f"Error initializing files: {e}")

# Call init_files at the start of the script to ensure files are ready
init_files()

def git_push():
    """
    Performs a Git add, commit, and push operation.
    """
    try:
        repo = Repo(REPO_PATH)
        
        # Check for uncommitted changes before adding
        if repo.is_dirty(untracked_files=True):
            repo.git.add(update=True) # Add all modified files
            repo.git.add(all=True) # Also add untracked files (like new HTML if created)
        
        # Only commit if there are changes in the index
        if repo.index.diff("HEAD"):
            repo.index.commit("Automated update: payment records")
        else:
            return True # No changes, so nothing to push, consider it successful

        origin = repo.remote(name='origin')
        origin.push()
        st.success("GitHub updated successfully!")
        return True
    except Exception as e:
        st.error(f"Error updating GitHub: {e}")
        st.warning("Please ensure you have configured Git and have push access to the repository.")
        st.warning("If the issue persists, try running 'git push' manually in your terminal for detailed errors.")
        return False

def prepare_dataframe_for_display(df):
    """
    Performs final preparation for displaying the DataFrame, including formatting.
    This function creates new columns for display purposes without altering
    the original DataFrame's data. It's designed to be robust against
    inconsistent data entries in the CSV.
    """
    df_display = df.copy()

    # Ensure columns are strings and handle common NaN/None representations
    for col in ['reference_number', 'cheque_status', 'transaction_status', 'payment_method', 'description', 'person', 'type', 'status']:
        if col in df_display.columns:
            df_display[col] = df_display[col].astype(str).replace('nan', '').replace('None', '').str.strip()
        else:
            df_display[col] = '' # Add missing column if it doesn't exist

    # Convert amount to float and handle missing values for calculations
    df_display['amount'] = pd.to_numeric(df_display['amount'], errors='coerce').fillna(0.0)
    df_display['amount_display'] = df_display['amount'].apply(lambda x: f"Rs. {x:,.2f}")

    # Robust Date Formatting:
    df_display['date_parsed'] = pd.to_datetime(df_display['date'], errors='coerce')
    df_display['formatted_date'] = df_display['date_parsed'].dt.strftime('%Y-%m-%d').fillna('')

    # Robust Cheque Status Display:
    df_display['cheque_status_cleaned'] = df_display.apply(
        lambda row: None if row['payment_method'].lower() == 'cash' else (
            str(row['cheque_status']) if pd.notna(row['cheque_status']) else None
        ), axis=1
    )
    df_display['cheque_status_display'] = df_display['cheque_status_cleaned'].apply(
        lambda x: next((s.capitalize() for s in valid_cheque_statuses_lower if x is not None and str(x).lower() == s), '-')
    )

    # Robust Transaction Status Display:
    df_display['transaction_status_display'] = df_display.apply(
        lambda row: str(row['transaction_status']).capitalize() if str(row['transaction_status']).lower() in valid_transaction_statuses_lower else '-',
        axis=1
    )

    # Robust Reference Number Display:
    # This uses the already cleaned 'reference_number' column from clean_payments_data
    df_display['reference_number_display'] = df_display.apply(
        lambda row: str(row['reference_number']) if str(row['reference_number']).strip() != '' else '-',
        axis=1
    )

    # Format 'type' for display ('paid_to_me' -> 'Received', 'i_paid' -> 'Paid')
    df_display['type_display'] = df_display['type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'}).fillna('')

    return df_display


def generate_html_summary(df):
    """
    Generates an HTML summary report based on the provided DataFrame.
    """
    try:
        # Prepare DataFrame for HTML display using the robust function
        transactions_display = prepare_dataframe_for_display(df)

        # Calculate payment totals from the original (unmodified) DataFrame for accuracy
        df_for_totals = df.copy()
        df_for_totals['amount'] = pd.to_numeric(df_for_totals['amount'], errors='coerce').fillna(0.0)
        df_for_totals['type'] = df_for_totals['type'].astype(str).str.lower()
        df_for_totals['payment_method'] = df_for_totals['payment_method'].astype(str).str.lower()
        df_for_totals['transaction_status'] = df_for_totals['transaction_status'].astype(str).str.lower()

        payment_totals = df_for_totals.groupby(['type', 'payment_method'])['amount'].sum().unstack().fillna(0)

        # Prepare summary statistics
        totals = {
            'total_received': df_for_totals[df_for_totals['type'] == 'paid_to_me']['amount'].sum(),
            'pending_received': df_for_totals[(df_for_totals['type'] == 'paid_to_me') &
                                              (df_for_totals['transaction_status'] == 'pending')]['amount'].sum(),
            'total_paid': df_for_totals[df_for_totals['type'] == 'i_paid']['amount'].sum(),
            'pending_paid': df_for_totals[(df_for_totals['type'] == 'i_paid') &
                                          (df_for_totals['transaction_status'] == 'pending')]['amount'].sum(),
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
            'net_balance': (df_for_totals[df_for_totals['type'] == 'paid_to_me']['amount'].sum() -
                           df_for_totals[df_for_totals['type'] == 'i_paid']['amount'].sum())
        }

        # Read people data for filters
        people_df = pd.read_csv(PEOPLE_FILE)
        person_options_html = ''.join(f'<option value="{name}">{name}</option>' for name in sorted(people_df['name'].unique()))

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
        body {{
            font-family: 'Poppins', sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f4f7f6;
            color: #333;
            line-height: 1.6;
        }}
        .container {{
            max-width: 1200px;
            margin: 20px auto;
            padding: 20px;
            background-color: #ffffff;
            border-radius: 12px;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
        }}
        header {{
            text-align: center;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
            margin-bottom: 30px;
        }}
        .logo {{
            font-size: 2.5em;
            font-weight: 700;
            color: #2c3e50;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 10px;
        }}
        .logo i {{
            color: #28a745;
            margin-right: 10px;
            font-size: 0.9em;
        }}
        .report-title {{
            font-size: 1.8em;
            color: #34495e;
            margin-bottom: 5px;
        }}
        .report-date {{
            font-size: 0.9em;
            color: #7f8c8d;
        }}
        .report-date i {{
            margin-right: 5px;
            color: #95a5a6;
        }}

        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }}
        .card {{
            background-color: #fdfdfd;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.06);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            border-left: 5px solid;
        }}
        .card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }}
        .card.received {{ border-left-color: #28a745; }}
        .card.paid {{ border-left-color: #dc3545; }}
        .card.balance {{ border-left-color: #007bff; }}

        .card-header {{
            display: flex;
            align-items: center;
            margin-bottom: 15px;
        }}
        .card-icon {{
            font-size: 1.8em;
            margin-right: 15px;
            padding: 12px;
            border-radius: 50%;
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .received .card-icon {{ background-color: #28a745; }}
        .paid .card-icon {{ background-color: #dc3545; }}
        .balance .card-icon {{ background-color: #007bff; }}

        .card-title {{
            font-size: 1.1em;
            color: #555;
            margin-bottom: 3px;
        }}
        .card-amount {{
            font-size: 1.9em;
            font-weight: 600;
            color: #2c3e50;
        }}
        .card-details {{
            font-size: 0.9em;
            color: #666;
            padding-left: 55px;
        }}
        .card-details div {{
            margin-bottom: 5px;
        }}
        .card-details i {{
            margin-right: 8px;
            color: #999;
        }}

        .section-title {{
            font-size: 1.6em;
            color: #34495e;
            margin-bottom: 25px;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
            display: flex;
            align-items: center;
        }}
        .section-title i {{
            margin-right: 10px;
            color: #007bff;
        }}

        .filters {{
            background-color: #fdfdfd;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.06);
            margin-bottom: 40px;
        }}
        .filter-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        .filter-group label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: #555;
        }}
        .filter-group select,
        .filter-group input[type="date"] {{
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-family: 'Poppins', sans-serif;
            font-size: 0.95em;
            color: #333;
            box-sizing: border-box;
            background-color: #fff;
        }}
        .filter-group select:focus,
        .filter-group input[type="date"]:focus {{
            border-color: #007bff;
            box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.15);
            outline: none;
        }}
        .filter-actions {{
            text-align: right;
            margin-top: 20px;
        }}
        .filter-btn {{
            background-color: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 500;
            transition: background-color 0.3s ease, transform 0.2s ease;
            margin-left: 10px;
            display: inline-flex;
            align-items: center;
        }}
        .filter-btn i {{
            margin-right: 8px;
        }}
        .filter-btn:hover {{
            background-color: #0056b3;
            transform: translateY(-2px);
        }}
        .filter-btn.reset-btn {{
            background-color: #6c757d;
        }}
        .filter-btn.reset-btn:hover {{
            background-color: #5a6268;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 40px;
            background-color: #fdfdfd;
            border-radius: 10px;
            overflow: hidden; /* Ensures rounded corners apply to content */
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.06);
        }}
        th, td {{
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}
        th {{
            background-color: #e9ecef;
            color: #495057;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.9em;
        }}
        tbody tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        tbody tr:hover {{
            background-color: #f1f1f1;
            transform: scale(1.005);
            transition: background-color 0.2s ease, transform 0.2s ease;
        }}
        .status {{
            padding: 5px 10px;
            border-radius: 5px;
            font-weight: 500;
            font-size: 0.85em;
            color: #fff;
            display: inline-block;
        }}
        .status.completed {{ background-color: #28a745; }}
        .status.pending {{ background-color: #ffc107; color: #333; }}
        .status.received-given {{ background-color: #6c757d; }}
        .status.processing {{ background-color: #007bff; }}
        .status.bounced {{ background-color: #dc3545; }}
        .status.processing-done {{ background-color: #20c997; }}

        .no-results {{
            text-align: center;
            padding: 50px 20px;
            background-color: #fdfdfd;
            border-radius: 10px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.06);
            margin-bottom: 40px;
            color: #7f8c8d;
        }}
        .no-results p {{
            font-size: 1.1em;
            margin-top: 10px;
        }}

        .footer {{
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #7f8c8d;
            font-size: 0.85em;
            margin-top: 30px;
        }}
        .footer p {{
            margin: 5px 0;
        }}
        .footer i {{
            margin-right: 5px;
            color: #95a5a6;
        }}

        /* Responsive adjustments */
        @media (max-width: 768px) {{
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
            .filter-grid {{
                grid-template-columns: 1fr;
            }}
            .filter-actions {{
                text-align: center;
            }}
            .filter-btn {{
                width: 100%;
                margin-left: 0;
                margin-bottom: 10px;
            }}
            table, thead, tbody, th, td, tr {{
                display: block;
            }}
            thead tr {{
                position: absolute;
                top: -9999px;
                left: -9999px;
            }}
            tr {{
                border: 1px solid #eee;
                margin-bottom: 15px;
                border-radius: 8px;
                overflow: hidden;
            }}
            td {{
                border: none;
                position: relative;
                padding-left: 50%;
                text-align: right;
            }}
            td:before {{
                content: attr(data-label);
                position: absolute;
                left: 10px;
                width: 45%;
                padding-right: 10px;
                white-space: nowrap;
                text-align: left;
                font-weight: 600;
                color: #555;
            }}
            /* Specific labels for mobile view */
            td:nth-of-type(1):before {{ content: "Date"; }}
            td:nth-of-type(2):before {{ content: "Person"; }}
            td:nth-of-type(3):before {{ content: "Amount"; }}
            td:nth-of-type(4):before {{ content: "Type"; }}
            td:nth-of-type(5):before {{ content: "Method"; }}
            td:nth-of-type(6):before {{ content: "Cheque Status"; }}
            td:nth-of-type(7):before {{ content: "Reference No."; }}
            td:nth-of-type(8):before {{ content: "Status"; }}
            td:nth-of-type(9):before {{ content: "Description"; }}
        }}
    </style>
    <script>
        $(document).ready(function() {{
            // Set default date range on load
            const today = new Date();
            const oneMonthAgo = new Date();
            oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
            $('#start-date').val(oneMonthAgo.toISOString().split('T')[0]);
            $('#end-date').val(today.toISOString().split('T')[0]);

            applyFilters(); // Apply filters immediately on page load with default dates
        }});

        function applyFilters() {{
            const startDate = $('#start-date').val();
            const endDate = $('#end-date').val();
            const person = $('#name-filter').val().toLowerCase();
            const type = $('#type-filter').val();
            const method = $('#method-filter').val().toLowerCase();
            const chequeStatus = $('#status-filter').val().toLowerCase();

            console.log("--- Applying Filters ---");
            console.log("Start Date:", startDate);
            console.log("End Date:", endDate);
            console.log("Person Filter:", person);
            console.log("Type Filter:", type);
            console.log("Method Filter:", method);
            console.log("Cheque Status Filter:", chequeStatus);

            let visibleRows = 0;

            $('#transactions-table tbody tr').each(function() {{
                const rowDate = $(this).data('date'); // This will be YYYY-MM-DD
                const rowPerson = $(this).data('person').toString().toLowerCase();
                const rowType = $(this).data('type');
                const rowMethod = $(this).data('method').toString().toLowerCase();
                const rowChequeStatus = $(this).data('cheque-status').toString().toLowerCase();

                console.log("Processing Row:", {{ rowDate, rowPerson, rowType, rowMethod, rowChequeStatus }});

                // Date filter: Compare YYYY-MM-DD strings directly
                const datePass = (!startDate || rowDate >= startDate) && (!endDate || rowDate <= endDate);

                // Person filter
                const personPass = !person || rowPerson.includes(person);

                // Type filter
                const typePass = !type || rowType === type;

                // Method filter
                const methodPass = !method || rowMethod === method;

                // Cheque status filter
                const chequeStatusPass = !chequeStatus ||
                                      (rowChequeStatus && rowChequeStatus.includes(chequeStatus));

                if (datePass && personPass && typePass && methodPass && chequeStatusPass) {{
                    $(this).show();
                    visibleRows++;
                    console.log("Row PASSED filters.");
                }} else {{
                    $(this).hide();
                    console.log("Row FAILED filters.");
                }}
            }});

            // Show/hide no results message
            if (visibleRows === 0) {{
                $('#no-results').show();
                $('#transactions-table').hide();
                console.log("No results found.");
            }} else {{
                $('#no-results').hide();
                $('#transactions-table').show();
                console.log(visibleRows + " results found.");
            }}
            console.log("--- Filters Applied ---");
        }}

        function resetFilters() {{
            // Reset select inputs
            $('#name-filter').val('');
            $('#type-filter').val('');
            $('#method-filter').val('');
            $('#status-filter').val('');

            // Reset date inputs to default range
            const today = new Date();
            const oneMonthAgo = new Date();
            oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
            $('#start-date').val(oneMonthAgo.toISOString().split('T')[0]);
            $('#end-date').val(today.toISOString().split('T')[0]);
            
            applyFilters(); // Apply filters after resetting
        }}
    </script>
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
                        {'<span style="color: #28a745;"><i class="fas fa-check-circle"></i> Positive Balance</span>'
                         if totals['net_balance'] >= 0
                         else '<span style="color: #dc3545;"><i class="fas fa-exclamation-circle"></i> Negative Balance</span>'}
                    </div>
                </div>
            </div>
        </div>

        <div class="filters">
            <h2 class="section-title">
                <i class="fas fa-filter"></i> Filters
            </h2>

            <div class="filter-grid">
                <div class="filter-group">
                    <label for="start-date">Date Range</label>
                    <input type="date" id="start-date" class="date-filter">
                    <span style="display: inline-block; margin: 0 5px; font-size: 12px;">to</span>
                    <input type="date" id="end-date" class="date-filter">
                </div>

                <div class="filter-group">
                    <label for="name-filter">Person</label>
                    <select id="name-filter">
                        <option value="">All</option>
                        {person_options_html}
                    </select>
                </div>

                <div class="filter-group">
                    <label for="type-filter">Transaction Type</label>
                    <select id="type-filter">
                        <option value="">All</option>
                        <option value="paid_to_me">Received</option>
                        <option value="i_paid">Paid</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="method-filter">Payment Method</label>
                    <select id="method-filter">
                        <option value="">All</option>
                        <option value="cash">Cash</option>
                        <option value="cheque">Cheque</option>
                    </select>
                </div>

                <div class="filter-group">
                    <label for="status-filter">Cheque Status</label>
                    <select id="status-filter">
                        <option value="">All</option>
                        <option value="received/given">Received/Given</option>
                        <option value="processing">Processing</option>
                        <option value="bounced">Bounced</option>
                        <option value="processing done">Processing Done</option>
                    </select>
                </div>
            </div>

            <div class="filter-actions">
                <button class="filter-btn" onclick="applyFilters()">
                    <i class="fas fa-filter"></i> Apply Filters
                </button>
                <button class="filter-btn reset-btn" onclick="resetFilters()">
                    <i class="fas fa-redo"></i> Reset
                </button>
            </div>
        </div>

        <h2 class="section-title">
            <i class="fas fa-list"></i> All Transactions
        </h2>

        <div class="no-results" id="no-results">
            <i class="fas fa-search" style="font-size: 24px; margin-bottom: 10px;"></i>
            <p>No transactions match your filters</p>
        </div>

        <table id="transactions-table">
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Person</th>
                    <th>Amount</th>
                    <th>Type</th>
                    <th>Method</th>
                    <th>Cheque Status</th>
                    <th>Reference No.</th>
                    <th>Status</th>
                    <th>Description</th>
                </tr>
            </thead>
            <tbody>"""

        # Add transaction rows with correct column data using the original, cleaned DataFrame for data attributes
        for idx, row in df.iterrows(): # Use 'df' directly for data attributes
            # Ensure values are strings for data attributes
            row_date = str(row['date'])
            row_person = str(row['person'])
            row_type = str(row['type'])
            row_method = str(row['payment_method']).lower()
            row_cheque_status = str(row['cheque_status']).lower() if str(row['cheque_status']).strip() != '' else ''

            # Use the _display columns for visible content
            cheque_status_class = str(transactions_display.loc[idx, 'cheque_status_display']).lower().replace(' ', '-').replace('/', '-') if transactions_display.loc[idx, 'cheque_status_display'] != '-' else ''
            status_class = str(transactions_display.loc[idx, 'transaction_status_display']).lower().replace(' ', '-') if transactions_display.loc[idx, 'transaction_status_display'] != '-' else ''

            html += f"""
                <tr data-date="{row_date}"
                    data-person="{row_person}"
                    data-type="{row_type}"
                    data-method="{row_method}"
                    data-cheque-status="{row_cheque_status}">
                    <td>{transactions_display.loc[idx, 'formatted_date']}</td>
                    <td>{transactions_display.loc[idx, 'person']}</td>
                    <td>{transactions_display.loc[idx, 'amount_display']}</td>
                    <td>{transactions_display.loc[idx, 'type_display']}</td>
                    <td>{str(transactions_display.loc[idx, 'payment_method']).capitalize()}</td>
                    <td><span class="status {cheque_status_class}">{transactions_display.loc[idx, 'cheque_status_display']}</span></td>
                    <td>{transactions_display.loc[idx, 'reference_number_display']}</td>
                    <td><span class="status {status_class}">{transactions_display.loc[idx, 'transaction_status_display']}</span></td>
                    <td>{transactions_display.loc[idx, 'description'] if transactions_display.loc[idx, 'description'] else '-'}</td>
                </tr>"""

        html += """
            </tbody>
        </table>

        <div class="footer">
            <p><i class="fas fa-file-alt"></i> This report was automatically generated by Payment Tracker System</p>
            <p><i class="far fa-copyright"></i> {datetime.now().year} All Rights Reserved</p>
        </div>
    </div>
</body>
</html>"""

        # Save the HTML file
        os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        st.toast("HTML summary generated successfully!")
        return True
    except Exception as e:
        st.error(f"Error generating HTML summary: {e}")
        return False

# Streamlit UI
st.set_page_config(layout="wide")
st.title("💰 Payment Tracker")
st.sidebar.markdown(f"[🌐 View Public Summary]({SUMMARY_URL})", unsafe_allow_html=True)

def reset_form_session_state_for_add_transaction():
    """Resets session state variables for the 'Add Transaction' form."""
    st.session_state['selected_transaction_type'] = 'Paid to Me'
    st.session_state['payment_method'] = 'cash'
    st.session_state['selected_person'] = "Select..."
    st.session_state['editing_row_idx'] = None # Ensure edit mode is off
    # Clear form inputs by setting their keys to default values
    st.session_state['add_amount'] = None # Reset to None
    st.session_state['add_date'] = None # Reset to None
    st.session_state['add_reference_number'] = ''
    st.session_state['add_cheque_status'] = 'received/given'
    st.session_state['add_status'] = 'completed'
    st.session_state['add_description'] = ''

# Handle form reset at the beginning of the rerun, if flagged
if st.session_state.get('reset_add_form', False):
    reset_form_session_state_for_add_transaction()
    st.session_state['reset_add_form'] = False # Reset the flag immediately after handling

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
        # Ensure 'name' is treated as string before filtering
        filtered_people = people_df[people_df['category'] == category]['name'].astype(str).tolist()
    except Exception as e:
        st.error(f"Error loading people data: {e}")
        filtered_people = []

    person_options = ["Select..."] + sorted(filtered_people)

    # Ensure selected_person is a valid option, or reset it
    if st.session_state['selected_person'] not in person_options:
        st.session_state['selected_person'] = "Select..."

    current_person_index = person_options.index(st.session_state['selected_person'])

    with st.form("transaction_form", clear_on_submit=False): # Set clear_on_submit to False to manage state manually
        col1, col2 = st.columns(2)
        with col1:
            # Conditionally pass value based on session state
            amount_value = st.session_state['add_amount']
            if amount_value is None:
                amount = st.number_input("Amount (Rs.)", min_value=0.0, format="%.2f", key='add_amount')
            else:
                amount = st.number_input("Amount (Rs.)", min_value=0.0, format="%.2f", value=float(amount_value), key='add_amount')
            
            # Conditionally pass value based on session state
            date_value = st.session_state['add_date']
            if date_value is None:
                date = st.date_input("Date", key='add_date')
            else:
                date = st.date_input("Date", value=date_value, key='add_date')

            reference_number = st.text_input("Reference Number (Receipt/Cheque No.)",
                                             value=st.session_state['add_reference_number'], key='add_reference_number')

            cheque_status_val = ""
            if st.session_state['payment_method'] == "cheque":
                default_cheque_status_idx = 0
                if st.session_state['add_cheque_status'] in valid_cheque_statuses_lower:
                    default_cheque_status_idx = valid_cheque_statuses_lower.index(st.session_state['add_cheque_status'])
                
                cheque_status_val = st.selectbox(
                    "Cheque Status",
                    valid_cheque_statuses_lower,
                    index=default_cheque_status_idx,
                    key='add_cheque_status'
                )

        with col2:
            st.session_state['selected_person'] = st.selectbox(
                "Select Person", person_options, index=current_person_index, key='selected_person_dropdown'
            )
            if st.session_state['selected_person'] == "Select...":
                selected_person_final = None
            else:
                selected_person_final = st.session_state['selected_person']

            default_status_idx = 0
            if st.session_state['add_status'] in valid_transaction_statuses_lower:
                default_status_idx = valid_transaction_statuses_lower.index(st.session_state['add_status'])
            
            status = st.selectbox("Transaction Status", valid_transaction_statuses_lower,
                                  index=default_status_idx,
                                  key='add_status')
            description = st.text_input("Description", value=st.session_state['add_description'], key='add_description')

        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            validation_passed = True
            if not selected_person_final:
                st.warning("Please select a valid person.")
                validation_passed = False
            if amount <= 0:
                st.warning("Amount must be greater than 0.")
                validation_passed = False
            if not str(reference_number).strip(): # Use str() to handle potential None/NaN from widget
                if st.session_state['payment_method'] == "cheque":
                    st.warning(f"🚨 Reference Number is **REQUIRED** for cheque transactions.")
                else:
                    st.warning(f"🚨 Reference Number is required.")
                validation_passed = False
            
            if validation_passed:
                try:
                    new_row = {
                        "date": date.strftime("%Y-%m-%d"),
                        "person": selected_person_final,
                        "amount": amount,
                        "type": 'paid_to_me' if st.session_state['selected_transaction_type'] == "Paid to Me" else 'i_paid',
                        "status": status, # This 'status' column is redundant with 'transaction_status' but kept for compatibility
                        "description": description,
                        "payment_method": st.session_state['payment_method'],
                        "reference_number": str(reference_number).strip(), # Explicitly cast to string before saving
                        "cheque_status": cheque_status_val if st.session_state['payment_method'] == "cheque" else None,
                        "transaction_status": status # Use the selected status for transaction_status
                    }
                    pd.DataFrame([new_row]).to_csv(CSV_FILE, mode='a', header=False, index=False)
                    
                    # Read the updated CSV and CLEAN IT before generating HTML
                    updated_df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False) # Re-read with dtype fix
                    updated_df['reference_number'] = updated_df['reference_number'].apply(
                        lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
                    )
                    updated_df = clean_payments_data(updated_df)
                    updated_df.to_csv(CSV_FILE, index=False) # Save the cleaned data back to CSV

                    html_generated = generate_html_summary(updated_df)
                    git_pushed = False
                    if html_generated: # Only push to git if HTML generation was successful
                        git_pushed = git_push()
                    
                    if html_generated and git_pushed:
                        st.success("Transaction added successfully and GitHub updated.")
                    elif html_generated:
                        st.success("Transaction added successfully. HTML summary generated.")
                    else:
                        st.error("Transaction added, but HTML summary or GitHub update failed.")

                    st.session_state['reset_add_form'] = True # Set flag for next rerun
                    st.rerun() # Rerun to clear form inputs visually
                except Exception as e:
                    st.error(f"Error saving transaction: {e}")

# ------------------ Tab 2: View Transactions ------------------
with tab2:
    st.subheader("Transaction History")

    try:
        # CRITICAL FIX: Force reference_number to be read as string here too
        df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
        df['reference_number'] = df['reference_number'].apply(
            lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
        )

        # Check if DataFrame is empty
        if df.empty:
            st.info("No transactions recorded yet.")
            
        # Prepare DataFrame for display, which includes validation and formatting
        # Use a temporary DataFrame for filtering to avoid modifying the original 'df'
        temp_filtered_df = df.copy()

        # Filters (apply filters on the original columns, then display with _display columns)
        col1, col2, col3 = st.columns(3)
        with col1:
            view_filter = st.radio("Filter by Type", ["All", "Received", "Paid"], horizontal=True, key='view_filter_radio')
        with col2:
            method_filter = st.selectbox("Payment Method", ["All", "Cash", "Cheque"], key='method_filter_select')
        with col3:
            status_filter = st.selectbox("Status", ["All", "Completed", "Pending", "Received/Given", "Processing", "Bounced", "Processing Done"], key='status_filter_select')

        # Apply filters to the original columns for accurate filtering logic
        if view_filter != "All":
            temp_filtered_df = temp_filtered_df[temp_filtered_df['type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'}) == view_filter]
        if method_filter != "All":
            temp_filtered_df = temp_filtered_df[temp_filtered_df['payment_method'].astype(str).str.lower() == method_filter.lower()]
        if status_filter != "All":
            if status_filter.lower() in valid_transaction_statuses_lower: # Check if it's a general transaction status
                temp_filtered_df = temp_filtered_df[temp_filtered_df['transaction_status'].astype(str).str.lower() == status_filter.lower()]
            elif status_filter.lower() in valid_cheque_statuses_lower: # Check if it's a cheque specific status
                temp_filtered_df = temp_filtered_df[temp_filtered_df['cheque_status'].astype(str).str.lower() == status_filter.lower()]


        # Now apply the display preparation to the filtered data
        filtered_df_for_display = prepare_dataframe_for_display(temp_filtered_df)
        # Add original index for editing purposes, ensuring it's available even if the original df was empty
        if not filtered_df_for_display.empty:
            filtered_df_for_display['original_index'] = temp_filtered_df.index
        else:
            st.info("No transactions match the current filters.")


        # Display DataFrame with clearer column names using the _display columns
        display_columns = {
            'original_index': 'ID',
            'formatted_date': 'Date',
            'person': 'Person',
            'amount_display': 'Amount',
            'type_display': 'Type',
            'payment_method': 'Method',
            'cheque_status_display': 'Cheque Status', # Using validated display column
            'reference_number_display': 'Reference No.', # Using validated display column
            'transaction_status_display': 'Status', # Using validated display column
            'description': 'Description'
        }

        if not filtered_df_for_display.empty:
            st.dataframe(
                filtered_df_for_display[list(display_columns.keys())].rename(columns=display_columns),
                use_container_width=True,
                hide_index=True
            )

            # Edit Section
            st.markdown("---")
            st.subheader("Edit Transaction")

            edit_options = [f"ID: {row['original_index']} - {row['formatted_date']} - {row['person']} - {row['amount_display']}"
                           for idx, row in filtered_df_for_display.iterrows()]

            selected_edit_option = st.selectbox(
                "Select transaction to edit:",
                ["Select a transaction"] + edit_options,
                key='select_edit_transaction'
            )

            if selected_edit_option != "Select a transaction":
                selected_original_index = int(selected_edit_option.split(' - ')[0].replace('ID: ', ''))

                # Set editing_row_idx and load data for editing form
                if st.session_state['editing_row_idx'] != selected_original_index:
                    st.session_state['editing_row_idx'] = selected_original_index
                    # FIX: Explicitly handle reference_number to avoid 'nan' in edit form
                    loaded_edit_data = df.loc[st.session_state['editing_row_idx']].to_dict()
                    # Ensure reference_number is a clean string for the widget
                    ref_num_for_widget = loaded_edit_data.get('reference_number', '')
                    if pd.isna(ref_num_for_widget) or str(ref_num_for_widget).strip().lower() == 'nan' or str(ref_num_for_widget).strip().lower() == 'none':
                        loaded_edit_data['reference_number'] = ''
                    else:
                        loaded_edit_data['reference_number'] = str(ref_num_for_widget).strip()

                    st.session_state['temp_edit_data'] = loaded_edit_data
                    st.rerun() # Rerun to populate the form with data

        # Edit Form (appears when editing_row_idx is set)
        if st.session_state['editing_row_idx'] is not None and st.session_state.get('temp_edit_data'):
            st.markdown("---")
            st.subheader(f"Editing Transaction ID: {st.session_state['editing_row_idx']}")
            edit_data = st.session_state['temp_edit_data']

            with st.form("edit_transaction_form"):
                col1_edit, col2_edit = st.columns(2)
                with col1_edit:
                    edited_amount = st.number_input("Amount (Rs.)", value=float(edit_data.get('amount', 0.0)), format="%.2f", key='edit_amount')

                    try:
                        default_date_value = datetime.strptime(str(edit_data.get('date', '')), "%Y-%m-%d").date()
                    except (ValueError, TypeError):
                        default_date_value = datetime.now().date()
                    edited_date = st.date_input("Date", value=default_date_value, key='edit_date')

                    edited_payment_method = st.radio(
                        "Payment Method",
                        ["cash", "cheque"],
                        horizontal=True,
                        index=["cash", "cheque"].index(str(edit_data.get('payment_method', 'cash')).lower()),
                        key='edit_payment_method'
                    )

                    edited_cheque_status = ""
                    if edited_payment_method == "cheque":
                        cheque_status_val = str(edit_data.get('cheque_status', 'processing')).lower()
                        if cheque_status_val not in valid_cheque_statuses_lower:
                            cheque_status_val = 'processing' # Default to a valid status if current is invalid
                        edited_cheque_status = st.selectbox(
                            "Cheque Status",
                            valid_cheque_statuses_lower,
                            index=valid_cheque_statuses_lower.index(cheque_status_val),
                            key='edit_cheque_status'
                        )
                    else:
                        edited_cheque_status = None # Ensure it's None for cash payments

                    edited_reference_number = st.text_input(
                        "Reference Number",
                        value=str(edit_data.get('reference_number', '')), # This should now correctly show the string
                        key='edit_reference_number'
                    )

                with col2_edit:
                    try:
                        people_df = pd.read_csv(PEOPLE_FILE)
                        people_list = people_df['name'].dropna().astype(str).tolist() # Ensure strings
                        current_person = str(edit_data.get('person', ''))

                        # Handle case where person might not be in current people list
                        if current_person not in people_list and current_person != '':
                            people_list = [current_person] + people_list
                            default_index = 0
                        elif current_person == '': # If person is empty, default to first option or 'Select...'
                             default_index = 0 if len(people_list) > 0 else 0
                        else:
                            default_index = people_list.index(current_person)

                        edited_person = st.selectbox(
                            "Select Person",
                            people_list,
                            index=default_index,
                            key='edit_person'
                        )
                    except Exception as e:
                        st.error(f"Error loading people data for edit: {e}")
                        edited_person = str(edit_data.get('person', '')) # Fallback to existing value

                    transaction_status_val = str(edit_data.get('transaction_status', 'completed')).lower()
                    if transaction_status_val not in valid_transaction_statuses_lower:
                        transaction_status_val = 'completed' # Default to a valid status if current is invalid
                    edited_transaction_status = st.selectbox(
                        "Transaction Status",
                        valid_transaction_statuses_lower,
                        index=valid_transaction_statuses_lower.index(transaction_status_val),
                        key='edit_transaction_status'
                    )

                    edited_description = st.text_input(
                        "Description",
                        value=str(edit_data.get('description', '')),
                        key='edit_description'
                    )

                # Form submit and cancel buttons
                col1_btns, col2_btns = st.columns(2)
                with col1_btns:
                    submit_button = st.form_submit_button("💾 Save Changes")
                with col2_btns:
                    cancel_button = st.form_submit_button("❌ Cancel")

                if submit_button:
                    validation_passed = True
                    if edited_amount <= 0:
                        st.warning("Amount must be greater than 0.")
                        validation_passed = False
                    if not str(edited_reference_number).strip(): # Use str() to handle potential None/NaN from widget
                        if edited_payment_method == "cheque":
                            st.warning(f"🚨 Reference Number is **REQUIRED** for cheque transactions.")
                        else:
                            st.warning(f"🚨 Reference Number is required.")
                        validation_passed = False
                    
                    if validation_passed:
                        try:
                            df.loc[st.session_state['editing_row_idx']] = {
                                "date": edited_date.strftime("%Y-%m-%d"),
                                "person": edited_person,
                                "amount": edited_amount,
                                "type": edit_data['type'], # Keep original type
                                "status": edited_transaction_status, # Update 'status' column (redundant but kept)
                                "description": edited_description,
                                "payment_method": edited_payment_method,
                                "reference_number": str(edited_reference_number).strip(), # Explicitly cast to string
                                "cheque_status": edited_cheque_status, # Will be None for cash
                                "transaction_status": edited_transaction_status # Update 'transaction_status' column
                            }
                            df.to_csv(CSV_FILE, index=False)

                            updated_df_after_edit = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False) # Re-read with dtype fix
                            updated_df_after_edit['reference_number'] = updated_df_after_edit['reference_number'].apply(
                                lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
                            )
                            updated_df_after_edit = clean_payments_data(updated_df_after_edit)
                            updated_df_after_edit.to_csv(CSV_FILE, index=False) # Save the cleaned DF
                            
                            generate_html_summary(updated_df_after_edit) # Pass the CLEANED df
                            git_push()
                            st.success("✅ Transaction updated successfully!")
                            st.session_state['editing_row_idx'] = None
                            st.session_state['temp_edit_data'] = {}
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving transaction: {e}")

                if cancel_button:
                    st.session_state['editing_row_idx'] = None
                    st.session_state['temp_edit_data'] = {}
                    st.rerun()

    except Exception as e:
            st.error(f"Error loading transaction history: {str(e)}")
            

# ------------------ Tab 3: Manage People ------------------
with tab3:
    st.subheader("Manage People")
    with st.expander("Add New Person"):
        with st.form("person_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name").strip() # Strip whitespace from name
            category = c2.selectbox("Category", ["investor", "client"])
            if st.form_submit_button("Add Person"):
                if not name: # Check if name is empty after stripping
                    st.warning("Name is required.")
                else:
                    try:
                        if not os.path.exists(PEOPLE_FILE):
                            pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)

                        df = pd.read_csv(PEOPLE_FILE)
                        # Convert 'name' column to string for consistent comparison
                        df['name'] = df['name'].astype(str)
                        if name.lower() in df['name'].str.lower().values: # Case-insensitive check
                            st.warning(f"Person '{name}' already exists.")
                        else:
                            pd.DataFrame([[name, category]], columns=["name", "category"])\
                                .to_csv(PEOPLE_FILE, mode='a', header=False, index=False)
                            st.success(f"{name} added!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error saving person: {e}")

    try:
        if os.path.exists(PEOPLE_FILE):
            ppl = pd.read_csv(PEOPLE_FILE)
            if not ppl.empty:
                st.dataframe(ppl, use_container_width=True, hide_index=True)
                
                # Ensure selectbox defaults gracefully if no people are present
                if not ppl['name'].empty:
                    to_del = st.selectbox("Delete Person", ppl['name'].astype(str).tolist(), key='delete_person_select')
                    if st.button("Delete", key='delete_person_button'):
                        try:
                            tx = pd.read_csv(CSV_FILE)
                            # Ensure 'person' column in transactions is string for comparison
                            tx['person'] = tx['person'].astype(str)
                            if to_del in tx['person'].values:
                                st.error(f"Cannot delete '{to_del}'. There are transactions associated with this person.")
                            else:
                                ppl = ppl[ppl['name'].astype(str) != to_del]
                                ppl.to_csv(PEOPLE_FILE, index=False)
                                st.success(f"'{to_del}' deleted.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting person: {e}")
                else:
                    st.info("No people records to delete.")
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
        df_bal = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False) # Apply dtype fix here too
        df_bal['reference_number'] = df_bal['reference_number'].apply(
            lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
        )
        if not df_bal.empty:
            # Ensure columns are treated as strings and amounts as numeric for calculations
            df_bal['amount'] = pd.to_numeric(df_bal['amount'], errors='coerce').fillna(0.0)
            df_bal['type'] = df_bal['type'].astype(str).str.lower()
            df_bal['payment_method'] = df_bal['payment_method'].astype(str).str.lower()

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
