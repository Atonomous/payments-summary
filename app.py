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

# Initialize data files
def init_files():
    """Initializes CSV files for payments and people if they don't exist."""
    if not os.path.exists(CSV_FILE):
        pd.DataFrame(columns=["date", "person", "amount", "type", "status", "description"]).to_csv(CSV_FILE, index=False)
    
    if not os.path.exists(PEOPLE_FILE):
        pd.DataFrame(columns=["name", "category"]).to_csv(PEOPLE_FILE, index=False)
    else:
        # Ensure people.csv has correct format, add 'category' if missing
        df = pd.read_csv(PEOPLE_FILE)
        if 'category' not in df.columns:
            df['category'] = 'client'  # Default category
            df.to_csv(PEOPLE_FILE, index=False)

init_files()

def git_push():
    """Pushes changes to the git repository."""
    try:
        repo = Repo(REPO_PATH)
        repo.git.add(update=True)
        repo.index.commit("Automated update: payment records")
        origin = repo.remote(name='origin')
        origin.push()
    except Exception as e:
        st.error(f"Error updating GitHub: {str(e)}")

def generate_summary():
    """Generates an HTML summary of payments and pushes it to git."""
    try:
        df = pd.read_csv(CSV_FILE)
        people_df = pd.read_csv(PEOPLE_FILE)
        
        # Ensure 'description' column exists to prevent KeyError
        for col in ["description"]:
            if col not in df.columns:
                df[col] = ''
        
        # Merge with people_df to potentially use category information
        df = pd.merge(df, people_df, left_on='person', right_on='name', how='left')
        
        summary = {
            "received": df[df['type'] == 'paid_to_me']['amount'].sum(),
            "paid": df[df['type'] == 'i_paid']['amount'].sum(),
            "pending_received": df[(df['type'] == 'paid_to_me') & (df['status'] == 'pending')]['amount'].sum(),
            "pending_paid": df[(df['type'] == 'i_paid') & (df['status'] == 'pending')]['amount'].sum(),
            "transactions": df.to_dict('records')
        }
        
        # HTML content for the summary page
        html = f"""
        <html>
        <head>
            <title>Payment Summary</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1 {{ color: #333; }}
                .summary-box {{ 
                    background: #f5f5f5; 
                    padding: 15px; 
                    border-radius: 5px; 
                    margin-bottom: 20px;
                    display: flex;
                    justify-content: space-between;
                }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                tr:hover {{ background-color: #f5f5f5; }}
            </style>
        </head>
        <body>
            <h1>Payment Summary</h1>
            
            <div class="summary-box">
                <div>
                    <h3>Received from others: Rs.{summary['received']:,.2f}</h3>
                    <p>Pending: Rs.{summary['pending_received']:,.2f}</p>
                </div>
                <div>
                    <h3>Paid to others: Rs.{summary['paid']:,.2f}</h3>
                    <p>Pending: Rs.{summary['pending_paid']:,.2f}</p>
                </div>
            </div>
            
            <h2>All Transactions</h2>
            <table>
                <tr>
                    <th>Date</th>
                    <th>Person</th>
                    <th>Amount</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Description</th>
                </tr>
                {"".join(
                    f"<tr><td>{t['date']}</td><td>{t['person']}</td><td>Rs.{float(t['amount']):,.2f}</td>"
                    f"<td>{'Received from' if t['type'] == 'paid_to_me' else 'Paid to'}</td>"
                    f"<td>{t['status'].capitalize()}</td><td>{t.get('description', '')}</td></tr>" 
                    for t in summary['transactions']
                )}
            </table>
        </body>
        </html>
        """
        
        os.makedirs(os.path.dirname(SUMMARY_FILE), exist_ok=True)
        with open(SUMMARY_FILE, 'w') as f:
            f.write(html)
        git_push()
    except Exception as e:
        st.error(f"Error generating summary: {str(e)}")

# Streamlit UI configuration
st.set_page_config(layout="wide")
st.title("💰 Payment Tracker")

# Initialize session state variables for consistent form behavior
if 'selected_transaction_type' not in st.session_state:
    st.session_state['selected_transaction_type'] = "Paid to Me"
if 'selected_person' not in st.session_state:
    st.session_state['selected_person'] = None # No person selected by default
if 'amount_input' not in st.session_state:
    st.session_state['amount_input'] = 0.0
if 'date_input' not in st.session_state:
    st.session_state['date_input'] = datetime.now().date() # Use .date() for st.date_input
if 'status_input' not in st.session_state:
    st.session_state['status_input'] = "completed"
if 'description_input' not in st.session_state:
    st.session_state['description_input'] = ""

