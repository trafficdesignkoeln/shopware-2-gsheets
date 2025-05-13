import os
import json
import requests
import pandas as pd
import gspread
from collections import defaultdict
from tabulate import tabulate
from google.oauth2 import service_account
from dateutil import parser

# --------------------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------------------
SHOPWARE_API_URL = "https://www.mediatec.de/api/search/order"
TOKEN_ENDPOINT = "https://www.mediatec.de/api/oauth/token"
CLIENT_ID = os.getenv("SHOPWARE_CLIENT_ID")
CLIENT_SECRET = os.getenv("SHOPWARE_CLIENT_SECRET")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1YIz6plMZUPPu6QsRoCLWawIKpnwJRhp0xnP4PFkXajw/edit#gid=1254539016"
TARGET_SHEET = "Monthly Order Status"

# --------------------------------------------------------------------------
# AUTHENTICATE
# --------------------------------------------------------------------------
def get_shopware_access_token():
    headers = {'Content-Type': 'application/json'}
    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(TOKEN_ENDPOINT, json=payload, headers=headers)
    response.raise_for_status()
    return response.json().get('access_token')

# --------------------------------------------------------------------------
# FETCH AND GROUP ORDERS BY YEAR-MONTH AND STATUS
# --------------------------------------------------------------------------
def fetch_all_orders(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    limit = 500
    page = 1
    has_more_data = True
    monthly_status_counts = defaultdict(int)

    while has_more_data:
        payload = {
            "limit": limit,
            "page": page,
            "filter": [
                {
                    "type": "range",
                    "field": "orderDateTime",
                    "parameters": {
                        "gte": "2022-01-01T00:00:00.000Z"
                    }
                }
            ],
            "associations": {
                "transactions": {
                    "associations": {
                        "stateMachineState": {}
                    }
                }
            }
        }

        response = requests.post(SHOPWARE_API_URL, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"❌ API error: {response.text}")
            break

        data = response.json().get('data', [])
        if not data:
            has_more_data = False
            break

        for order in data:
            try:
                dt = parser.isoparse(order['orderDateTime'])
                year_month = dt.strftime("%Y-%m")
            except Exception:
                continue

            transactions = order.get('transactions') or []
            if transactions:
                status = transactions[0].get('stateMachineState', {}).get('technicalName', 'unknown')
            else:
                status = 'no_transaction'

            key = (year_month, status)
            monthly_status_counts[key] += 1

        print(f"➡️ Page {page}: Fetched {len(data)} orders.")
        page += 1

    return monthly_status_counts

# --------------------------------------------------------------------------
# EXPORT TO GOOGLE SHEETS
# --------------------------------------------------------------------------
def export_to_google_sheets(data_dict):
    rows = [(month, status, count) for (month, status), count in sorted(data_dict.items())]
    df = pd.DataFrame(rows, columns=["Year-Month", "Payment Status", "Order Count"])

    print("\n📊 Table Preview:")
    print(tabulate(df.head(20), headers="keys", tablefmt="github"))

    # Auth for Google Sheets
    service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    client = gspread.authorize(credentials)

    sheet = client.open_by_url(SPREADSHEET_URL)
    worksheet = sheet.worksheet(TARGET_SHEET)
    worksheet.clear()

    from gspread_dataframe import set_with_dataframe
    set_with_dataframe(worksheet, df, include_index=False, include_column_header=True, resize=True)

    print(f"✅ Exported grouped data to sheet tab: '{TARGET_SHEET}'")

# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Grouping orders by month + status...")

    token = get_shopware_access_token()
    grouped_data = fetch_all_orders(token)
    export_to_google_sheets(grouped_data)

    print("🎉 Sync complete!")