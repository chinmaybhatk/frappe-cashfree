# -*- coding: utf-8 -*-
# Copyright (c) 2025, walue.biz and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import requests
import hmac
import hashlib
import base64
from frappe import _
from frappe.utils import get_url, cint, flt, cstr, now, get_datetime
from frappe.integrations.utils import create_request_log 
from cashfree.doctype.cashfree_settings.cashfree_settings import CashfreeSettings

@frappe.whitelist()
# Add this where the Payment Request is being created
def make_payment(checkout_data=None):
    # If checkout_data is not provided, try to get data from frappe.form_dict
    if checkout_data is None:
        checkout_data = frappe.form_dict
    
    # If checkout_data is still empty, initialize it as an empty dict
    if not checkout_data:
        checkout_data = {}
    
    # Create a Payment Request with proper reference
    payment_request = frappe.new_doc("Payment Request")
    
    # Set required fields to pass validation
    payment_request.reference_doctype = checkout_data.get("reference_doctype") or "Sales Order"
    payment_request.reference_name = checkout_data.get("reference_name")
    
    # If reference_name is not provided, create a temporary "Shopping Cart" reference
    if not payment_request.reference_name:
        # Check if there's a Sales Order or Cart to reference
        cart_id = frappe.db.get_value("Shopping Cart", 
                                     {"owner": frappe.session.user, "status": "Open"}, 
                                     "name")
        if cart_id:
            payment_request.reference_doctype = "Shopping Cart"
            payment_request.reference_name = cart_id
        else:
            # As a fallback, create a dummy reference
            # Note: You should modify this based on your actual requirements
            dummy_ref = frappe.new_doc("Sales Order")
            dummy_ref.order_type = "Shopping Cart"
            dummy_ref.customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
            dummy_ref.currency = checkout_data.get("currency") or "INR"
            dummy_ref.company = frappe.db.get_single_value("Global Defaults", "default_company")
            dummy_ref.transaction_date = frappe.utils.today()
            dummy_ref.save(ignore_permissions=True)
            
            payment_request.reference_doctype = "Sales Order"
            payment_request.reference_name = dummy_ref.name
    
    # Set other required fields
    payment_request.payment_request_type = "Inward"
    payment_request.currency = checkout_data.get("currency") or "INR"
    payment_request.grand_total = checkout_data.get("amount") or 0
    payment_request.payment_gateway = "Cashfree"
    payment_request.payment_gateway_account = frappe.db.get_value("Payment Gateway Account", 
                                                                 {"payment_gateway": "Cashfree", "currency": payment_request.currency},
                                                                 "name")
    
    # Email details
    payment_request.email_to = checkout_data.get("email") or frappe.session.user
    payment_request.subject = _("Payment Request for {}").format(payment_request.reference_name)
    payment_request.message = checkout_data.get("message") or _("Please click the link below to make your payment")
    
    # Save the payment request
    payment_request.save(ignore_permissions=True)
    
    # Submit if auto-submission is required
    if cint(frappe.db.get_single_value("Cashfree Settings", "submit_payment_request", default=1)):
        payment_request.submit()
    
    return payment_request

def create_payment_request(reference_doctype, reference_docname):
    """Create a payment request for the order"""
    reference_doc = frappe.get_doc(reference_doctype, reference_docname)
    
    payment_request = frappe.new_doc("Payment Request")
    payment_request.payment_gateway = "Cashfree"
    payment_request.payment_gateway_account = get_gateway_account("Cashfree")
    payment_request.payment_request_type = "Inward"
    payment_request.party_type = reference_doc.get("party_type") or "Customer"
    payment_request.party = reference_doc.get("party") or reference_doc.get("customer")
    payment_request.reference_doctype = reference_doctype
    payment_request.reference_docname = reference_docname
    payment_request.grand_total = reference_doc.get("grand_total") or reference_doc.get("total")
    payment_request.currency = reference_doc.get("currency")
    payment_request.email_to = reference_doc.get("email_to") or reference_doc.get("contact_email")
    
    return payment_request


def get_gateway_account(gateway_name):
    """Get payment gateway account"""
    return frappe.db.get_value("Payment Gateway Account", 
        {"payment_gateway": gateway_name}, "name")


