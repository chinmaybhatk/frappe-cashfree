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
        # Get payment data from the request
        data = frappe.form_dict
        
        # Validate required parameters
        required_fields = ["reference_doctype", "reference_docname", "amount", "currency", 
                          "payer_name", "payer_email", "payer_phone", "description"]
        
        for field in required_fields:
            if not data.get(field):
                frappe.throw(_(f"Required field {field} is missing"))
        
        # Get Cashfree settings
        cashfree_settings = frappe.get_single("Cashfree Settings")
        if not cashfree_settings:
            frappe.throw(_("Cashfree Settings not found. Please configure Cashfree Settings first."))
        
        # Get reference document
        reference_doctype = data.get("reference_doctype")
        reference_docname = data.get("reference_docname")
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
            "order_amount": float(data.get("amount")),
            "order_currency": data.get("currency", "INR"),
            "order_note": data.get("description", f"Payment for {reference_doctype} {reference_docname}"),
            "customer_details": {
                "customer_id": f"CUST{reference_docname.replace('-', '')}"[:15],
                "customer_name": data.get("payer_name"),
                "customer_email": data.get("payer_email"),
                "customer_phone": data.get("payer_phone")
            },
            "order_meta": {
                "return_url": f"{return_url}?order_id={order_id}",
                "notify_url": notify_url,
                "payment_methods": ""  # Leave empty for all payment methods
            }
        }
        
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
            
            # Save payment details for future reference
            payment_request = frappe.new_doc("Payment Request")
            payment_request.update({
                "payment_gateway": "Cashfree",
                "payment_gateway_account": "Cashfree",
                "payment_request_type": "Outward",
                "reference_doctype": reference_doctype,
                "reference_name": reference_docname,
                "grand_total": data.get("amount"),
                "currency": data.get("currency", "INR"),
                "email_to": data.get("payer_email"),
                "subject": f"Payment Request for {reference_docname}",
                "message": data.get("description", f"Payment for {reference_doctype} {reference_docname}"),
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

@frappe.whitelist(allow_guest=True)
def payment_callback():
    """Handle the redirect after payment completion"""
    try:
        # Get callback data
        data = frappe.form_dict
        order_id = data.get("order_id")
        
        if not order_id:
            frappe.throw(_("No order ID received in callback"))
        
        # Verify the payment status with Cashfree
        payment_status = verify_payment(order_id)
        
        # Get the payment request
        payment_requests = frappe.get_all(
            "Payment Request",
            filters={"gateway_data": ["like", f"%{order_id}%"]},
            fields=["name", "reference_doctype", "reference_name", "status"]
        )
        
        if not payment_requests:
            frappe.throw(_("No payment request found for this order"))
        
        payment_request = frappe.get_doc("Payment Request", payment_requests[0].name)
        reference_doctype = payment_request.reference_doctype
        reference_name = payment_request.reference_name
        
        if payment_status.get("order_status") == "PAID":
            # Payment successful
            payment_request.status = "Paid"
            payment_request.flags.ignore_permissions = True
            payment_request.save()
            
            # Create a payment entry if needed
            # This will depend on your specific workflow
            
            frappe.msgprint(_("Payment completed successfully!"))
            
            # Redirect to success page or back to the reference document
            success_url = frappe.get_doc("Cashfree Settings").get("redirect_url") or f"/app/{reference_doctype.lower().replace(' ', '-')}/{reference_name}"
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = success_url
            
        else:
            # Payment failed or pending
            payment_request.status = "Failed"
            payment_request.flags.ignore_permissions = True
            payment_request.save()
            
            frappe.msgprint(_("Payment was not successful. Please try again."))
            
            # Redirect to failure page
            failure_url = f"/payment-failed?order_id={order_id}"
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = failure_url
            
    except Exception as e:
        frappe.logger().error(f"Error in payment_callback: {str(e)}")
        frappe.logger().error(traceback.format_exc())
        frappe.log_error(traceback.format_exc(), "Cashfree Callback Error")
        
        # Show error and redirect to home
        frappe.msgprint(_("Error processing payment callback: {0}").format(str(e)))
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/"

@frappe.whitelist(allow_guest=True)
def webhook_handler():
    """Handle webhooks from Cashfree"""
    try:
        # Get the webhook data
        webhook_data = json.loads(frappe.request.data)
        event_type = webhook_data.get("event_type")
        order_id = webhook_data.get("data", {}).get("order", {}).get("order_id")
        
        if not order_id:
            frappe.throw(_("No order ID received in webhook"))
        
        # Verify webhook signature if configured
        cashfree_settings = frappe.get_single("Cashfree Settings")
        webhook_secret = cashfree_settings.get_password("webhook_secret")
        
        if webhook_secret:
            signature = frappe.request.headers.get("X-Webhook-Signature")
            computed_signature = hmac.new(
                webhook_secret.encode(),
                frappe.request.data,
                hashlib.sha256
            ).hexdigest()
            
            if not signature or signature != computed_signature:
                frappe.throw(_("Invalid webhook signature"))
        
        # Process based on event type
        if event_type == "ORDER_PAID":
            # Handle successful payment
            process_successful_payment(webhook_data)
        elif event_type == "PAYMENT_FAILED":
            # Handle failed payment
            process_failed_payment(webhook_data)
        
        return {"status": "Success"}
        
    except Exception as e:
        frappe.logger().error(f"Error in webhook_handler: {str(e)}")
        frappe.logger().error(traceback.format_exc())
        frappe.log_error(traceback.format_exc(), "Cashfree Webhook Error")
        
        return {
            "status": "Error",
            "message": str(e)
        }

def verify_payment(order_id):
    """Verify the payment status with Cashfree"""
    try:
        cashfree_settings = frappe.get_single("Cashfree Settings")
        
        # Determine API endpoint based on mode
        base_url = CASHFREE_TEST_URL if cashfree_settings.mode == "TEST" else CASHFREE_PROD_URL
        
        # Make the API request to Cashfree
        headers = {
            "x-api-version": "2022-09-01",
            "x-client-id": cashfree_settings.api_key,
            "x-client-secret": cashfree_settings.get_password("secret_key"),
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{base_url}/orders/{order_id}",
            headers=headers
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            return response.json()
        else:
            frappe.log_error(f"Payment verification failed: {response.text}", "Cashfree Payment Error")
            return {"order_status": "ERROR"}
        
    except Exception as e:
        frappe.log_error(f"Error verifying payment: {str(e)}", "Cashfree Payment Error")
        return {"order_status": "ERROR"}

def process_successful_payment(webhook_data):
    """Process a successful payment webhook"""
    order_id = webhook_data.get("data", {}).get("order", {}).get("order_id")
    
    # Get the payment request
    payment_requests = frappe.get_all(
        "Payment Request",
        filters={"gateway_data": ["like", f"%{order_id}%"]},
        fields=["name", "reference_doctype", "reference_name", "status"]
    )
    
    if not payment_requests:
        frappe.log_error(f"No payment request found for order {order_id}", "Cashfree Webhook Error")
        return
    
    payment_request = frappe.get_doc("Payment Request", payment_requests[0].name)
    
    # Update payment request status
    if payment_request.status != "Paid":
        payment_request.status = "Paid"
        payment_request.flags.ignore_permissions = True
        payment_request.save()
        
        # Create a payment entry or update reference document as needed
        # This will depend on your specific workflow

def process_failed_payment(webhook_data):
    """Process a failed payment webhook"""
    order_id = webhook_data.get("data", {}).get("order", {}).get("order_id")
    
    # Get the payment request
    payment_requests = frappe.get_all(
        "Payment Request",
        filters={"gateway_data": ["like", f"%{order_id}%"]},
        fields=["name"]
    )
    
    if not payment_requests:
        frappe.log_error(f"No payment request found for order {order_id}", "Cashfree Webhook Error")
        return
    
    payment_request = frappe.get_doc("Payment Request", payment_requests[0].name)
    
    # Update payment request status
    payment_request.status = "Failed"
    payment_request.flags.ignore_permissions = True
    payment_request.save()