# Function to reset transaction form fields in session state
def reset_transaction_form():
    """Resets all input fields in the 'Add Transaction' form."""
    st.session_state['amount_input'] = 0.0
    st.session_state['date_input'] = datetime.now().date()
    st.session_state['status_input'] = "completed"
    st.session_state['description_input'] = ""
    st.session_state['selected_person'] = None # Explicitly clear the person selectbox

# Tab layout for the application
tab1, tab2, tab3 = st.tabs(["Add Transaction", "View Transactions", "Manage People"])

with tab1:
    st.subheader("Add New Transaction")
    # Removed clear_on_submit=True to manually control form clearing
    with st.form("payment_form"): 
        col1, col2 = st.columns(2)
        
        with col1:
            # Store the current transaction type from session state before rendering the radio
            current_transaction_type_from_radio = st.session_state['selected_transaction_type']

            # Radio button for transaction type, linked to session state
            transaction_type = st.radio(
                "Transaction Type", 
                ["Paid to Me", "I Paid"], 
                horizontal=True, 
                key='transaction_type_radio' # Linked to session state
                # Removed on_change callback here to avoid StreamlitInvalidFormCallbackError
            )
            # Update session state with the current radio selection
            st.session_state['selected_transaction_type'] = transaction_type

            # Check if the transaction type has changed since the last run
            # If it has, reset the selected person to avoid incorrect pre-selection
            if transaction_type != current_transaction_type_from_radio:
                st.session_state['selected_person'] = None

            # Number input for amount, linked to session state
            amount = st.number_input(
                "Amount (Rs.)", 
                min_value=0.0, 
                step=0.01, 
                format="%.2f", 
                key='amount_input' # Linked to session state
            )
            
            # Date input, linked to session state
            date = st.date_input(
                "Date", 
                value=st.session_state['date_input'], # Use value from session state
                key='date_input' # Linked to session state
            )
            
        with col2:
            people_df = pd.DataFrame(columns=["name", "category"]) # Default empty DataFrame for safety
            try:
                people_df = pd.read_csv(PEOPLE_FILE)
                # Ensure category column is treated as string and cleaned
                people_df['category'] = people_df['category'].astype(str).str.strip().str.lower()
            except Exception as e:
                st.error(f"Error loading people data: {str(e)}")

            filtered_people = []
            if not people_df.empty:
                if st.session_state['selected_transaction_type'] == "Paid to Me":
                    filtered_people = people_df[people_df['category'] == 'investor']['name'].tolist()
                else:
                    filtered_people = people_df[people_df['category'] == 'client']['name'].tolist()
            
            # Add a "Select a person" placeholder option
            display_options = ["Select a person..."] + filtered_people
            
            # Determine the initial index for the selectbox based on session state
            initial_person_index = 0 # Default to "Select a person..."
            if st.session_state['selected_person'] in filtered_people:
                # If a person is selected and is in the filtered list, find their index (+1 for placeholder)
                initial_person_index = filtered_people.index(st.session_state['selected_person']) + 1 
            
            person_selection = st.selectbox(
                f"Select {'Investor' if st.session_state['selected_transaction_type'] == 'Paid to Me' else 'Client'}",
                options=display_options,
                index=initial_person_index,
                key='person_selectbox_widget' # Unique key for the widget
            )

            # Update session state with the actual selected person (not the placeholder)
            if person_selection == "Select a person...":
                st.session_state['selected_person'] = None # Store None if placeholder is selected
            else:
                st.session_state['selected_person'] = person_selection # Store the actual person name
            
            # Selectbox for status, linked to session state
            status = st.selectbox(
                "Status", 
                ["completed", "pending"], 
                key='status_input' # Linked to session state
            )
            
            # Text input for description, linked to session state
            description = st.text_input(
                "Description (optional)", 
                key='description_input' # Linked to session state
            )
        
        submitted = st.form_submit_button("Add Transaction")
        if submitted:
            # Validate that a person is selected (not the placeholder)
            if st.session_state['selected_person'] is None: 
                st.error("Please select a person to add the transaction.")
            else:
                try:
                    new_entry = pd.DataFrame([[
                        st.session_state['date_input'].strftime("%Y-%m-%d"), 
                        st.session_state['selected_person'], # Use the value from session state
                        st.session_state['amount_input'], 
                        'paid_to_me' if st.session_state['selected_transaction_type'] == "Paid to Me" else 'i_paid', 
                        st.session_state['status_input'],
                        st.session_state['description_input'] or ''
                    ]], columns=["date", "person", "amount", "type", "status", "description"])
                    
                    new_entry.to_csv(CSV_FILE, mode='a', header=False, index=False)
                    st.success("Transaction added successfully!")
                    generate_summary() # Regenerate HTML summary and push to git
                    
                    # Reset all form fields in session state after successful submission
                    reset_transaction_form() 
                    
                    # Rerun the app to ensure all widgets reflect the reset state and updated balances
                    st.rerun() 
                except Exception as e:
                    st.error(f"Error adding transaction: {str(e)}")

