import frappe
import json
import hmac
import hashlib
import requests
import traceback
from frappe import _
from frappe.utils import get_url, get_datetime, now_datetime, cint
from frappe.integrations.utils import create_request_log

# Cashfree API URLs
CASHFREE_TEST_URL = "https://sandbox.cashfree.com/pg"
CASHFREE_PROD_URL = "https://api.cashfree.com/pg"

@frappe.whitelist(allow_guest=True)
def make_payment():
    """Create a new payment order with Cashfree"""
    try:
        # Debug: Log all received data to understand what's available
        frappe.logger().info(f"make_payment called with frappe.form_dict: {json.dumps(frappe.form_dict)}")
        frappe.logger().info(f"make_payment called with frappe.request.data: {frappe.request.data}")
        
        # Get payment data from the request
        data = frappe.form_dict
        
        # If data is coming from a different source, try to parse it
        if not data and frappe.request.data:
            try:
                data = json.loads(frappe.request.data)
                frappe.logger().info(f"Parsed data from request.data: {json.dumps(data)}")
            except Exception as parse_error:
                frappe.logger().error(f"Failed to parse request.data: {str(parse_error)}")
        
        # Check for missing form_dict data
        if not data or not isinstance(data, dict) or len(data) == 0:
            frappe.logger().error("No data received in the request")
            return {
                "status": "Error",
                "message": _("No payment data received"),
                "error": "Empty request data"
            }
        
        # Log the data we're working with
        frappe.logger().info(f"Processing payment with data: {json.dumps(data)}")
        
        # Look for amount in different possible fields
        amount = data.get("amount") or data.get("order_amount") or data.get("grand_total")
        if not amount:
            # Try to get amount from reference document if provided
            reference_doctype = data.get("reference_doctype")
            reference_docname = data.get("reference_docname")
            if reference_doctype and reference_docname:
                try:
                    reference_doc = frappe.get_doc(reference_doctype, reference_docname)
                    # Try common field names for amount
                    for field in ["grand_total", "total", "total_amount", "amount", "price"]:
                        if hasattr(reference_doc, field) and getattr(reference_doc, field):
                            amount = getattr(reference_doc, field)
                            frappe.logger().info(f"Found amount {amount} in reference document field {field}")
                            break
                except Exception as doc_error:
                    frappe.logger().error(f"Error fetching reference doc: {str(doc_error)}")
        
        # Prepare data with defaults for missing values
        processed_data = {
            "reference_doctype": data.get("reference_doctype"),
            "reference_docname": data.get("reference_docname"),
            "amount": amount,
            "currency": data.get("currency") or "INR",
            "payer_name": data.get("payer_name") or data.get("customer_name") or "Customer",
            "payer_email": data.get("payer_email") or data.get("customer_email") or "customer@example.com",
            "payer_phone": data.get("payer_phone") or data.get("customer_phone") or "9999999999",
            "description": data.get("description") or data.get("order_note") or "Payment"
        }
        
        # Validate required parameters with clear error messages
        missing_fields = []
        for field in ["reference_doctype", "reference_docname", "amount"]:
            if not processed_data.get(field):
                missing_fields.append(field)
        
        if missing_fields:
            missing_fields_str = ", ".join(missing_fields)
            frappe.logger().error(f"Missing required fields: {missing_fields_str}")
            return {
                "status": "Error",
                "message": _("Missing required payment information"),
                "error": f"Required field(s) {missing_fields_str} missing",
                "received_data": data
            }
        
        # Get Cashfree settings
        cashfree_settings = frappe.get_single("Cashfree Settings")
        if not cashfree_settings:
            frappe.throw(_("Cashfree Settings not found. Please configure Cashfree Settings first."))
        
        # Get reference document
        reference_doctype = processed_data.get("reference_doctype")
        reference_docname = processed_data.get("reference_docname")
        reference_doc = frappe.get_doc(reference_doctype, reference_docname)
        
        # Create a unique order ID
        order_id = f"CF{reference_docname.replace('-', '')}"[:20]
        
        # Create return URLs
        base_url = get_url()
        return_url = data.get("redirect_url") or cashfree_settings.redirect_url or f"{base_url}/api/method/cashfree.api.payment_callback"
        notify_url = cashfree_settings.webhook_url or f"{base_url}/api/method/cashfree.api.webhook_handler"
        
        # Determine API endpoint based on mode
        base_url = CASHFREE_TEST_URL if cashfree_settings.mode == "TEST" else CASHFREE_PROD_URL
        
        # Prepare the order request
        order_data = {
            "order_id": order_id,
            "order_amount": float(processed_data.get("amount")),
            "order_currency": processed_data.get("currency"),
            "order_note": processed_data.get("description"),
            "customer_details": {
                "customer_id": f"CUST{reference_docname.replace('-', '')}"[:15],
                "customer_name": processed_data.get("payer_name"),
                "customer_email": processed_data.get("payer_email"),
                "customer_phone": processed_data.get("payer_phone")
            },
            "order_meta": {
                "return_url": f"{return_url}?order_id={order_id}",
                "notify_url": notify_url,
                "payment_methods": ""  # Leave empty for all payment methods
            }
        }
        
        frappe.logger().info(f"Cashfree order data: {json.dumps(order_data)}")
        
        # Create log of the request
        request_log = create_request_log(order_data, "Host", "Cashfree")
        
        # Make the API request to Cashfree
        headers = {
            "x-api-version": "2022-09-01",
            "x-client-id": cashfree_settings.api_key,
            "x-client-secret": cashfree_settings.get_password("secret_key"),
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{base_url}/orders", 
            headers=headers,
            json=order_data
        )
        
        # Update request log with response
        request_log.response = response.text
        request_log.status_code = response.status_code
        request_log.save()
        
        # Process response
        if response.status_code >= 200 and response.status_code < 300:
            response_data = response.json()
            frappe.logger().info(f"Cashfree response: {json.dumps(response_data)}")
            
            # Save payment details for future reference
            payment_request = frappe.new_doc("Payment Request")
            payment_request.update({
                "payment_gateway": "Cashfree",
                "payment_gateway_account": "Cashfree",
                "payment_request_type": "Outward",
                "reference_doctype": reference_doctype,
                "reference_name": reference_docname,
                "grand_total": processed_data.get("amount"),
                "currency": processed_data.get("currency"),
                "email_to": processed_data.get("payer_email"),
                "subject": f"Payment Request for {reference_docname}",
                "message": processed_data.get("description"),
                "status": "Initiated",
                "gateway_data": json.dumps({
                    "order_id": order_id,
                    "payment_link": response_data.get("payment_link")
                })
            })
            payment_request.flags.ignore_permissions = True
            payment_request.save()
            
            return {
                "status": "Success",
                "message": _("Payment initiated successfully"),
                "payment_url": response_data.get("payment_link"),
                "order_id": order_id,
                "reference_name": reference_docname
            }
        else:
            error_msg = response.text
            frappe.log_error(f"Cashfree payment creation failed: {error_msg}", "Cashfree Payment Error")
            
            return {
                "status": "Error",
                "message": _("Failed to initiate payment"),
                "error": error_msg
            }
        
    except Exception as e:
        # Log the error
        frappe.logger().error(f"Error in make_payment: {str(e)}")
        frappe.logger().error(traceback.format_exc())
        frappe.log_error(traceback.format_exc(), "Cashfree Payment Error")
        
        # Return error response
        return {
            "status": "Error",
            "message": _("An error occurred while processing your payment"),
            "error": str(e)
        }

# The rest of the functions remain the same
@frappe.whitelist(allow_guest=True)
def payment_callback():
    """Handle the redirect after payment completion"""
    try:
        # Get callback data
        data = frappe.form_dict
        order_id = data.get("order_id")
        
        # Rest of the function remains the same...
        
    except Exception as e:
        frappe.logger().error(f"Error in payment_callback: {str(e)}")
        frappe.logger().error(traceback.format_exc())

# Include other functions from the previous implementation