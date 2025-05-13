import os
import json
import requests
from collections import defaultdict
from tabulate import tabulate
from dateutil import parser

# --------------------------------------------------------------------------
# CONFIGURATION
# --------------------------------------------------------------------------
SHOPWARE_API_URL = "https://www.mediatec.de/api/search/order"
TOKEN_ENDPOINT = "https://www.mediatec.de/api/oauth/token"
CLIENT_ID = os.getenv("SHOPWARE_CLIENT_ID")
CLIENT_SECRET = os.getenv("SHOPWARE_CLIENT_SECRET")

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
# FETCH ALL ORDERS (NO FILTER)
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
    status_counts = defaultdict(int)

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
            ]
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
            transaction = order.get('transactions', [{}])[0]
            state = transaction.get('stateMachineState', {}).get('technicalName', 'unknown')
            status_counts[state] += 1

        page += 1

    return status_counts

# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------
if __name__ == "__main__":
    print("🔍 Fetching all orders and grouping by payment status...")

    token = get_shopware_access_token()
    grouped = fetch_all_orders(token)

    # Print as table
    print("\n📊 Order Count by Payment Status:\n")
    table = sorted(grouped.items(), key=lambda x: x[1], reverse=True)
    print(tabulate(table, headers=["Payment Status", "Order Count"], tablefmt="github"))