def create_cashfree_order(payment_request, cashfree_settings):
    """Create order in Cashfree"""
    api_url = f"{cashfree_settings.get_api_url()}/pg/orders"
    
    # Generate a unique order id
    order_id = f"CFORDER_{payment_request.name}"
    
    # Get site URL for callbacks
    site_url = frappe.utils.get_url()
    
    # Prepare order data
    order_data = {
        "order_id": order_id,
        "order_amount": flt(payment_request.grand_total),
        "order_currency": payment_request.currency,
        "customer_details": {
            "customer_id": payment_request.party,
            "customer_email": payment_request.email_to,
            "customer_phone": get_contact_phone(payment_request.party_type, payment_request.party) or "9999999999"
        },
        "order_meta": {
            "payment_request_id": payment_request.name,
            "reference_doctype": payment_request.reference_doctype,
            "reference_docname": payment_request.reference_docname
        },
        "order_note": f"Payment for {payment_request.reference_doctype} {payment_request.reference_docname}",
        "notify": {
            "email": cint(cashfree_settings.get("send_email_notification", 0)),
            "sms": cint(cashfree_settings.get("send_sms_notification", 0))
        }
    }
    
    # Add callback URLs
    if cashfree_settings.redirect_url:
        order_data["return_url"] = cashfree_settings.redirect_url
    else:
        order_data["return_url"] = f"{site_url}/api/method/cashfree.api.handle_redirect"
    
    # Add webhook URL if configured
    if cashfree_settings.webhook_url:
        order_data["notify"]["webhook"] = cashfree_settings.webhook_url
    else:
        order_data["notify"]["webhook"] = f"{site_url}/api/method/cashfree.api.handle_webhook"


    
    # Headers for API request
    headers = {
        "x-api-version": "2022-09-01",  # Use the appropriate API version
        "Content-Type": "application/json",
        "x-client-id": cashfree_settings.api_key,
        "x-client-secret": cashfree_settings.secret_key
    }
    
    # Make the API call
    response = requests.post(api_url, headers=headers, json=order_data)
    if response.status_code >= 200 and response.status_code < 300:
        return response.json()
    else:
        frappe.log_error(
            title="Cashfree Order Creation Failed",
            message=f"Status Code: {response.status_code}, Response: {response.text}"
        )
        return {"status": "ERROR", "message": response.text}


def get_contact_phone(party_type, party):
    """Get contact phone number for party"""
    contact_name = frappe.db.get_value("Contact", 
        {"links": {"link_doctype": party_type, "link_name": party}}, "name")
    
    if contact_name:
        return frappe.db.get_value("Contact", contact_name, "mobile_no") or \
               frappe.db.get_value("Contact", contact_name, "phone")
    return None


@frappe.whitelist(allow_guest=True)
def handle_redirect():
    """Handle the redirect from Cashfree payment page"""
    try:
        # Get the payment data from GET parameters
        data = frappe.request.args
        
        # Verify the payment
        order_id = data.get("order_id")
        order_details = get_payment_status(order_id)
        
        if order_details.get("order_status") == "PAID":
            # Extract the payment request ID from order_id
            if order_id.startswith("CFORDER_"):
                payment_request_id = order_id[8:]  # Remove "CFORDER_" prefix
                update_payment_status(payment_request_id, order_details)
                
                # Redirect to success page
                payment_request = frappe.get_doc("Payment Request", payment_request_id)
                redirect_url = payment_request.get_redirect_url()
                frappe.local.response["type"] = "redirect"
                frappe.local.response["location"] = redirect_url or "/payment-success"
            else:
                frappe.log_error(title="Invalid Cashfree Order ID", message=str(data))
                frappe.local.response["type"] = "redirect"
                frappe.local.response["location"] = "/payment-failed"
        else:
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/payment-failed"
            
    except Exception as e:
        frappe.log_error(title="Cashfree Redirect Handler Error", message=frappe.get_traceback())
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-failed"


