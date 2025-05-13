# 🛍️ Shopware to Google Sheets Exporter

This Python script fetches **Shopware order data** and exports daily aggregated **net and total revenue**, plus **order counts**, to a specified **Google Sheets tab**. It includes support for filtering by payment status and corrects for refunded transactions.

---

## ✅ Features

* Filters orders by transaction status:

  * `paid`
  * `in_progress`
  * `refunded_partially`
  * `refunded`
* Automatically subtracts revenue from refunded orders
* Ensures each order is counted **only once**
* Aggregates by order date
* Exports to Google Sheets via Service Account

---

## 📄 Output Example

| Date       | Number of Orders | Revenue (Net) | Revenue (Total) |
| ---------- | ---------------- | ------------- | --------------- |
| 2025-04-01 | 12               | 842.50        | 999.80          |
| 2025-04-02 | 17               | 1,234.90      | 1,453.00        |

---

## 📂 Google Sheet Output

Your data will be exported to:

👉 [Shopware Orders Sheet](https://docs.google.com/spreadsheets/d/1YIz6plMZUPPu6QsRoCLWawIKpnwJRhp0xnP4PFkXajw/edit#gid=1254539016)

Tab name: **\[Data] Shopware Orders NEW**

---

## 🚀 Setup & Usage

1. Clone this repo
2. Set environment variables:

   ```bash
   export SHOPWARE_CLIENT_ID=xxx
   export SHOPWARE_CLIENT_SECRET=xxx
   export GOOGLE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}'
   ```
3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
4. Run the script:

   ```bash
   python shopware_API.py
   ```

---

## 🧠 Notes

* Refunds (`refunded`, `refunded_partially`) are **subtracted** from revenue totals
* Orders are counted **once only**, regardless of multiple transactions
* Requires Shopware API v6

---

## 📬 Questions?

Open an issue or reach out to [@trafficdesignkoeln](https://github.com/trafficdesignkoeln) 🧠