with tab2:
    st.subheader("Transaction History")
    
    view_option = st.radio("View", ["All", "Received", "Paid"], horizontal=True)
    
    try:
        df = pd.read_csv(CSV_FILE)
        if len(df) > 0:
            # Ensure 'description' column exists
            for col in ["description"]:
                if col not in df.columns:
                    df[col] = ''
            
            people_df = pd.read_csv(PEOPLE_FILE)
            df = pd.merge(df, people_df, left_on='person', right_on='name', how='left')
            
            # Format amount and type for display in the dataframe
            df['amount'] = df['amount'].apply(lambda x: f"Rs. {float(x):,.2f}")
            df['type'] = df['type'].apply(lambda x: "Received" if x == "paid_to_me" else "Paid")
            
            # Filter transactions based on the selected view option
            if view_option == "Received":
                df = df[df['type'] == "Received"]
            elif view_option == "Paid":
                df = df[df['type'] == "Paid"]
            
            # Define columns to show in the Streamlit dataframe
            columns_to_show = ['date', 'person', 'amount', 'type', 'status']
            if 'description' in df.columns:
                columns_to_show.append('description')
            
            st.dataframe(df[columns_to_show], hide_index=True, use_container_width=True)
        else:
            st.info("No transactions recorded yet.")
    except Exception as e:
        st.error(f"Error loading transactions: {str(e)}")

with tab3:
    st.subheader("Manage People")
    
    with st.expander("➕ Add New Person"):
        # Form for adding a new person, with clear_on_submit=True
        with st.form("person_add_form", clear_on_submit=True): 
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Name", key='new_person_name') # Unique key for input
            with col2:
                category = st.selectbox("Category", ["investor", "client"], key='new_person_category') # Unique key for selectbox
            
            submitted = st.form_submit_button("Add Person")
            if submitted:
                try:
                    people_df = pd.read_csv(PEOPLE_FILE)
                    if name.strip() == "":
                        st.warning("Please enter a name")
                    elif name.strip() in people_df['name'].values:
                        st.warning("This person already exists!")
                    else:
                        new_person = pd.DataFrame([[name.strip(), category]], columns=["name", "category"])
                        new_person.to_csv(PEOPLE_FILE, mode='a', header=False, index=False)
                        st.success(f"{name.strip()} added as {category}!")
                        st.rerun() # Rerun to refresh the people list immediately in the dataframe below
                except Exception as e:
                    st.error(f"Error adding person: {str(e)}")
    
    try:
        people_df = pd.read_csv(PEOPLE_FILE)
        if len(people_df) > 0:
            st.dataframe(people_df, hide_index=True, use_container_width=True)
            
            # Ensure selectbox for deletion has options
            if not people_df['name'].empty:
                person_to_delete = st.selectbox("Select person to delete", people_df['name'], key='person_to_delete_selectbox') # Unique key
                if st.button("Delete Selected Person"):
                    transactions = pd.read_csv(CSV_FILE)
                    if person_to_delete in transactions['person'].values:
                        st.error("Cannot delete - this person has existing transactions")
                    else:
                        people_df = people_df[people_df['name'] != person_to_delete]
                        people_df.to_csv(PEOPLE_FILE, index=False)
                        st.success(f"{person_to_delete} deleted!")
                        st.rerun() # Rerun to refresh the people list immediately
            else:
                st.info("No people to delete.")

        else:
            st.info("No people added yet.")
    except Exception as e:
        st.error(f"Error loading people: {str(e)}")

# Current balances displayed in the sidebar
st.sidebar.header("Current Balances")
try:
    df = pd.read_csv(CSV_FILE)
    if len(df) > 0:
        received = df[df['type'] == 'paid_to_me']['amount'].sum()
        paid = df[df['type'] == 'i_paid']['amount'].sum()
        st.sidebar.metric("Total Received", f"Rs. {received:,.2f}")
        st.sidebar.metric("Total Paid", f"Rs. {paid:,.2f}")
        st.sidebar.metric("Net Balance", f"Rs. {received - paid:,.2f}", delta_color="inverse")
    else:
        st.sidebar.info("No transactions yet")
except Exception as e:
    st.sidebar.error("Error loading balances")