@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """Handle webhook notifications from Cashfree"""
    try:
        # Get the webhook data
        data = json.loads(frappe.request.data)
        event_type = data.get("event_type")
        
        # Log the webhook data
        create_request_log(data, "Host", "Cashfree")
        
        # Verify webhook signature
        if not verify_webhook_signature(frappe.request):
            frappe.throw(_("Invalid webhook signature"))
        
        # Process the webhook based on event type
        if event_type == "PAYMENT_SUCCESS":
            order_id = data.get("data", {}).get("order", {}).get("order_id")
            if order_id and order_id.startswith("CFORDER_"):
                payment_request_id = order_id[8:]  # Remove "CFORDER_" prefix
                update_payment_status(payment_request_id, data.get("data", {}).get("order", {}))
        
        return {"status": "success"}
        
    except Exception as e:
        frappe.log_error(title="Cashfree Webhook Error", message=frappe.get_traceback())
        return {"status": "error", "message": str(e)}


def verify_webhook_signature(request):
    """Verify the webhook signature"""
    try:
        # Get cashfree settings
        cashfree_settings = frappe.get_doc("Cashfree Settings")
        
        # If webhook secret is not set, skip verification (not recommended for production)
        if not cashfree_settings.webhook_secret:
            return True
        
        # Get webhook signature from headers
        cf_signature = request.headers.get("x-webhook-signature")
        if not cf_signature:
            return False
        
        # Get request body as bytes
        request_body = request.data
        
        # Calculate expected signature
        timestamp = request.headers.get("x-webhook-timestamp")
        message = timestamp + request_body.decode('utf-8')
        
        # Create HMAC signature
        secret = cashfree_settings.webhook_secret.encode('utf-8')
        expected_signature = base64.b64encode(
            hmac.new(secret, message.encode('utf-8'), hashlib.sha256).digest()
        ).decode('utf-8')
        
        # Compare signatures
        return cf_signature == expected_signature
        
    except Exception as e:
        frappe.log_error(title="Cashfree Webhook Signature Verification Error", message=frappe.get_traceback())
        return False


def get_payment_status(order_id):
    """Get payment status from Cashfree API"""
    try:
        cashfree_settings = frappe.get_doc("Cashfree Settings")
        api_url = f"{cashfree_settings.get_api_url()}/pg/orders/{order_id}"
        
        headers = {
            "x-api-version": "2022-09-01",
            "Content-Type": "application/json",
            "x-client-id": cashfree_settings.api_key,
            "x-client-secret": cashfree_settings.secret_key
        }
        
        response = requests.get(api_url, headers=headers)
        if response.status_code >= 200 and response.status_code < 300:
            return response.json()
        else:
            frappe.log_error(
                title="Cashfree Payment Status Check Failed",
                message=f"Status Code: {response.status_code}, Response: {response.text}"
            )
            return {"status": "ERROR", "message": response.text}
            
    except Exception as e:
        frappe.log_error(title="Cashfree Payment Status Error", message=frappe.get_traceback())
        return {"status": "ERROR", "message": str(e)}


def update_payment_status(payment_request_id, order_details):
    """Update payment request and reference document status"""
    try:
        # Get payment request
        payment_request = frappe.get_doc("Payment Request", payment_request_id)
        
        # Update payment request
        payment_request.db_set("status", "Paid")
        payment_request.db_set("transaction_date", now())
        
        # Create a payment entry
        payment_entry = payment_request.create_payment_entry(
            submit=True,
            payment_id=order_details.get("cf_order_id", order_details.get("order_id")),
            payment_gateway="Cashfree"
        )
        
        # Log the transaction
        payment_log = {
            "payment_request": payment_request_id,
            "payment_entry": payment_entry.name,
            "order_id": order_details.get("order_id"),
            "cf_payment_id": order_details.get("cf_payment_id"),
            "order_amount": order_details.get("order_amount"),
            "order_status": order_details.get("order_status"),
            "payment_method": order_details.get("payment_method"),
            "transaction_time": order_details.get("transaction_time")
        }
        
        frappe.get_doc({
            "doctype": "Integration Request",
            "integration_type": "Payment Request",
            "service_name": "Cashfree",
            "reference_doctype": "Payment Request",
            "reference_docname": payment_request_id,
            "data": json.dumps(payment_log),
            "status": "Completed"
        }).insert(ignore_permissions=True)
        
        # Return payment entry
        return payment_entry
        
    except Exception as e:
        frappe.log_error(title="Cashfree Payment Update Error", message=frappe.get_traceback())
        raise e