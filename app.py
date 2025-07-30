import streamlit as st
import pandas as pd
from datetime import datetime
import os
from git import Repo
import numpy as np
import uuid
from fpdf import FPDF

def init_state():
    keys = [
        'selected_transaction_type', 'payment_method', 'editing_row_idx', 'selected_person', 'reset_add_form',
        'add_amount', 'add_date', 'add_reference_number', 'add_cheque_status', 'add_status', 'add_description',
        'temp_edit_data', 'invoice_person_name', 'invoice_type', 'invoice_start_date', 'invoice_end_date',
        'generated_invoice_pdf_path', 'show_download_button',
        'view_person_filter',
        'view_reference_number_search',
        'selected_client_for_expense', 'add_client_expense_amount', 'add_client_expense_date',
        'add_client_expense_category', 'add_client_expense_description', 'reset_client_expense_form',
        'add_client_expense_quantity' # New: Quantity for client expenses
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
        'temp_edit_data': {},
        'invoice_person_name': "Select...",
        'invoice_type': 'Invoice for Person (All Transactions)',
        'invoice_start_date': datetime.now().date().replace(day=1),
        'invoice_end_date': datetime.now().date(),
        'generated_invoice_pdf_path': None,
        'show_download_button': False,
        'view_person_filter': "All",
        'view_reference_number_search': "",
        'selected_client_for_expense': "Select...",
        'add_client_expense_amount': None,
        'add_client_expense_date': None,
        'add_client_expense_category': 'General',
        'add_client_expense_description': '',
        'reset_client_expense_form': False,
        'add_client_expense_quantity': 1.0 # Default quantity
    }
    for k in keys:
        if k not in st.session_state:
            st.session_state[k] = defaults[k]

init_state()

REPO_PATH = os.getcwd()
CSV_FILE = os.path.join(REPO_PATH, "payments.csv")
PEOPLE_FILE = os.path.join(REPO_PATH, "people.csv")
CLIENT_EXPENSES_FILE = os.path.join(REPO_PATH, "client_expenses.csv")
SUMMARY_FILE = os.path.join(REPO_PATH, "docs/index.html")
SUMMARY_URL = "https://atonomous.github.io/payments-summary/"
INVOICE_DIR = os.path.join(REPO_PATH, "docs", "invoices")

valid_cheque_statuses_lower = ["received/given", "processing", "bounced", "processing done"]
valid_transaction_statuses_lower = ["completed", "pending"]
valid_expense_categories = ["General", "Salaries", "Rent", "Utilities", "Supplies", "Travel", "Other"]

def clean_payments_data(df):
    if df.empty:
        return df

    cols_to_check = ["payment_method", "cheque_status", "transaction_status", "reference_number", "date", "amount", "person", "type", "status", "description"]
    for col in cols_to_check:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].astype(str).replace('nan', '').replace('None', '').str.strip()

    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    cash_payments_mask = df['payment_method'].str.lower() == 'cash'
    df.loc[cash_payments_mask, 'cheque_status'] = ''

    for index, row in df.iterrows():
        ref_num_lower = str(row['reference_number']).lower()
        trans_status_current_lower = str(row['transaction_status']).lower()
        cheque_status_current_lower = str(row['cheque_status']).lower()
        payment_method_lower = str(row['payment_method']).lower()

        if ref_num_lower in valid_transaction_statuses_lower:
            if trans_status_current_lower not in valid_transaction_statuses_lower:
                df.loc[index, 'transaction_status'] = ref_num_lower
            df.loc[index, 'reference_number'] = ''
        elif ref_num_lower in valid_cheque_statuses_lower and payment_method_lower == 'cheque':
            if cheque_status_current_lower not in valid_cheque_statuses_lower:
                df.loc[index, 'cheque_status'] = ref_num_lower
            df.loc[index, 'reference_number'] = ''

        if df.loc[index, 'transaction_status'].lower() not in valid_transaction_statuses_lower:
            df.loc[index, 'transaction_status'] = 'completed'

        if payment_method_lower == 'cheque':
            if df.loc[index, 'cheque_status'].lower() not in valid_cheque_statuses_lower:
                df.loc[index, 'cheque_status'] = 'processing'
        else:
            df.loc[index, 'cheque_status'] = ''

    df = df[~((df['date'].isna()) & (df['person'] == '') & (df['amount'] == 0.0))]
    return df

