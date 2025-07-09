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
        if not os.path.exists(CSV_FILE):
            pd.DataFrame(columns=[
                "date", "person", "amount", "type", "status",
                "description", "payment_method", "cheque_number",
                "cheque_status", "transaction_status", "receipt_number"
            ]).to_csv(CSV_FILE, index=False)
            st.toast(f"Created new {CSV_FILE}")
        else:
            df = pd.read_csv(CSV_FILE)
            if 'receipt_number' not in df.columns:
                df['receipt_number'] = ''
                df.to_csv(CSV_FILE, index=False)

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
    # Create a copy and ensure proper data types
    df = df.copy()
    
    # Convert amounts to float and handle missing values
    df['amount'] = pd.to_numeric(df['amount'], errors='coerce').fillna(0.0)
    
    # Force string type for cheque and receipt numbers
    df['cheque_number'] = df['cheque_number'].astype(str)
    df['receipt_number'] = df['receipt_number'].astype(str)
    
    # Clean up 'nan' strings and empty values
    df['cheque_number'] = df['cheque_number'].replace('nan', '').replace('None', '')
    df['receipt_number'] = df['receipt_number'].replace('nan', '').replace('None', '')
    
    # Format cheque numbers to avoid scientific notation
    def format_cheque_number(num):
        if num.replace('.', '').isdigit():
            try:
                # Remove any existing formatting
                clean_num = num.replace(',', '').replace('.', '')
                # Format with commas as thousand separators
                return "{:,}".format(int(clean_num))
            except:
                return num
        return num
    
    df['cheque_number'] = df['cheque_number'].apply(format_cheque_number)
    
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
        'cheque_number': 'Cheque No.',
        'cheque_status': 'Cheque Status', 
        'receipt_number': 'Receipt No.'
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
            font-size: 18px;
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
        
        .card-details div {{
            margin-bottom: 5px;
            display: flex;
            align-items: center;
        }}
        
        .card-details i {{
            margin-right: 8px;
            width: 18px;
            text-align: center;
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
        
        .filters {{
            background: var(--white);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        }}
        
        .filter-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 15px;
        }}
        
        .filter-group {{
            margin-bottom: 10px;
        }}
        
        .filter-group label {{
            display: block;
            margin-bottom: 5px;
            font-weight: 500;
            font-size: 14px;
            color: var(--dark);
        }}
        
        .filter-group select, 
        .filter-group input {{
            width: 100%;
            padding: 8px 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-family: 'Poppins', sans-serif;
        }}
        
        .filter-actions {{
            display: flex;
            justify-content: space-between;
            margin-top: 10px;
        }}
        
        .filter-btn {{
            background-color: var(--primary);
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            cursor: pointer;
            font-family: 'Poppins', sans-serif;
            transition: background-color 0.3s;
        }}
        
        .filter-btn:hover {{
            background-color: var(--secondary);
        }}
        
        .reset-btn {{
            background-color: #f0f0f0;
            color: #333;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--white);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
            margin-bottom: 30px;
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
            white-space: nowrap;
        }}
        
        .completed {{ background-color: rgba(40, 167, 69, 0.1); color: #28a745; }}
        .pending {{ background-color: rgba(255, 193, 7, 0.1); color: #ffc107; }}
        .processing {{ background-color: rgba(13, 110, 253, 0.1); color: #0d6efd; }}
        .bounced {{ background-color: rgba(220, 53, 69, 0.1); color: #dc3545; }}
        .received-given {{ background-color: rgba(108, 117, 125, 0.1); color: #6c757d; }}
        .processing-done {{ background-color: rgba(25, 135, 84, 0.1); color: #198754; }}
        
        .no-results {{
            text-align: center;
            padding: 30px;
            color: #666;
            display: none;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            color: #666;
            font-size: 14px;
        }}
        
        .footer i {{
            margin: 0 5px;
        }}
        
        @media (max-width: 768px) {{
            .summary-cards {{
                grid-template-columns: 1fr;
            }}
            
            .filter-grid {{
                grid-template-columns: 1fr;
            }}
            
            th, td {{
                padding: 12px 8px;
                font-size: 14px;
            }}
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
                        {''.join(f'<option value="{name}">{name}</option>' for name in sorted(df['person'].unique()))}
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
                    <th>Cheque No.</th>
                    <th>Receipt No.</th>
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
                    <td>{row['Date']}</td>
                    <td>{row['Person']}</td>
                    <td>{row['Amount']}</td>
                    <td>{row['Type']}</td>
                    <td>{row['Method'].capitalize()}</td>
                    <td>{row['Cheque No.'] if row['Cheque No.'] else '-'}</td>
                    <td>{row['Receipt No.'] if row['Receipt No.'] else '-'}</td>
                    <td><span class="status {status_class}">{row['Status'].capitalize()}</span></td>
                    <td><span class="status {cheque_status_class}">{row['Cheque Status'] if pd.notna(row['Cheque Status']) else '-'}</span></td>
                    <td>{row['Description'] if pd.notna(row['Description']) else '-'}</td>
                </tr>"""

    html += """
            </tbody>
        </table>
        
        <div class="footer">
            <p><i class="fas fa-file-alt"></i> This report was automatically generated by Payment Tracker System</p>
            <p><i class="far fa-copyright"></i> {datetime.now().year} All Rights Reserved</p>
        </div>
        
        <script>
            function applyFilters() {
                const startDate = $('#start-date').val();
                const endDate = $('#end-date').val();
                const person = $('#name-filter').val().toLowerCase();
                const type = $('#type-filter').val();
                const method = $('#method-filter').val();
                const chequeStatus = $('#status-filter').val().toLowerCase();
                
                let visibleRows = 0;
                
                $('#transactions-table tbody tr').each(function() {
                    const rowDate = $(this).data('date');
                    const rowPerson = $(this).data('person').toLowerCase();
                    const rowType = $(this).data('type');
                    const rowMethod = $(this).data('method');
                    const rowChequeStatus = $(this).data('cheque-status');
                    
                    // Date filter
                    const datePass = !startDate || !endDate || 
                                   (rowDate >= startDate && rowDate <= endDate);
                    
                    // Person filter
                    const personPass = !person || rowPerson.includes(person);
                    
                    // Type filter
                    const typePass = !type || rowType === type;
                    
                    // Method filter
                    const methodPass = !method || rowMethod === method;
                    
                    // Cheque status filter
                    const chequeStatusPass = !chequeStatus || 
                                          (rowChequeStatus && rowChequeStatus.includes(chequeStatus));
                    
                    if (datePass && personPass && typePass && methodPass && chequeStatusPass) {
                        $(this).show();
                        visibleRows++;
                    } else {
                        $(this).hide();
                    }
                });
                
                // Show/hide no results message
                if (visibleRows === 0) {
                    $('#no-results').show();
                    $('#transactions-table').hide();
                } else {
                    $('#no-results').hide();
                    $('#transactions-table').show();
                }
            }
            
            function resetFilters() {
                $('.filter-group select').val('');
                $('.date-filter').val('');
                $('#transactions-table tbody tr').show();
                $('#no-results').hide();
                $('#transactions-table').show();
                // Reset to default date range
                const today = new Date();
                const oneMonthAgo = new Date();
                oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
                $('#start-date').val(oneMonthAgo.toISOString().split('T')[0]);
                $('#end-date').val(today.toISOString().split('T')[0]);
            }
            
            // Initialize date pickers with reasonable defaults
            $(document).ready(function() {
                const today = new Date();
                const oneMonthAgo = new Date();
                oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
                
                $('#start-date').val(oneMonthAgo.toISOString().split('T')[0]);
                $('#end-date').val(today.toISOString().split('T')[0]);
                
                // Apply filters when dropdowns change
                $('.filter-group select').change(function() {
                    applyFilters();
                });
            });
        </script>
    </div>
</body>
</html>"""

    # Save the HTML file
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
