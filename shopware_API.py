import os
import json
import locale
import requests
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2 import service_account
from datetime import datetime
from dateutil import parser  # Handles ISO 8601 dates with timezones

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------
SHOPWARE_API_URL = "https://www.mediatec.de/api/search/order"
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1YIz6plMZUPPu6QsRoCLWawIKpnwJRhp0xnP4PFkXajw/edit?pli=1&gid=1254539016#gid=1254539016"
TARGET_SHEET = "[Data] Shopware Orders NEW"

# Load credentials from environment variables
CLIENT_ID = os.getenv("SHOPWARE_CLIENT_ID")
CLIENT_SECRET = os.getenv("SHOPWARE_CLIENT_SECRET")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

# Check if required environment variables are set
if not CLIENT_ID or not CLIENT_SECRET:
    raise ValueError("❌ ERROR: SHOPWARE_CLIENT_ID or SHOPWARE_CLIENT_SECRET is not set!")

if not GOOGLE_SERVICE_ACCOUNT_JSON:
    raise ValueError("❌ ERROR: GOOGLE_SERVICE_ACCOUNT_JSON is not set!")

# Parse Google Service Account JSON
try:
    service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
except json.JSONDecodeError:
    raise ValueError("❌ ERROR: GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON!")

# Set up Google Sheets authentication
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
client = gspread.authorize(credentials)

# Set German locale for proper number formatting
try:
    locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
except locale.Error:
    print("⚠️ Locale 'de_DE.UTF-8' is not available. Using default locale.")
    locale.setlocale(locale.LC_ALL, '')  # Use system default

# ------------------------------------------------------------------------------
# AUTHENTICATE WITH SHOPWARE API
# ------------------------------------------------------------------------------
TOKEN_ENDPOINT = "https://www.mediatec.de/api/oauth/token"

def get_shopware_access_token():
    headers = {'Content-Type': 'application/json'}
    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    
    response = requests.post(TOKEN_ENDPOINT, json=payload, headers=headers)
    
    if response.status_code != 200:
        raise ValueError(f"❌ ERROR: Failed to retrieve access token. Response: {response.text}")
    
    token = response.json().get('access_token')
    if token:
        print("✅ Access token retrieved successfully.")
    else:
        raise ValueError("❌ ERROR: Access token is missing in response.")

    return token

# ------------------------------------------------------------------------------
# FETCH ORDERS FROM SHOPWARE
# ------------------------------------------------------------------------------
def fetch_orders(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    limit = 500
    page = 1
    has_more_data = True
    aggregated_data = {}

    while has_more_data:
        payload = {
            "filter": [
                {"type": "equals", "field": "transactions.stateMachineState.technicalName", "value": "paid"},
                {"type": "range", "field": "orderDateTime", "parameters": {"gte": "2022-01-01T00:00:00.000Z"}}
            ],
            "limit": limit,
            "page": page
        }

        response = requests.post(SHOPWARE_API_URL, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"❌ ERROR: Failed to fetch orders. Response: {response.text}")
            break

        data = response.json().get('data', [])
        if not data:
            has_more_data = False
            break

        # Aggregate data by date
        for order in data:
            date_str = order['orderDateTime']
            try:
                date_obj = parser.isoparse(date_str)
            except ValueError:
                print(f"❌ ERROR: Unable to parse date: {date_str}")
                continue  # Skip if parsing fails

            date = date_obj.strftime("%Y-%m-%d")  # Convert to YYYY-MM-DD
            revenue = float(order.get('amountNet', 0))

            if date not in aggregated_data:
                aggregated_data[date] = {'orders': 0, 'revenue': 0.0}

            aggregated_data[date]['orders'] += 1
            aggregated_data[date]['revenue'] += revenue

        page += 1

    return aggregated_data

# ------------------------------------------------------------------------------
# PROCESS AND FORMAT DATA
# ------------------------------------------------------------------------------
def process_data(aggregated_data):
    sorted_dates = sorted(aggregated_data.keys())
    data_to_insert = []

    for date in sorted_dates:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y-%m-%d")  # Keep date format
        orders = aggregated_data[date]['orders']
        revenue = locale.format_string("%.2f", aggregated_data[date]['revenue']).replace('.', ',')

        data_to_insert.append([formatted_date, orders, revenue])

    # Create DataFrame
    df = pd.DataFrame(data_to_insert, columns=["Date", "Number of Orders", "Revenue (Net)"])
    
    # Convert columns to correct data types
    df['Date'] = pd.to_datetime(df['Date']).dt.date
    df['Number of Orders'] = pd.to_numeric(df['Number of Orders'], errors='coerce').fillna(0).astype(int)
    df['Revenue (Net)'] = df['Revenue (Net)'].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)

    print("\n📊 Processed Data Preview:")
    print(df.head(10))  # Display first 10 rows

    return df

# ------------------------------------------------------------------------------
# EXPORT TO GOOGLE SHEETS
# ------------------------------------------------------------------------------
def export_to_google_sheets(df):
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    worksheet = spreadsheet.worksheet(TARGET_SHEET)
    worksheet.clear()

    # Ensure 'Number of Orders' is formatted correctly in Google Sheets
    worksheet.format('B2:B', {'numberFormat': {'type': 'NUMBER'}})

    # Export DataFrame to Google Sheets
    set_with_dataframe(worksheet, df, include_index=False, include_column_header=True, resize=True)

    print(f"✅ Data exported successfully to Google Sheet: '{TARGET_SHEET}'")

# ------------------------------------------------------------------------------
# MAIN EXECUTION
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Starting Shopware Order Sync...")

    # Get Shopware access token
    access_token = get_shopware_access_token()

    # Fetch order data
    orders_data = fetch_orders(access_token)

    if not orders_data:
        print("⚠️ No order data found. Exiting.")
        exit(0)

    # Process data
    df = process_data(orders_data)

    # Export to Google Sheets
    export_to_google_sheets(df)

    print("🎉 Sync complete!")