def init_files():
    try:
        if not os.path.exists(CSV_FILE):
            pd.DataFrame(columns=[
                "date", "person", "amount", "type", "status",
                "description", "payment_method", "reference_number",
                "cheque_status", "transaction_status"
            ]).to_csv(CSV_FILE, index=False)
            st.toast(f"Created new {CSV_FILE}")
        else:
            df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
            df['reference_number'] = df['reference_number'].apply(
                lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
            )
            if 'receipt_number' in df.columns or 'cheque_number' in df.columns:
                df['reference_number'] = df.apply(
                    lambda row: row['receipt_number'] if row['payment_method'] == 'cash'
                    else (row['cheque_number'] if row['payment_method'] == 'cheque' else ''),
                    axis=1
                ).fillna('')
                df = df.drop(columns=['receipt_number', 'cheque_number'], errors='ignore')
                st.toast("Migrated old reference number columns.")
            df = clean_payments_data(df)
            df.to_csv(CSV_FILE, index=False)
            st.toast("Payments data cleaned and saved.")

        if not os.path.exists(PEOPLE_FILE):
            pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)
            st.toast(f"Created new {PEOPLE_FILE}")
        else:
            df = pd.read_csv(PEOPLE_FILE)
            if 'category' not in df.columns:
                df['category'] = 'client'
                df.to_csv(PEOPLE_FILE, index=False)
            df['name'] = df['name'].astype(str)
            df.to_csv(PEOPLE_FILE, index=False)

        if not os.path.exists(CLIENT_EXPENSES_FILE):
            pd.DataFrame(columns=[
                "original_transaction_ref_num", "expense_date", "expense_person",
                "expense_category", "expense_amount", "expense_quantity", "expense_description" # Added expense_quantity
            ]).to_csv(CLIENT_EXPENSES_FILE, index=False)
            st.toast(f"Created new {CLIENT_EXPENSES_FILE}")
        else:
            df_exp = pd.read_csv(CLIENT_EXPENSES_FILE, dtype={'original_transaction_ref_num': str, 'expense_person': str}, keep_default_na=False)
            
            # Add 'expense_quantity' column if it doesn't exist
            if 'expense_quantity' not in df_exp.columns:
                df_exp['expense_quantity'] = 1.0 # Default to 1.0 for existing entries
                st.toast("Added 'expense_quantity' column to client_expenses.csv")

            for col in ["original_transaction_ref_num", "expense_person", "expense_category", "expense_description"]:
                if col in df_exp.columns:
                    df_exp[col] = df_exp[col].astype(str).replace('nan', '').replace('None', '').str.strip()
            if 'expense_amount' in df_exp.columns:
                df_exp['expense_amount'] = pd.to_numeric(df_exp['expense_amount'], errors='coerce').fillna(0.0)
            if 'expense_quantity' in df_exp.columns: # Ensure quantity is numeric
                df_exp['expense_quantity'] = pd.to_numeric(df_exp['expense_quantity'], errors='coerce').fillna(1.0)
            if 'expense_date' in df_exp.columns:
                df_exp['expense_date'] = pd.to_datetime(df_exp['expense_date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
            df_exp.to_csv(CLIENT_EXPENSES_FILE, index=False)
            st.toast("Client expenses data cleaned and saved.")

    except Exception as e:
        st.error(f"Error initializing files: {e}")

init_files()

def git_push():
    try:
        repo = Repo(REPO_PATH)
        if repo.is_dirty(untracked_files=True):
            repo.git.add(update=True)
            repo.git.add(all=True)
        if repo.index.diff("HEAD"):
            repo.index.commit("Automated update: payment records")
        else:
            return True
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
    df_display = df.copy()
    for col in ['reference_number', 'cheque_status', 'transaction_status', 'payment_method', 'description', 'person', 'type', 'status']:
        if col in df_display.columns:
            df_display[col] = df_display[col].astype(str).replace('nan', '').replace('None', '').str.strip()
        else:
            df_display[col] = ''

    df_display['amount'] = pd.to_numeric(df_display['amount'], errors='coerce').fillna(0.0)
    df_display['amount_display'] = df_display['amount'].apply(lambda x: f"Rs. {x:,.2f}")
    
    df_display['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
    df_display['formatted_date'] = df_display['date_parsed'].dt.strftime('%Y-%m-%d').fillna('-') # Changed fillna('') to fillna('-')
    
    df_display['cheque_status_cleaned'] = df_display.apply(
        lambda row: None if row['payment_method'].lower() == 'cash' else (
            str(row['cheque_status']) if pd.notna(row['cheque_status']) else None
        ), axis=1
    )
    df_display['cheque_status_display'] = df_display['cheque_status_cleaned'].apply(
        lambda x: next((s.capitalize() for s in valid_cheque_statuses_lower if x is not None and str(x).lower() == s), '-')
    )
    df_display['transaction_status_display'] = df_display.apply(
        lambda row: str(row['transaction_status']).capitalize() if str(row['transaction_status']).lower() in valid_transaction_statuses_lower else '-',
        axis=1
    )
    df_display['reference_number_display'] = df_display.apply(
        lambda row: str(row['reference_number']) if str(row['reference_number']).strip() != '' else '-',
        axis=1
    )
    df_display['type_display'] = df_display['type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'}).fillna('')
    
    # Ensure payment_method is also explicitly handled for display
    df_display['payment_method_display'] = df_display['payment_method'].apply(
        lambda x: str(x).capitalize() if str(x).strip() != '' else '-'
    )

    return df_display

def generate_html_summary(df):
    print("Attempting to generate HTML summary...")
    try:
        transactions_display = prepare_dataframe_for_display(df)
        df_for_totals = df.copy()
        df_for_totals['amount'] = pd.to_numeric(df_for_totals['amount'], errors='coerce').fillna(0.0)
        df_for_totals['type'] = df_for_totals['type'].astype(str).str.lower()
        df_for_totals['payment_method'] = df_for_totals['payment_method'].astype(str).str.lower()
        df_for_totals['transaction_status'] = df_for_totals['transaction_status'].astype(str).str.lower()

        payment_totals = df_for_totals.groupby(['type', 'payment_method'])['amount'].sum().unstack().fillna(0)

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

        people_df = pd.read_csv(PEOPLE_FILE)
        person_options_html = ''.join(f'<option value="{name}">{name}</option>' for name in sorted(people_df['name'].unique()))

        client_expenses_df_all = pd.DataFrame()
        if os.path.exists(CLIENT_EXPENSES_FILE) and os.path.getsize(CLIENT_EXPENSES_FILE) > 0:
            client_expenses_df_all = pd.read_csv(CLIENT_EXPENSES_FILE, dtype={'original_transaction_ref_num': str, 'expense_person': str}, keep_default_na=False)
            client_expenses_df_all['expense_amount'] = pd.to_numeric(client_expenses_df_all['expense_amount'], errors='coerce').fillna(0.0)
            client_expenses_df_all['expense_person'] = client_expenses_df_all['expense_person'].astype(str)
            client_expenses_df_all['expense_date'] = pd.to_datetime(client_expenses_df_all['expense_date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
            # Ensure expense_quantity is loaded and cleaned
            if 'expense_quantity' not in client_expenses_df_all.columns:
                client_expenses_df_all['expense_quantity'] = 1.0
            client_expenses_df_all['expense_quantity'] = pd.to_numeric(client_expenses_df_all['expense_quantity'], errors='coerce').fillna(1.0)
            
            # Calculate Total Line Amount for client expenses
            client_expenses_df_all['total_line_amount'] = client_expenses_df_all['expense_amount'] * client_expenses_df_all['expense_quantity']
        
        # Initialize with expected columns to prevent KeyError if empty
        total_paid_to_clients = pd.DataFrame(columns=['client_name', 'total_paid_to_client'])
        if not df_for_totals[df_for_totals['type'] == 'i_paid'].empty:
            total_paid_to_clients = df_for_totals[df_for_totals['type'] == 'i_paid'].groupby('person')['amount'].sum().reset_index()
            total_paid_to_clients.rename(columns={'person': 'client_name', 'amount': 'total_paid_to_client'}, inplace=True)

        # Initialize with expected columns to prevent KeyError if empty
        total_spent_by_clients = pd.DataFrame(columns=['client_name', 'total_spent_by_client'])
        if not client_expenses_df_all.empty:
            total_spent_by_clients = client_expenses_df_all.groupby('expense_person')['total_line_amount'].sum().reset_index() # Sum of total_line_amount
            total_spent_by_clients.rename(columns={'expense_person': 'client_name', 'total_line_amount': 'total_spent_by_client'}, inplace=True)

        expected_client_summary_cols = ['client_name', 'total_paid_to_client', 'total_spent_by_client']
        summary_by_client_df = pd.merge(
            total_paid_to_clients,
            total_spent_by_clients,
            on='client_name',
            how='outer'
        )
        # Ensure all expected columns are present after merge and fill NaNs
        for col in expected_client_summary_cols:
            if col not in summary_by_client_df.columns:
                summary_by_client_df[col] = 0
        summary_by_client_df.fillna(0, inplace=True) # Fill NaNs that might result from outer merge
        summary_by_client_df['client_name'] = summary_by_client_df['client_name'].astype(str).fillna('')
        summary_by_client_df['total_paid_to_client'] = pd.to_numeric(summary_by_client_df['total_paid_to_client'], errors='coerce').fillna(0)
        summary_by_client_df['total_spent_by_client'] = pd.to_numeric(summary_by_client_df['total_spent_by_client'], errors='coerce').fillna(0)
        summary_by_client_df['remaining_balance'] = summary_by_client_df['total_paid_to_client'] - summary_by_client_df['total_spent_by_client']


        client_overview_html = ""
        if not summary_by_client_df.empty:
            client_overview_html += """
            <h3 class="section-subtitle"><i class="fas fa-chart-pie"></i> Spending Overview by Client</h3>
            <table class="client-summary-table">
                <thead>
                    <tr>
                        <th>Client Name</th>
                        <th>Total Paid to Client</th>
                        <th>Total Spent by Client</th>
                        <th>Remaining Balance</th>
                    </tr>
                </thead>
                <tbody>
            """
            for idx, row in summary_by_client_df.iterrows():
                balance_class = 'positive-balance' if row['remaining_balance'] >= 0 else 'negative-balance'
                client_overview_html += f"""
                    <tr>
                        <td>{row['client_name']}</td>
                        <td>Rs. {row['total_paid_to_client']:,.2f}</td>
                        <td>Rs. {row['total_spent_by_client']:,.2f}</td>
                        <td class="{balance_class}">Rs. {row['remaining_balance']:,.2f}</td>
                    </tr>
                """
            client_overview_html += """
                </tbody>
            </table>
            """
        else:
            client_overview_html = "<p class='no-results'>No client spending overview available yet.</p>"

        detailed_expenses_html = ""
        total_client_expenses_grand = 0.0
        if not client_expenses_df_all.empty:
            total_client_expenses_grand = client_expenses_df_all['total_line_amount'].sum()

            detailed_expenses_html += f"""
            <h3 class="section-subtitle"><i class="fas fa-list-alt"></i> Detailed Client Expenses</h3>
            <div style="text-align: right; margin-bottom: 10px; font-weight: bold; font-size: 1.2em; color: #34495e;">
                Total Client Expenses: Rs. {total_client_expenses_grand:,.2f}
            </div>
            <table class="detailed-expenses-table">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Client Name</th>
                        <th>Category</th>
                        <th>Amount (Unit)</th>
                        <th>Quantity</th>
                        <th>Total Line Amount</th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody>
            """
            for idx, row in client_expenses_df_all.iterrows():
                detailed_expenses_html += f"""
                    <tr>
                        <td>{row['expense_date']}</td>
                        <td>{row['expense_person']}</td>
                        <td>{row['expense_category']}</td>
                        <td>Rs. {row['expense_amount']:,.2f}</td>
                        <td>{row['expense_quantity']:,.0f}</td> <!-- Changed to .0f for integer quantity -->
                        <td>Rs. {row['total_line_amount']:,.2f}</td>
                        <td>{row['expense_description'] if row['expense_description'] else '-'}</td>
                    </tr>
                """
            detailed_expenses_html += """
                </tbody>
            </table>
            """
        else:
            detailed_expenses_html = "<p class='no-results'>No detailed client expenses to display yet.</p>"

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
        .section-subtitle {{
            font-size: 1.3em;
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
            border-bottom: 1px solid #eee;
            padding-bottom: 8px;
            display: flex;
            align-items: center;
        }}
        .section-subtitle i {{
            margin-right: 8px;
            color: #28a745;
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
        .filter-group input[type="date"],
        .filter-group input[type="text"] {{
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
        .filter-group input[type="date"]:focus,
        .filter-group input[type="text"]:focus {{
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
            overflow: hidden;
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

        .tabs {{
            margin-top: 30px;
            margin-bottom: 40px;
        }}
        .tab-buttons {{
            display: flex;
            border-bottom: 2px solid #ddd;
            margin-bottom: 20px;
        }}
        .tab-button {{
            padding: 12px 25px;
            cursor: pointer;
            font-size: 1.1em;
            font-weight: 500;
            color: #555;
            background-color: #f8f8f8;
            border: 1px solid #ddd;
            border-bottom: none;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            margin-right: 5px;
            transition: all 0.3s ease;
        }}
        .tab-button:hover {{
            background-color: #eee;
            color: #333;
        }}
        .tab-button.active {{
            background-color: #ffffff;
            color: #007bff;
            border-color: #007bff;
            border-bottom: 2px solid #ffffff;
            transform: translateY(2px);
            box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.05);
            z-index: 1;
        }}
        .tab-content {{
            background-color: #ffffff;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
            position: relative;
            top: -2px;
        }}
        .tab-pane {{
            display: none;
        }}
        .tab-pane.active {{
            display: block;
        }}

        .client-summary-table .positive-balance {{ color: #28a745; font-weight: 600; }}
        .client-summary-table .negative-balance {{ color: #dc3545; font-weight: 600; }}

        .download-button-container {{
            text-align: right;
            margin-bottom: 20px;
        }}
        .download-button {{
            background-color: #28a745;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 500;
            transition: background-color 0.3s ease, transform 0.2s ease;
            display: inline-flex;
            align-items: center;
        }}
        .download-button i {{
            margin-right: 8px;
        }}
        .download-button:hover {{
            background-color: #218838;
            transform: translateY(-2px);
        }}

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
            td:nth-of-type(1):before {{ content: "Date"; }}
            td:nth-of-type(2):before {{ content: "Person"; }}
            td:nth-of-type(3):before {{ content: "Amount"; }}
            td:nth-of-type(4):before {{ content: "Type"; }}
            td:nth-of-type(5):before {{ content: "Method"; }}
            td:nth-of-type(6):before {{ content: "Cheque Status"; }}
            td:nth-of-type(7):before {{ content: "Reference No."; }}
            td:nth-of-type(8):before {{ content: "Status"; }}
            td:nth-of-type(9):before {{ content: "Description"; }}

            .client-summary-table td:nth-of-type(1):before {{ content: "Client Name"; }}
            .client-summary-table td:nth-of-type(2):before {{ content: "Total Paid"; }}
            .client-summary-table td:nth-of-type(3):before {{ content: "Total Spent"; }}
            .client-summary-table td:nth-of-type(4):before {{ content: "Balance"; }}

            .detailed-expenses-table td:nth-of-type(1):before {{ content: "Date"; }}
            .detailed-expenses-table td:nth-of-type(2):before {{ content: "Client Name"; }}
            .detailed-expenses-table td:nth-of-type(3):before {{ content: "Category"; }}
            .detailed-expenses-table td:nth-of-type(4):before {{ content: "Amount"; }}
            td:nth-of-type(5):before {{ content: "Quantity"; }} /* New media query label */
            td:nth-of-type(6):before {{ content: "Total Line Amount"; }} /* New media query label */
            .detailed-expenses-table td:nth-of-type(7):before {{ content: "Description"; }}
        }}

        @media print {{
            body {{
                background-color: #fff;
                margin: 0;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                border-radius: 0;
                margin: 0;
                padding: 0;
                max-width: none;
            }}
            header, .summary-cards, .filters, .tabs, .tab-buttons, .tab-content {{
                box-shadow: none !important;
                border: none !important;
                margin: 0 !important;
                padding: 0 !important;
            }}
            .tab-button, .tab-pane {{
                display: block !important;
                width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
                background-color: #fff !important;
                border: none !important;
            }}
            .tab-buttons {{
                display: none;
            }}
            .tab-pane.active {{
                display: block;
            }}
            .download-button-container, .footer {{
                display: none;
            }}
            table {{
                box_shadow: none;
                border_radius: 0;
                margin_bottom: 20px;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 8px;
            }}
            .no-results {{
                display: none;
            }}
            .section-title, .section-subtitle {{
                page-break-after: avoid;
                margin-top: 20px;
                margin-bottom: 10px;
                padding-bottom: 5px;
                border-bottom: 1px solid #ccc;
            }}
        }}
    </style>
    <script>
        $(document).ready(function() {{
            const today = new Date();
            const oneMonthAgo = new Date();
            oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
            $('#start-date').val(oneMonthAgo.toISOString().split('T')[0]);
            $('#end-date').val(today.toISOString().split('T')[0]);

            applyFilters();

            $('.tab-button').on('click', function() {{
                const tabId = $(this).data('tab');
                $('.tab-button').removeClass('active');
                $(this).addClass('active');
                $('.tab-pane').removeClass('active');
                $('#' + tabId).addClass('active');
            }});

            $('.tab-button[data-tab="transactions-tab"]').click();
        }});

        function applyFilters() {{
            const startDate = $('#start-date').val();
            const endDate = $('#end-date').val();
            const person = $('#name-filter').val().toLowerCase();
            const type = $('#type-filter').val();
            const method = $('#method-filter').val().toLowerCase();
            const chequeStatus = $('#status-filter').val().toLowerCase();
            const referenceNumber = $('#reference-number-filter').val().toLowerCase();

            let visibleRows = 0;
            let totalAmount = 0; // Initialize total amount for filtered transactions

            $('#transactions-table tbody tr').each(function() {{
                const rowDate = $(this).data('date');
                const rowPerson = $(this).data('person').toString().toLowerCase();
                const rowType = $(this).data('type');
                const rowMethod = $(this).data('method').toString().toLowerCase();
                const rowChequeStatus = $(this).data('cheque-status').toString().toLowerCase();
                const rowReferenceNumber = $(this).data('reference-number').toString().toLowerCase();
                const rowAmount = parseFloat($(this).data('amount-raw')); // Get raw amount for calculation

                const datePass = (!startDate || rowDate >= startDate) && (!endDate || rowDate <= endDate);
                const personPass = !person || rowPerson.includes(person);
                const typePass = !type || rowType === type;
                const methodPass = !method || rowMethod === method;
                const chequeStatusPass = !chequeStatus || (rowChequeStatus && rowChequeStatus.includes(chequeStatus));
                const referenceNumberPass = !referenceNumber || rowReferenceNumber.includes(referenceNumber);

                if (datePass && personPass && typePass && methodPass && chequeStatusPass && referenceNumberPass) {{
                    $(this).show();
                    visibleRows++;
                    totalAmount += rowAmount; // Add to total if visible
                }} else {{
                    $(this).hide();
                }}
            }});

            // Update the total amount display
            $('#total-displayed-amount').text('Rs. ' + totalAmount.toLocaleString('en-IN', {{ minimumFractionDigits: 2, maximumFractionDigits: 2 }}));


            if (visibleRows === 0) {{
                $('#no-results').show();
                $('#transactions-table').hide();
            }} else {{
                $('#no-results').hide();
                $('#transactions-table').show();
            }}
        }}

        function resetFilters() {{
            const today = new Date();
            const oneMonthAgo = new Date();
            oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
            $('#start-date').val(oneMonthAgo.toISOString().split('T')[0]);
            $('#end-date').val(today.toISOString().split('T')[0]);
            $('#name-filter').val('');
            $('#type-filter').val('');
            $('#method-filter').val('');
            $('#status-filter').val('');
            $('#reference-number-filter').val('');
            applyFilters(); // Re-apply filters after resetting
        }}

        function downloadPdf() {{
            window.print();
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
                
                <div class="filter-group">
                    <label for="reference-number-filter">Reference Number</label>
                    <input type="text" id="reference-number-filter" placeholder="Search by reference number">
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

        <div class="tabs">
            <div class="tab-buttons">
                <button class="tab-button" data-tab="transactions-tab">
                    <i class="fas fa-list"></i> All Transactions
                </button>
                <button class="tab-button" data-tab="client-expenses-tab">
                    <i class="fas fa-money-check-alt"></i> Client Expenses
                </button>
            </div>

            <div class="tab-content">
                <div id="transactions-tab" class="tab-pane">
                    <h2 class="section-title">
                        <i class="fas fa-list"></i> All Transactions
                    </h2>
                    <div style="text-align: right; margin-bottom: 10px; font-weight: bold; font-size: 1.2em; color: #34495e;">
                        Total Displayed Amount: <span id="total-displayed-amount">Rs. 0.00</span>
                    </div>
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

        for idx, row in df.iterrows():
            row_date = transactions_display.loc[idx, 'formatted_date'] if pd.notna(transactions_display.loc[idx, 'date_parsed']) else ''
            row_person = str(row['person'])
            row_type = str(row['type'])
            row_method = str(row['payment_method']).lower()
            row_cheque_status = str(row['cheque_status']).lower() if str(row['cheque_status']).strip() != '' else ''
            row_reference_number = str(row['reference_number']).lower() if str(row['reference_number']).strip() != '' else ''
            row_amount_raw = transactions_display.loc[idx, 'amount'] # Pass raw amount for JS calculation

            cheque_status_class = str(transactions_display.loc[idx, 'cheque_status_display']).lower().replace(' ', '-').replace('/', '-') if transactions_display.loc[idx, 'cheque_status_display'] != '-' else ''
            status_class = str(transactions_display.loc[idx, 'transaction_status_display']).lower().replace(' ', '-') if transactions_display.loc[idx, 'transaction_status_display'] != '-' else ''

            html += f"""
                            <tr data-date="{row_date}"
                                data-person="{row_person}"
                                data-type="{row_type}"
                                data-method="{row_method}"
                                data-cheque-status="{row_cheque_status}"
                                data-reference-number="{row_reference_number}"
                                data-amount-raw="{row_amount_raw}">
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

        html += f"""
                        </tbody>
                    </table>
                </div>

                <div id="client-expenses-tab" class="tab-pane">
                    <div class="download-button-container">
                        <button class="download-button" onclick="downloadPdf()">
                            <i class="fas fa-file-pdf"></i> Download as PDF
                        </button>
                    </div>
                    <h2 class="section-title">
                        <i class="fas fa-money-check-alt"></i> Client Expenses Overview
                    </h2>
                    {client_overview_html}
                    {detailed_expenses_html}
                </div>
            </div>
        </div>

        <div class="footer">
            <p><i class="fas fa-file-alt"></i> This report was automatically generated by Payment Tracker System</p>
            <p><i class="far fa-copyright"></i> {datetime.now().year} All Rights Reserved</p>
        </div>
    </div>
</body>
</html>"""

        os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML summary successfully generated at {SUMMARY_FILE}")
        return True
    except Exception as e:
        print(f"Error generating HTML summary: {e}")
        st.error(f"Error generating HTML summary: {e}")
        return False

def generate_invoice_pdf(person_name, transactions_df, start_date=None, end_date=None):
    try:
        class PDF(FPDF):
            def header(self):
                self.set_font("Arial", "B", 24)
                self.set_text_color(0, 123, 255)
                self.cell(0, 10, "Soft Tech Business System", ln=True, align='C')
                self.ln(10)
                self.set_draw_color(0, 123, 255)
                self.line(10, self.get_y(), 200, self.get_y())
                self.ln(10)

            def footer(self):
                self.set_y(-25)
                self.set_font("Arial", "I", 9)
                self.set_text_color(127, 140, 141)
                self.cell(0, 5, "Thank you for your business!", ln=True, align='C')
                self.cell(0, 5, f"© {datetime.now().year} Soft Tech Business System. All Rights Reserved.", ln=True, align='C')
                self.set_y(-15)
                self.set_font("Arial", size=8)
                self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", 0, 0, 'C')

        pdf = PDF()
        pdf.alias_nb_pages()
        pdf.add_page()

        pdf.set_font("Arial", "B", size=36)
        pdf.set_text_color(52, 73, 94)
        pdf.cell(0, 20, "INVOICE", ln=True, align='C')
        pdf.ln(5)

        pdf.set_font("Arial", size=12)
        pdf.set_text_color(68, 68, 68)
        invoice_id = str(uuid.uuid4()).split('-')[0].upper()
        invoice_date = datetime.now().strftime('%Y-%m-%d')
        
        pdf.set_x(120) 
        pdf.cell(0, 7, f"Invoice #: INV-{invoice_id}", ln=True, align='L')
        pdf.set_x(120)
        pdf.cell(0, 7, f"Date: {invoice_date}", ln=True, align='L')
        pdf.ln(10)

        pdf.set_font("Arial", "B", size=14)
        pdf.set_text_color(52, 73, 94)
        pdf.cell(0, 10, "Bill To:", ln=True)
        pdf.set_font("Arial", size=12)
        pdf.set_text_color(85, 85, 85)
        pdf.cell(0, 7, person_name, ln=True)
        pdf.ln(5)

        pdf.set_font("Arial", "B", size=12)
        pdf.set_text_color(52, 73, 94)
        pdf.cell(0, 7, "Invoice For:", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.set_text_color(85, 85, 85)
        
        # Display date range in invoice
        if start_date and end_date:
            pdf.cell(0, 7, f"Transactions from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}", ln=True)
        else:
            pdf.cell(0, 7, "All Transactions", ln=True)
        pdf.ln(10)

        pdf.set_fill_color(233, 236, 239)
        pdf.set_text_color(73, 80, 87)
        pdf.set_font("Arial", "B", size=8)
        
        # Define column widths for PDF: Date, Ref No., Method, Description, Quantity, Type, Chq. Status, Amount, Line Total
        # Adjusted widths for better fit
        col_widths = [20, 20, 20, 30, 15, 15, 25, 25, 25] # Total 195

        pdf.cell(col_widths[0], 10, "Date", 1, 0, 'L', 1)
        pdf.cell(col_widths[1], 10, "Ref. No.", 1, 0, 'L', 1)
        pdf.cell(col_widths[2], 10, "Method", 1, 0, 'L', 1)
        pdf.cell(col_widths[3], 10, "Description", 1, 0, 'L', 1)
        pdf.cell(col_widths[4], 10, "Qty", 1, 0, 'C', 1) # Quantity header
        pdf.cell(col_widths[5], 10, "Type", 1, 0, 'L', 1)
        pdf.cell(col_widths[6], 10, "Chq. Status", 1, 0, 'L', 1)
        pdf.cell(col_widths[7], 10, "Amount", 1, 0, 'R', 1) # Unit Amount
        pdf.cell(col_widths[8], 10, "Line Total", 1, 1, 'R', 1) # Line Total header

        pdf.set_font("Arial", size=8)
        pdf.set_text_color(51, 51, 51)
        total_invoice_amount = 0.0 # Renamed for clarity for invoice total

        if not transactions_df.empty:
            transactions_df_sorted = transactions_df.sort_values(by='date_parsed', ascending=True)
            for i, row in enumerate(transactions_df_sorted.iterrows()):
                idx, row_data = row
                
                # Retrieve quantity from row_data, default to 1 if not present
                quantity = row_data.get('expense_quantity', 1.0)
                line_total = row_data['amount'] * quantity
                total_invoice_amount += line_total # Sum the line total

                if i % 2 == 0:
                    pdf.set_fill_color(248, 249, 250)
                else:
                    pdf.set_fill_color(255, 255, 255)

                # Get data for the row, ensuring they are strings and use display columns
                formatted_date = str(row_data['formatted_date'])
                reference_number_text = str(row_data['reference_number_display'])
                payment_method_display = str(row_data['payment_method_display'])
                description_text = str(row_data['description'] if row_data['description'] else '-')
                quantity_display = f"{quantity:,.0f}" # Format quantity as integer
                type_display = str(row_data['type_display'])
                cheque_status_display = str(row_data['cheque_status_display'])
                amount_display = f"Rs. {row_data['amount']:,.2f}"
                line_total_display = f"Rs. {line_total:,.2f}"

                row_height = 10 

                # Check for page break BEFORE drawing the row
                if pdf.get_y() + row_height + 55 > pdf.h:
                    pdf.add_page()
                    # Redraw headers
                    pdf.set_fill_color(233, 236, 239)
                    pdf.set_text_color(73, 80, 87)
                    pdf.set_font("Arial", "B", size=8)
                    pdf.cell(col_widths[0], 10, "Date", 1, 0, 'L', 1)
                    pdf.cell(col_widths[1], 10, "Ref. No.", 1, 0, 'L', 1)
                    pdf.cell(col_widths[2], 10, "Method", 1, 0, 'L', 1)
                    pdf.cell(col_widths[3], 10, "Description", 1, 0, 'L', 1)
                    pdf.cell(col_widths[4], 10, "Qty", 1, 0, 'C', 1)
                    pdf.cell(col_widths[5], 10, "Type", 1, 0, 'L', 1)
                    pdf.cell(col_widths[6], 10, "Chq. Status", 1, 0, 'L', 1)
                    pdf.cell(col_widths[7], 10, "Amount", 1, 0, 'R', 1)
                    pdf.cell(col_widths[8], 10, "Line Total", 1, 1, 'R', 1)
                    pdf.set_font("Arial", size=8)
                    pdf.set_text_color(51, 51, 51)

                # Draw cells for the row using standard cell method for consistent alignment
                pdf.cell(col_widths[0], row_height, formatted_date, 1, 0, 'L', 1)
                pdf.cell(col_widths[1], row_height, reference_number_text, 1, 0, 'L', 1)
                pdf.cell(col_widths[2], row_height, payment_method_display, 1, 0, 'L', 1)
                pdf.cell(col_widths[3], row_height, description_text, 1, 0, 'L', 1)
                pdf.cell(col_widths[4], row_height, quantity_display, 1, 0, 'C', 1) # Quantity data cell
                pdf.cell(col_widths[5], row_height, type_display, 1, 0, 'L', 1)
                pdf.cell(col_widths[6], row_height, cheque_status_display, 1, 0, 'L', 1)
                pdf.cell(col_widths[7], row_height, amount_display, 1, 0, 'R', 1) # Unit Amount
                pdf.cell(col_widths[8], row_height, line_total_display, 1, 1, 'R', 1) # Line Total
        else:
            pdf.set_fill_color(255, 255, 255)
            pdf.cell(sum(col_widths), 20, "No transactions found for the selected criteria.", 1, 1, 'C', 1)

        pdf.ln(10)

        if pdf.get_y() + 30 > pdf.h - 35:
            pdf.add_page()
            pdf.ln(20)

        pdf.set_font("Arial", "B", size=14)
        pdf.set_text_color(0, 123, 255)
        
        # Calculate the X position for the "Total Amount:" label
        # It should start at the left margin, and span up to the start of the Line Total column.
        total_label_span_width = sum(col_widths[:-1]) # Sum of all widths except the last one (Line Total)

        pdf.set_x(pdf.l_margin) # Start from the left margin
        pdf.cell(total_label_span_width, 10, "Total Amount:", 0, 0, 'R') # Right align label within its span

        # Print the total amount value in the last column's space
        pdf.cell(col_widths[8], 10, f"Rs. {total_invoice_amount:,.2f}", 0, 1, 'R') # Right align value in the last column
        pdf.ln(20)

        os.makedirs(INVOICE_DIR, exist_ok=True)
        
        current_datetime_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        person_name_clean = person_name.replace(' ', '_').replace('.', '')

        # Simplified filename based on date range
        start_date_str_file = start_date.strftime('%Y%m%d') if start_date else "All"
        end_date_str_file = end_date.strftime('%Y%m%d') if end_date else "Transactions"
        pdf_filename = f"{person_name_clean}_Invoice_{start_date_str_file}_to_{end_date_str_file}_{current_datetime_str}.pdf"

        pdf_file_path = os.path.join(INVOICE_DIR, pdf_filename)
        pdf.output(pdf_file_path)
        
        st.toast(f"PDF invoice generated at {pdf_file_path}")
        return pdf_file_path
    except Exception as e:
        st.error(f"Error generating PDF invoice: {e}")
        return None

st.set_page_config(layout="wide")
st.title("💰 Payment Tracker")
st.sidebar.markdown(f"[🌐 View Public Summary]({SUMMARY_URL})", unsafe_allow_html=True)

def reset_form_session_state_for_add_transaction():
    st.session_state['selected_transaction_type'] = 'Paid to Me'
    st.session_state['payment_method'] = 'cash'
    st.session_state['selected_person'] = "Select..."
    st.session_state['editing_row_idx'] = None
    st.session_state['add_amount'] = None
    st.session_state['add_date'] = None
    st.session_state['add_reference_number'] = ''
    st.session_state['add_cheque_status'] = 'received/given'
    st.session_state['add_status'] = 'completed'
    st.session_state['add_description'] = ''

def reset_form_session_state_for_add_client_expense():
    st.session_state['selected_client_for_expense'] = "Select..."
    st.session_state['add_client_expense_amount'] = None
    st.session_state['add_client_expense_date'] = None
    st.session_state['add_client_expense_category'] = 'General'
    st.session_state['add_client_expense_description'] = ''
    st.session_state['add_client_expense_quantity'] = 1.0 # Reset quantity

if st.session_state.get('reset_add_form', False):
    reset_form_session_state_for_add_transaction()
    st.session_state['reset_add_form'] = False

if st.session_state.get('reset_client_expense_form', False):
    reset_form_session_state_for_add_client_expense()
    st.session_state['reset_client_expense_form'] = False

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Add Transaction", "View Transactions", "Track Client Expenses", "Manage People", "Generate Invoice"])

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
        filtered_people = people_df[people_df['category'] == category]['name'].astype(str).tolist()
    except Exception as e:
        st.error(f"Error loading people data: {e}")
        filtered_people = []

    person_options = ["Select..."] + sorted(filtered_people)

    if st.session_state['selected_person'] not in person_options:
        st.session_state['selected_person'] = "Select..."

    current_person_index = person_options.index(st.session_state['selected_person'])

    with st.form("transaction_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            amount_value = st.session_state['add_amount']
            amount = st.number_input("Amount (Rs.)", min_value=0.0, format="%.2f", value=float(amount_value) if amount_value is not None else None, key='add_amount')
            
            date_value = st.session_state['add_date']
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
            selected_person_final = st.session_state['selected_person'] if st.session_state['selected_person'] != "Select..." else None

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
            
            normalized_reference_number = str(reference_number).strip()

            if not normalized_reference_number:
                if st.session_state['payment_method'] == "cheque":
                    st.warning(f"🚨 Reference Number is **REQUIRED** for cheque transactions.")
                else:
                    st.warning(f"🚨 Reference Number is required.")
                validation_passed = False
            
            try:
                existing_df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
                existing_df['reference_number'] = existing_df['reference_number'].apply(
                    lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
                )
                if not existing_df.empty and normalized_reference_number in existing_df['reference_number'].values:
                    st.warning(f"🚨 Duplicate Reference Number found: '{normalized_reference_number}'. Please use a unique reference number.")
                    validation_passed = False
            except Exception as e:
                st.error(f"Error checking for duplicate reference numbers: {e}")
                validation_passed = False

            if validation_passed:
                try:
                    new_row = {
                        "date": date.strftime("%Y-%m-%d"),
                        "person": selected_person_final,
                        "amount": amount,
                        "type": 'paid_to_me' if st.session_state['selected_transaction_type'] == "Paid to Me" else 'i_paid',
                        "status": status,
                        "description": description,
                        "payment_method": st.session_state['payment_method'],
                        "reference_number": normalized_reference_number,
                        "cheque_status": cheque_status_val if st.session_state['payment_method'] == "cheque" else None,
                        "transaction_status": status
                    }
                    pd.DataFrame([new_row]).to_csv(CSV_FILE, mode='a', header=False, index=False)
                    
                    updated_df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
                    updated_df['reference_number'] = updated_df['reference_number'].apply(
                        lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
                    )
                    updated_df = clean_payments_data(updated_df)
                    updated_df.to_csv(CSV_FILE, index=False)

                    html_generated = generate_html_summary(updated_df)
                    git_pushed = False
                    if html_generated:
                        git_pushed = git_push()
                    
                    if html_generated and git_pushed:
                        st.success("Transaction added successfully and GitHub updated.")
                    elif html_generated:
                        st.success("Transaction added successfully. HTML summary generated.")
                    else:
                        st.error("Transaction added, but HTML summary or GitHub update failed.")

                    st.session_state['reset_add_form'] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving transaction: {e}")

with tab2:
    st.subheader("Transaction History")

    try:
        df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
        df['reference_number'] = df['reference_number'].apply(
            lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
        )
        df = clean_payments_data(df)

        if df.empty:
            st.info("No transactions recorded yet.")
            
        temp_filtered_df = df.copy()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            view_filter = st.radio("Filter by Type", ["All", "Received", "Paid"], horizontal=True, key='view_filter_radio')
        with col2:
            method_filter = st.selectbox("Payment Method", ["All", "Cash", "Cheque"], key='method_filter_select')
        with col3:
            status_filter = st.selectbox("Status", ["All", "Completed", "Pending", "Received/Given", "Processing", "Bounced", "Processing Done"], key='status_filter_select')
        
        try:
            people_df_view = pd.read_csv(PEOPLE_FILE)
            person_options_view = ["All"] + sorted(people_df_view['name'].astype(str).tolist())
        except Exception as e:
            st.error(f"Error loading people data for view filter: {e}")
            person_options_view = ["All"]

        with col4:
            st.session_state['view_person_filter'] = st.selectbox(
                "Filter by Person",
                person_options_view,
                key='view_person_filter_select'
            )
        
        st.session_state['view_reference_number_search'] = st.text_input(
            "Search by Reference Number",
            value=st.session_state['view_reference_number_search'],
            key='view_reference_number_search_input',
            placeholder="Enter reference number..."
        )

        if view_filter != "All":
            temp_filtered_df = temp_filtered_df[temp_filtered_df['type'].map({'paid_to_me': 'Received', 'i_paid': 'Paid'}) == view_filter]
        if method_filter != "All":
            temp_filtered_df = temp_filtered_df[temp_filtered_df['payment_method'].astype(str).str.lower() == method_filter.lower()]
        if status_filter != "All":
            if status_filter.lower() in valid_transaction_statuses_lower:
                temp_filtered_df = temp_filtered_df[temp_filtered_df['transaction_status'].astype(str).str.lower() == status_filter.lower()]
            elif status_filter.lower() in valid_cheque_statuses_lower:
                temp_filtered_df = temp_filtered_df[temp_filtered_df['cheque_status'].astype(str).str.lower() == status_filter.lower()]
        
        if st.session_state['view_person_filter'] != "All":
            temp_filtered_df = temp_filtered_df[temp_filtered_df['person'] == st.session_state['view_person_filter']]

        if st.session_state['view_reference_number_search']:
            search_term = st.session_state['view_reference_number_search'].lower()
            temp_filtered_df = temp_filtered_df[
                temp_filtered_df['reference_number'].astype(str).str.lower().str.contains(search_term)
            ]

        filtered_df_for_display = prepare_dataframe_for_display(temp_filtered_df)
        if not filtered_df_for_display.empty:
            filtered_df_for_display['original_index'] = temp_filtered_df.index
        else:
            st.info("No transactions match the current filters.")

        display_columns = {
            'original_index': 'ID',
            'formatted_date': 'Date',
            'person': 'Person',
            'amount_display': 'Amount',
            'type_display': 'Type',
            'payment_method': 'Method',
            'cheque_status_display': 'Cheque Status',
            'reference_number_display': 'Reference No.',
            'transaction_status_display': 'Status',
            'description': 'Description'
        }

        if not filtered_df_for_display.empty:
            total_displayed_amount = filtered_df_for_display['amount'].sum()
            st.metric("Total Displayed Amount", f"Rs. {total_displayed_amount:,.2f}")

            st.dataframe(
                filtered_df_for_display[list(display_columns.keys())].rename(columns=display_columns),
                use_container_width=True,
                hide_index=True
            )

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

                if st.session_state['editing_row_idx'] != selected_original_index:
                    st.session_state['editing_row_idx'] = selected_original_index
                    loaded_edit_data = df.loc[st.session_state['editing_row_idx']].to_dict()
                    ref_num_for_widget = loaded_edit_data.get('reference_number', '')
                    if pd.isna(ref_num_for_widget) or str(ref_num_for_widget).strip().lower() == 'nan' or str(ref_num_for_widget).strip().lower() == 'none':
                        loaded_edit_data['reference_number'] = ''
                    else:
                        loaded_edit_data['reference_number'] = str(ref_num_for_widget).strip()

                    st.session_state['temp_edit_data'] = loaded_edit_data
                    st.rerun()

        if st.session_state['editing_row_idx'] is not None and st.session_state.get('temp_edit_data'):
            st.markdown("---")
            st.subheader(f"Editing Transaction ID: {st.session_state['editing_row_idx']}")
            edit_data = st.session_state['temp_edit_data']

            with st.form("edit_transaction_form"):
                col1_edit, col2_edit = st.columns(2)
                with col1_edit:
                    edited_amount = st.number_input("Amount (Rs.)", value=float(edit_data.get('amount', 0.0)), format="%.2f", key='edit_amount')

                    default_date_value = edit_data.get('date')
                    if pd.isna(default_date_value):
                        default_date_value = None
                    elif isinstance(default_date_value, pd.Timestamp):
                        default_date_value = default_date_value.date()
                    elif isinstance(default_date_value, str):
                        try:
                            default_date_value = datetime.strptime(default_date_value, "%Y-%m-%d").date()
                        except ValueError:
                            default_date_value = None
                    
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
                            cheque_status_val = 'processing'
                        edited_cheque_status = st.selectbox(
                            "Cheque Status",
                            valid_cheque_statuses_lower,
                            index=valid_cheque_statuses_lower.index(cheque_status_val),
                            key='edit_cheque_status'
                        )
                    else:
                        edited_cheque_status = None

                    edited_reference_number = st.text_input(
                        "Reference Number",
                        value=str(edit_data.get('reference_number', '')),
                        key='edit_reference_number'
                    )

                with col2_edit:
                    try:
                        people_df = pd.read_csv(PEOPLE_FILE)
                        people_list = people_df['name'].dropna().astype(str).tolist()
                        current_person = str(edit_data.get('person', ''))

                        if current_person not in people_list and current_person != '':
                            people_list = [current_person] + people_list
                            default_index = 0
                        elif current_person == '':
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
                        edited_person = str(edit_data.get('person', ''))

                    transaction_status_val = str(edit_data.get('transaction_status', 'completed')).lower()
                    if transaction_status_val not in valid_transaction_statuses_lower:
                        transaction_status_val = 'completed'
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
                    
                    normalized_edited_reference_number = str(edited_reference_number).strip()

                    if not normalized_edited_reference_number:
                        if edited_payment_method == "cheque":
                            st.warning(f"🚨 Reference Number is **REQUIRED** for cheque transactions.")
                        else:
                            st.warning(f"🚨 Reference Number is required.")
                        validation_passed = False
                    
                    try:
                        existing_df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
                        existing_df['reference_number'] = existing_df['reference_number'].apply(
                            lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
                        )
                        other_transactions = existing_df.drop(st.session_state['editing_row_idx'], errors='ignore')
                        
                        if not other_transactions.empty and normalized_edited_reference_number in other_transactions['reference_number'].values:
                            st.warning(f"🚨 Duplicate Reference Number found: '{normalized_edited_reference_number}'. Please use a unique reference number.")
                            validation_passed = False
                    except Exception as e:
                        st.error(f"Error checking for duplicate reference numbers during edit: {e}")
                        validation_passed = False

                    if validation_passed:
                        try:
                            df.loc[st.session_state['editing_row_idx']] = {
                                "date": edited_date.strftime("%Y-%m-%d"),
                                "person": edited_person,
                                "amount": edited_amount,
                                "type": edit_data['type'],
                                "status": edited_transaction_status,
                                "description": edited_description,
                                "payment_method": edited_payment_method,
                                "reference_number": normalized_edited_reference_number,
                                "cheque_status": edited_cheque_status,
                                "transaction_status": edited_transaction_status
                            }
                            df.to_csv(CSV_FILE, index=False)

                            updated_df_after_edit = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
                            updated_df_after_edit['reference_number'] = updated_df_after_edit['reference_number'].apply(
                                lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
                            )
                            updated_df_after_edit = clean_payments_data(updated_df_after_edit)
                            updated_df_after_edit.to_csv(CSV_FILE, index=False)
                            
                            generate_html_summary(updated_df_after_edit)
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
            
with tab3:
    st.subheader("Track Client Expenses")

    try:
        people_df_for_expenses = pd.read_csv(PEOPLE_FILE)
        client_people = people_df_for_expenses[people_df_for_expenses['category'] == 'client']['name'].astype(str).tolist()
        client_options = ["Select..."] + sorted(client_people)
        
        current_client_index = 0
        if st.session_state['selected_client_for_expense'] in client_options:
            current_client_index = client_options.index(st.session_state['selected_client_for_expense'])

    except Exception as e:
        st.error(f"Error loading client data for expenses: {e}")
        client_options = ["Select..."]
        current_client_index = 0
        client_people = []

    with st.form("client_expense_form", clear_on_submit=False):
        st.session_state['selected_client_for_expense'] = st.selectbox(
            "Select Client",
            client_options,
            index=current_client_index,
            key='selected_client_for_expense_select'
        )

        col1_exp, col2_exp = st.columns(2)
        with col1_exp:
            expense_amount_value = st.session_state['add_client_expense_amount']
            expense_amount = st.number_input("Expense Amount (Unit Price Rs.)", min_value=0.0, format="%.2f", value=float(expense_amount_value) if expense_amount_value is not None else None, key='add_client_expense_amount')

            expense_date_value = st.session_state['add_client_expense_date']
            expense_date = st.date_input("Expense Date", value=expense_date_value, key='add_client_expense_date')
            
            expense_quantity_value = st.session_state['add_client_expense_quantity']
            expense_quantity = st.number_input("Quantity", min_value=0.0, format="%.2f", value=float(expense_quantity_value) if expense_quantity_value is not None else 1.0, key='add_client_expense_quantity')


        with col2_exp:
            expense_category = st.selectbox(
                "Expense Category",
                valid_expense_categories,
                index=valid_expense_categories.index(st.session_state['add_client_expense_category']),
                key='add_client_expense_category'
            )
            expense_description = st.text_input(
                "Expense Description",
                value=st.session_state['add_client_expense_description'],
                key='add_client_expense_description'
            )
        
        submitted_expense = st.form_submit_button("Add Client Expense")

        if submitted_expense:
            expense_validation_passed = True
            selected_client_final_for_expense = None

            if st.session_state['selected_client_for_expense'] == "Select...":
                st.warning("Please select a client.")
                expense_validation_passed = False
            else:
                selected_client_final_for_expense = st.session_state['selected_client_for_expense']

            if expense_amount <= 0:
                st.warning("Expense amount (unit price) must be greater than 0.")
                expense_validation_passed = False
            if expense_quantity <= 0:
                st.warning("Quantity must be greater than 0.")
                expense_validation_passed = False
            
            # Removed client expense validation:
            # if (spent_by_this_client + current_transaction_total) > total_paid_to_this_client:
            #     st.warning(f"🚨 Total reported expenses (Rs. {spent_by_this_client + current_transaction_total:,.2f}) for {selected_client_final_for_expense} exceed the total amount paid to them (Rs. {total_paid_to_this_client:,.2f}). Remaining to be accounted for: Rs. {total_paid_to_this_client - spent_by_this_client:,.2f}")
            #     expense_validation_passed = False
            
            # if total_paid_to_this_client == 0:
            #     st.warning(f"No money has been recorded as 'Paid to' {selected_client_final_for_expense} yet. Please add a corresponding 'I Paid' transaction first.")
            #     expense_validation_passed = False

            if expense_validation_passed:
                try:
                    new_expense_row = {
                        "original_transaction_ref_num": "",
                        "expense_date": expense_date.strftime("%Y-%m-%d"),
                        "expense_person": selected_client_final_for_expense,
                        "expense_category": expense_category,
                        "expense_amount": expense_amount,
                        "expense_quantity": expense_quantity, # Added quantity here
                        "expense_description": expense_description
                    }
                    pd.DataFrame([new_expense_row]).to_csv(CLIENT_EXPENSES_FILE, mode='a', header=False, index=False)
                    st.success("Client expense added successfully!")
                    
                    updated_payments_df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
                    updated_payments_df['reference_number'] = updated_payments_df['reference_number'].apply(
                        lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
                    )
                    updated_payments_df = clean_payments_data(updated_payments_df)
                    updated_payments_df.to_csv(CSV_FILE, index=False)

                    generate_html_summary(updated_payments_df)
                    git_push()

                    st.session_state['reset_client_expense_form'] = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving client expense: {e}")

    st.markdown("---")
    st.subheader("Client Expense Summary")

    try:
        payments_df_all = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
        payments_df_all['amount'] = pd.to_numeric(payments_df_all['amount'], errors='coerce').fillna(0.0)
        payments_df_all['person'] = payments_df_all['person'].astype(str)
        payments_df_all['type'] = payments_df_all['type'].astype(str).str.lower()

        client_expenses_df_all = pd.DataFrame()
        if os.path.exists(CLIENT_EXPENSES_FILE) and os.path.getsize(CLIENT_EXPENSES_FILE) > 0:
            client_expenses_df_all = pd.read_csv(CLIENT_EXPENSES_FILE, dtype={'original_transaction_ref_num': str, 'expense_person': str}, keep_default_na=False)
            client_expenses_df_all['expense_amount'] = pd.to_numeric(client_expenses_df_all['expense_amount'], errors='coerce').fillna(0.0)
            client_expenses_df_all['expense_person'] = client_expenses_df_all['expense_person'].astype(str)
            client_expenses_df_all['expense_date'] = pd.to_datetime(client_expenses_df_all['expense_date'], errors='coerce').dt.strftime('%Y-%m-%d').fillna('')
            # Ensure expense_quantity is loaded and cleaned
            if 'expense_quantity' not in client_expenses_df_all.columns:
                client_expenses_df_all['expense_quantity'] = 1.0
            client_expenses_df_all['expense_quantity'] = pd.to_numeric(client_expenses_df_all['expense_quantity'], errors='coerce').fillna(1.0)
            client_expenses_df_all['total_line_amount'] = client_expenses_df_all['expense_amount'] * client_expenses_df_all['expense_quantity'] # Calculate total line amount
        
        # Initialize with expected columns to prevent KeyError if empty
        total_paid_to_clients = pd.DataFrame(columns=['client_name', 'total_paid_to_client'])
        if not payments_df_all[payments_df_all['type'] == 'i_paid'].empty:
            total_paid_to_clients = payments_df_all[payments_df_all['type'] == 'i_paid'].groupby('person')['amount'].sum().reset_index()
            total_paid_to_clients.rename(columns={'person': 'client_name', 'amount': 'total_paid_to_client'}, inplace=True)

        # Initialize with expected columns to prevent KeyError if empty
        total_spent_by_clients = pd.DataFrame(columns=['client_name', 'total_spent_by_client'])
        if not client_expenses_df_all.empty:
            total_spent_by_clients = client_expenses_df_all.groupby('expense_person')['total_line_amount'].sum().reset_index() # Sum of total_line_amount
            total_spent_by_clients.rename(columns={'expense_person': 'client_name', 'total_line_amount': 'total_spent_by_client'}, inplace=True)

        expected_client_summary_cols = ['client_name', 'total_paid_to_client', 'total_spent_by_client']
        summary_by_client_df = pd.merge(
            total_paid_to_clients,
            total_spent_by_clients,
            on='client_name',
            how='outer'
        )
        # Ensure all expected columns are present after merge and fill NaNs
        for col in expected_client_summary_cols:
            if col not in summary_by_client_df.columns:
                summary_by_client_df[col] = 0
        summary_by_client_df.fillna(0, inplace=True) # Fill NaNs that might result from outer merge
        summary_by_client_df['client_name'] = summary_by_client_df['client_name'].astype(str).fillna('')
        summary_by_client_df['total_paid_to_client'] = pd.to_numeric(summary_by_client_df['total_paid_to_client'], errors='coerce').fillna(0)
        summary_by_client_df['total_spent_by_client'] = pd.to_numeric(summary_by_client_df['total_spent_by_client'], errors='coerce').fillna(0)
        summary_by_client_df['remaining_balance'] = summary_by_client_df['total_paid_to_client'] - summary_by_client_df['total_spent_by_client']


        if not summary_by_client_df.empty:
            st.write("#### Spending Overview by Client")
            st.dataframe(
                summary_by_client_df[[
                    'client_name', 'total_paid_to_client', 'total_spent_by_client', 'remaining_balance'
                ]].style.format({
                    'total_paid_to_client': "Rs. {:,.2f}",
                    'total_spent_by_client': "Rs. {:,.2f}",
                    'remaining_balance': "Rs. {:,.2f}"
                }),
                use_container_width=True,
                hide_index=True
            )

            st.write("#### Detailed Client Expenses")
            if not client_expenses_df_all.empty:
                st.dataframe(
                    client_expenses_df_all[[
                        'expense_date', 'expense_person', 'expense_category', 'expense_amount', 'expense_quantity', 'total_line_amount', 'expense_description'
                    ]].style.format({
                        'expense_amount': "Rs. {:,.2f}",
                        'expense_quantity': "{:,.0f}", # Format quantity
                        'total_line_amount': "Rs. {:,.2f}" # Format total line amount
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No detailed client expenses to display.")
        else:
            st.info("No client expenses or 'I Paid' transactions recorded yet.")
    except Exception as e:
        st.error(f"Error loading client expenses summary: {e}")

with tab4:
    st.subheader("Manage People")
    with st.expander("Add New Person"):
        with st.form("person_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name").strip()
            category = c2.selectbox("Category", ["investor", "client"])
            if st.form_submit_button("Add Person"):
                if not name:
                    st.warning("Name is required.")
                else:
                    try:
                        if not os.path.exists(PEOPLE_FILE):
                            pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)

                        df = pd.read_csv(PEOPLE_FILE)
                        df['name'] = df['name'].astype(str)
                        if name.lower() in df['name'].str.lower().values:
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
                
                if not ppl['name'].empty:
                    to_del = st.selectbox("Delete Person", ppl['name'].astype(str).tolist(), key='delete_person_select')
                    if st.button("Delete", key='delete_person_button'):
                        try:
                            tx = pd.read_csv(CSV_FILE)
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

with tab5:
    st.subheader("Generate Invoice")

    try:
        people_df_invoice = pd.read_csv(PEOPLE_FILE)
        invoice_person_options = ["Select..."] + sorted(people_df_invoice['name'].astype(str).tolist())
    except Exception as e:
        st.error(f"Error loading people data for invoice: {e}")
        invoice_person_options = ["Select..."]

    st.session_state['invoice_person_name'] = st.selectbox(
        "Select Person for Invoice",
        invoice_person_options,
        index=invoice_person_options.index(st.session_state['invoice_person_name']) if st.session_state['invoice_person_name'] in invoice_person_options else 0,
        key='invoice_person_name_select'
    )

    st.session_state['invoice_type'] = st.radio(
        "Invoice Type",
        ["Invoice for Person (All Transactions)", "Invoice for Date Range"],
        key='invoice_type_radio'
    )

    filtered_invoice_df = pd.DataFrame()
    if st.session_state['invoice_person_name'] != "Select...":
        try:
            all_transactions_df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
            all_transactions_df['reference_number'] = all_transactions_df['reference_number'].apply(
                lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
            )
            all_transactions_df = clean_payments_data(all_transactions_df)
            
            client_expenses_for_invoice = pd.DataFrame()
            if os.path.exists(CLIENT_EXPENSES_FILE) and os.path.getsize(CLIENT_EXPENSES_FILE) > 0:
                client_expenses_for_invoice = pd.read_csv(CLIENT_EXPENSES_FILE, dtype={'original_transaction_ref_num': str, 'expense_person': str}, keep_default_na=False)
                client_expenses_for_invoice['expense_amount'] = pd.to_numeric(client_expenses_for_invoice['expense_amount'], errors='coerce').fillna(0.0)
                client_expenses_for_invoice['expense_quantity'] = pd.to_numeric(client_expenses_for_invoice['expense_quantity'], errors='coerce').fillna(1.0)
                client_expenses_for_invoice['expense_person'] = client_expenses_for_invoice['expense_person'].astype(str)
            
            filtered_invoice_df = all_transactions_df[
                (all_transactions_df['person'] == st.session_state['invoice_person_name']) &
                (all_transactions_df['type'] == 'i_paid')
            ].copy()

            if 'expense_quantity' not in filtered_invoice_df.columns:
                filtered_invoice_df['expense_quantity'] = 1.0 # Default to 1 for payments in invoice
            
            # Conditionally display date inputs and filter based on invoice type
            if st.session_state['invoice_type'] == "Invoice for Date Range":
                col_start_date, col_end_date = st.columns(2)
                with col_start_date:
                    st.session_state['invoice_start_date'] = st.date_input(
                        "Start Date",
                        value=st.session_state['invoice_start_date'] if st.session_state['invoice_start_date'] else datetime.now().date().replace(day=1),
                        key='invoice_start_date_select'
                    )
                with col_end_date:
                    st.session_state['invoice_end_date'] = st.date_input(
                        "End Date",
                        value=st.session_state['invoice_end_date'] if st.session_state['invoice_end_date'] else datetime.now().date(),
                        key='invoice_end_date_select'
                    )
                
                if st.session_state['invoice_start_date'] and st.session_state['invoice_end_date']:
                    filtered_invoice_df = filtered_invoice_df[
                        (filtered_invoice_df['date'] >= pd.to_datetime(st.session_state['invoice_start_date'])) &
                        (filtered_invoice_df['date'] <= pd.to_datetime(st.session_state['invoice_end_date']))
                    ]
            
            # This block should be outside the date range IF, but inside the main person IF
            if not filtered_invoice_df.empty:
                filtered_invoice_df_display = prepare_dataframe_for_display(filtered_invoice_df)
                filtered_invoice_df_display['original_index'] = filtered_invoice_df.index
                
                if 'expense_quantity' not in filtered_invoice_df_display.columns:
                    filtered_invoice_df_display['expense_quantity'] = 1.0 

                filtered_invoice_df_display['line_total_display'] = (
                    filtered_invoice_df_display['amount'] * filtered_invoice_df_display['expense_quantity']
                ).apply(lambda x: f"Rs. {x:,.2f}")

                st.write("#### Transactions for Invoice")
                st.dataframe(
                    filtered_invoice_df_display[[
                        'original_index', 'formatted_date', 'amount_display', 'expense_quantity', 'line_total_display', 'type_display', 
                        'payment_method_display', 'cheque_status_display', 'reference_number_display', 
                        'transaction_status_display', 'description'
                    ]].rename(columns={
                        'original_index': 'ID',
                        'formatted_date': 'Date',
                        'amount_display': 'Amount (Unit)', # Renamed for clarity
                        'expense_quantity': 'Quantity', # Display Quantity
                        'line_total_display': 'Line Total', # Display Line Total
                        'type_display': 'Type',
                        'payment_method_display': 'Method',
                        'cheque_status_display': 'Cheque Status',
                        'reference_number_display': 'Reference No.',
                        'transaction_status_display': 'Status',
                        'description': 'Description'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            else: # This is the correct else for 'if not filtered_invoice_df.empty:'
                st.info("No 'I Paid' transactions found for the selected person and criteria.")

        except Exception as e:
            st.error(f"Error loading transactions for invoice: {e}")
    else: # This is the correct else for 'if st.session_state['invoice_person_name'] != "Select...":'
        st.info("Please select a person to view transactions for invoice.")

    if st.button("Generate PDF Invoice"):
        if st.session_state['invoice_person_name'] == "Select...":
            st.warning("Please select a person to generate an invoice.")
        elif not filtered_invoice_df.empty:
            # Pass the filtered_invoice_df directly
            pdf_path = generate_invoice_pdf(
                st.session_state['invoice_person_name'],
                prepare_dataframe_for_display(filtered_invoice_df), # Pass the prepared df for PDF generation
                st.session_state['invoice_start_date'] if st.session_state['invoice_type'] == "Invoice for Date Range" else None,
                st.session_state['invoice_end_date'] if st.session_state['invoice_type'] == "Invoice for Date Range" else None
            )
            if pdf_path:
                st.session_state['generated_invoice_pdf_path'] = pdf_path
                st.session_state['show_download_button'] = True
                st.success("Invoice generated successfully!")
            else:
                st.error("Failed to generate invoice.")
        else:
            st.warning("No transactions to include in the invoice based on your selection and date range.")

    if st.session_state['show_download_button'] and st.session_state['generated_invoice_pdf_path']:
        with open(st.session_state['generated_invoice_pdf_path'], "rb") as pdf_file:
            PDFbyte = pdf_file.read()
            st.download_button(
                label="Download Invoice PDF",
                data=PDFbyte,
                file_name=os.path.basename(st.session_state['generated_invoice_pdf_path']),
                mime="application/pdf"
            )

st.sidebar.header("Current Balances")
try:
    if os.path.exists(CSV_FILE):
        df_bal = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
        df_bal['reference_number'] = df_bal['reference_number'].apply(
            lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
        )
        df_bal = clean_payments_data(df_bal)

        # Calculate total client expenses for the sidebar
        total_client_expenses_for_sidebar = 0.0
        if os.path.exists(CLIENT_EXPENSES_FILE) and os.path.getsize(CLIENT_EXPENSES_FILE) > 0:
            df_exp_sidebar = pd.read_csv(CLIENT_EXPENSES_FILE, dtype={'expense_amount': float, 'expense_quantity': float}, keep_default_na=False)
            df_exp_sidebar['expense_amount'] = pd.to_numeric(df_exp_sidebar['expense_amount'], errors='coerce').fillna(0.0)
            if 'expense_quantity' not in df_exp_sidebar.columns:
                df_exp_sidebar['expense_quantity'] = 1.0
            df_exp_sidebar['expense_quantity'] = pd.to_numeric(df_exp_sidebar['expense_quantity'], errors='coerce').fillna(1.0)
            df_exp_sidebar['total_line_amount'] = df_exp_sidebar['expense_amount'] * df_exp_sidebar['expense_quantity']
            total_client_expenses_for_sidebar = df_exp_sidebar['total_line_amount'].sum()


        if not df_bal.empty:
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
            st.sidebar.metric("Total Paid (by me)", f"Rs. {paid:,.2f}")
            st.sidebar.metric("Total Client Expenses", f"Rs. {total_client_expenses_for_sidebar:,.2f}")
            st.sidebar.metric("Net Balance (Paid - Spent)", f"Rs. {paid - total_client_expenses_for_sidebar:,.2f}", delta_color="inverse")

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

# Ensure HTML summary is generated on every run
try:
    current_payments_df = pd.read_csv(CSV_FILE, dtype={'reference_number': str}, keep_default_na=False)
    current_payments_df['reference_number'] = current_payments_df['reference_number'].apply(
        lambda x: '' if pd.isna(x) or str(x).strip().lower() == 'nan' or str(x).strip().lower() == 'none' else str(x).strip()
    )
    current_payments_df = clean_payments_data(current_payments_df)
    generate_html_summary(current_payments_df)
except Exception as e:
    st.error(f"Failed to generate HTML summary on app load: {e}")

