# Cashfree Payment Integration for Frappe/ERPNext

This app provides integration between Frappe/ERPNext and Cashfree Payment Gateway.

## Features

- Accept payments via Cashfree payment gateway
- Support for test and production environments
- Webhook integration for automatic payment updates
- Detailed payment tracking and logs
- Auto creation of payment entries for successful payments
- Customizable redirect URLs for success/failure

## Installation

### From the bench directory

```bash
# Get the app from GitHub
bench get-app https://github.com/chinmaybhatk/frappe-cashfree

# Install the app to your site
bench --site your-site.com install-app cashfree

# Migrate your database
bench --site your-site.com migrate
```

## Configuration

1. Go to **Cashfree Settings** in ERPNext and enter your API key and Secret key from your Cashfree dashboard.
2. Select the appropriate mode (TEST or PRODUCTION).
3. Configure the redirect URLs (optional).
4. Set up webhook URL in your Cashfree dashboard to receive automatic payment updates.

### Creating a Payment Gateway Account

1. Go to **Accounts > Payment Gateway Account > New**
2. Select "Cashfree" as the Payment Gateway
3. Select the account where payments will be recorded
4. Set the currency (Cashfree currently supports INR)
5. Save the account

## Usage

### From Sales Invoice

1. Open a Sales Invoice
2. Click on "Create Payment Request"
3. Select "Cashfree" as the Payment Gateway
4. Save the Payment Request
5. Click on "Generate Cashfree Payment Link"
6. Share the payment link with your customer

### From Payment Request

1. Create a new Payment Request
2. Select "Cashfree" as the Payment Gateway
3. Save the Payment Request
4. Click on "Generate Cashfree Payment Link"
5. Share the payment link with your customer

## Webhook Setup

For automatic payment updates, set up a webhook in your Cashfree dashboard:

1. Log in to your Cashfree dashboard
2. Go to Settings > Webhook
3. Add a new webhook with the URL: https://your-site.com/api/method/cashfree.handle_webhook
4. Configure the events you want to receive (at minimum, select "PAYMENT_SUCCESS")
5. Add a webhook secret key for enhanced security (optional but recommended)
6. Save the webhook configuration

## Webhook Events

The integration supports the following Cashfree webhook events:

- PAYMENT_SUCCESS: When a payment is successfully completed
- PAYMENT_FAILED: When a payment fails
- PAYMENT_USER_DROPPED: When a user abandons the payment process
- PAYMENT_AUTO_REFUNDED: When a payment is automatically refunded

## Troubleshooting

### Payment Not Updating Automatically

1. Check if the webhook is properly configured in Cashfree dashboard
2. Verify that your site is accessible from the internet
3. Check the Integration Request logs in ERPNext for any errors
4. Ensure the webhook secret key matches between Cashfree dashboard and ERPNext settings

### Missing Transaction Details

1. Go to the Payment Request
2. Click on "View Cashfree Payment" to see detailed transaction information
3. Check the Integration Request doctype for logs and raw data

## API Reference

The app provides the following API methods:

1. `cashfree.make_payment`: Creates a payment order and returns payment link
2. `cashfree.handle_redirect`: Handles redirect from Cashfree payment page
3. `cashfree.handle_webhook`: Processes webhook notifications from Cashfree
4. `cashfree.get_payment_status`: Retrieves payment status from Cashfree API
  hi
## Supported Features

The integration supports:

- Credit/Debit Cards
- UPI
- Netbanking
- Wallets
- EMI
- Pay Later options
- QR Code Payments

## Currency Support

Currently, this integration supports INR (Indian Rupee) only. Support for international currencies can be enabled in the Cashfree Settings.

## License

This Frappe app is licensed under the MIT License.