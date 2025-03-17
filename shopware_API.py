import requests
import pandas as pd
from gspread import service_account
from gspread_dataframe import set_with_dataframe
from datetime import datetime
from dateutil import parser  # Handles ISO 8601 dates with timezones
import locale
import os
import json

# ------------------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------------------
SHOPWARE_API_URL = "https://www.mediatec.de/api/search/order"
SPREADSHEET_URL = 'https://docs.google.com/spreadsheets/d/1YIz6plMZUPPu6QsRoCLWawIKpnwJRhp0xnP4PFkXajw/edit?pli=1&gid=1254539016#gid=1254539016'
TARGET_SHEET = '[Data] Shopware Orders NEW'

# Set German locale for proper number formatting
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')

# ------------------------------------------------------------------------------
# AUTHENTICATE WITH SHOPWARE API
# ------------------------------------------------------------------------------
# Define constants


CLIENT_ID = os.getenv('SHOPWARE_CLIENT_ID')
CLIENT_SECRET = os.getenv('SHOPWARE_CLIENT_SECRET')

# Save Google Service Account JSON from environment variable
SERVICE_ACCOUNT_FILE = 'service-account.json'
with open(SERVICE_ACCOUNT_FILE, 'w') as f:
    f.write(os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON'))

def get_shopware_access_token():
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(TOKEN_ENDPOINT, json=payload, headers=headers)
    
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Content: {response.content.decode('utf-8')}")  # Show detailed error message if any
    
    response.raise_for_status()  # Raise HTTPError for bad responses
    token = response.json().get('access_token')
    
    if token:
        print("✅ Access token retrieved successfully.")
    else:
        print("❌ Failed to retrieve access token.")
    
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
                {
                    "type": "equals",
                    "field": "transactions.stateMachineState.technicalName",
                    "value": "paid"
                },
                {
                    "type": "range",
                    "field": "orderDateTime",
                    "parameters": {
                        "gte": "2022-01-01T00:00:00.000Z"
                    }
                }
            ],
            "limit": limit,
            "page": page
        }
        response = requests.post(SHOPWARE_API_URL, headers=headers, json=payload)
        
        if response.status_code != 200:
            print(f"❌ Error fetching data: Response Code {response.status_code}")
            break

        data = response.json().get('data', [])
        if not data:
            has_more_data = False
            break

        # Aggregate data by date
        for order in data:
            date_str = order['orderDateTime']
            try:
                # Use dateutil parser to handle ISO format with timezone
                date_obj = parser.isoparse(date_str)
            except ValueError:
                print(f"❌ Error parsing date: {date_str}")
                continue  # Skip this entry if date parsing fails

            date = date_obj.strftime("%Y-%m-%d")  # Convert back to string if needed
            revenue = float(order.get('amountNet', 0))

            if date not in aggregated_data:
                aggregated_data[date] = {'orders': 0, 'revenue': 0.0}

            aggregated_data[date]['orders'] += 1
            aggregated_data[date]['revenue'] += revenue

        page += 1  # Move to next page

    return aggregated_data

# ------------------------------------------------------------------------------
# PROCESS AND FORMAT DATA
# ------------------------------------------------------------------------------
def process_data(aggregated_data):
    sorted_dates = sorted(aggregated_data.keys())
    data_to_insert = []

    for date in sorted_dates:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        formatted_date = date_obj.strftime("%Y-%m-%d")  # Date only, no time
        orders = aggregated_data[date]['orders']
        revenue = locale.format_string("%.2f", aggregated_data[date]['revenue']).replace('.', ',')

        data_to_insert.append([formatted_date, orders, revenue])

    # Create DataFrame
    df = pd.DataFrame(data_to_insert, columns=["Date", "Number of Orders", "Revenue (Net)"])
    
    # 🛠 Parse Date column as date-only (no time)
    df['Date'] = pd.to_datetime(df['Date']).dt.date  # Extract only date part
    
    # 🛠 Ensure 'Number of Orders' is an integer
    df['Number of Orders'] = pd.to_numeric(df['Number of Orders'], errors='coerce').fillna(0).astype(int)
    
    # 🛠 Convert 'Revenue (Net)' column to float
    df['Revenue (Net)'] = df['Revenue (Net)'].str.replace('.', '', regex=False).str.replace(',', '.', regex=False).astype(float)
    
    # 🔍 Show data types and preview data to confirm changes
    print("\n🔄 Data Types After Parsing:")
    print(df.dtypes)
    print("\n📊 Preview Data:")
    print(df.head(10))  # Show first 10 rows for inspection
    
    return df
# ------------------------------------------------------------------------------
# EXPORT TO GOOGLE SHEETS
# ------------------------------------------------------------------------------
def export_to_google_sheets(df):
    client = service_account(filename=SERVICE_ACCOUNT_FILE)
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    worksheet = spreadsheet.worksheet(TARGET_SHEET)
    worksheet.clear()

    # 🛠 Explicitly set format to Plain Text for 'Number of Orders' to avoid date conversion
    worksheet.format('B2:B', {'numberFormat': {'type': 'NUMBER'}})  # Ensure column B is formatted as a number

    # Export DataFrame to Google Sheets
    set_with_dataframe(worksheet, df, include_index=False, include_column_header=True, resize=True)

    print(f"✅ Data exported successfully to Google Sheet: '{TARGET_SHEET}'")
