import frappe
import json
import hmac
import hashlib
import requests
import traceback
from frappe import _
from frappe.utils import get_url, cint

@frappe.whitelist(allow_guest=True)
def make_payment():
    """Create a new payment order with Cashfree"""
    try:
        # Get payment data from the request - safely handle potential None
        data = frappe.form_dict if hasattr(frappe, 'form_dict') else {}
        
        # Basic logging without JSON serialization to avoid errors
        frappe.log_error(
            f"make_payment called with data type: {type(data).__name__}", 
            "Cashfree Payment Debug"
        )
        
        # Check if we have the necessary data - safely access dictionary
        reference_doctype = data.get("reference_doctype") if isinstance(data, dict) else None
        reference_docname = data.get("reference_docname") if isinstance(data, dict) else None
        
        # Log the reference document info
        frappe.log_error(
            f"Reference document: {reference_doctype} {reference_docname}",
            "Cashfree Payment Debug"
        )
        
        if not reference_doctype or not reference_docname:
            return {
                "status": "Error",
                "message": _("Missing reference document information"),
                "error": "Required fields reference_doctype and reference_docname are missing"
            }
        
        # Get reference document to extract payment details
        try:
            reference_doc = frappe.get_doc(reference_doctype, reference_docname)
            if not reference_doc:
                return {
                    "status": "Error",
                    "message": _("Could not retrieve reference document"),
                    "error": f"Document {reference_doctype} {reference_docname} not found"
                }
        except Exception as doc_error:
            return {
                "status": "Error",
                "message": _("Could not retrieve reference document"),
                "error": str(doc_error)
            }
        
        # Extract payment amount from the reference document - safely check attributes
        amount = 0
        amount_field_found = False
        
        # Check for common amount fields
        for field in ['grand_total', 'amount', 'total', 'outstanding_amount', 'base_grand_total']:
            if hasattr(reference_doc, field) and getattr(reference_doc, field) is not None:
                amount = float(getattr(reference_doc, field))
                amount_field_found = True
                frappe.log_error(f"Found amount {amount} in field '{field}'", "Cashfree Payment Debug")
                break
        
        # If no amount field found, check for custom amount passed directly
        if not amount_field_found and isinstance(data, dict) and data.get("amount"):
            try:
                amount = float(data.get("amount"))
                amount_field_found = True
                frappe.log_error(f"Using provided amount {amount}", "Cashfree Payment Debug")
            except (ValueError, TypeError):
                frappe.log_error(f"Invalid amount format: {data.get('amount')}", "Cashfree Payment Debug")
        
        if not amount_field_found or amount <= 0:
            return {
                "status": "Error",
                "message": _("Could not determine payment amount"),
                "error": "No valid amount field found in the document or request"
            }
        
        # Get customer details - default empty strings
        customer_name = ""
        customer_email = ""
        customer_phone = ""
        
        # Try to get customer info from the document itself first (direct fields)
        # This avoids unnecessary DB queries for simple cases
        for name_field in ['customer_name', 'contact_display', 'customer', 'party_name', 'title', 'name']:
            if hasattr(reference_doc, name_field) and getattr(reference_doc, name_field):
                customer_name = getattr(reference_doc, name_field)
                break
                
        for email_field in ['contact_email', 'email', 'email_id', 'owner']:
            if hasattr(reference_doc, email_field) and getattr(reference_doc, email_field):
                customer_email = getattr(reference_doc, email_field)
                break
                
        for phone_field in ['contact_phone', 'phone', 'mobile_no', 'phone_no']:
            if hasattr(reference_doc, phone_field) and getattr(reference_doc, phone_field):
                customer_phone = getattr(reference_doc, phone_field)
                break
        
        # If we still don't have customer info and there's a customer field,
        # try to get from Customer document - but only if we need to
        if (not customer_name or not customer_email or not customer_phone) and hasattr(reference_doc, 'customer') and reference_doc.customer:
            try:
                # Get customer document
                customer_doc = frappe.get_doc("Customer", reference_doc.customer)
                
                # If we still need the name
                if not customer_name and hasattr(customer_doc, 'customer_name') and customer_doc.customer_name:
                    customer_name = customer_doc.customer_name
                
                # Try to get contact details, but only if we need them
                if not customer_email or not customer_phone:
                    contact_name = None
                    # Get primary contact
                    links = frappe.get_all(
                        "Dynamic Link",
                        filters={
                            "link_doctype": "Customer",
                            "link_name": reference_doc.customer,
                            "parenttype": "Contact"
                        },
                        fields=["parent"],
                        limit=1
                    )
                    
                    if links and isinstance(links, list) and len(links) > 0 and isinstance(links[0], dict):
                        contact_name = links[0].get('parent')
                    
                    if contact_name:
                        contact = frappe.get_doc("Contact", contact_name)
                        
                        # Get email if we need it
                        if not customer_email and hasattr(contact, 'email_ids') and isinstance(contact.email_ids, list) and len(contact.email_ids) > 0:
                            for email_row in contact.email_ids:
                                if hasattr(email_row, 'email_id') and email_row.email_id:
                                    customer_email = email_row.email_id
                                    break
                        
                        # Get phone if we need it
                        if not customer_phone and hasattr(contact, 'phone_nos') and isinstance(contact.phone_nos, list) and len(contact.phone_nos) > 0:
                            for phone_row in contact.phone_nos:
                                if hasattr(phone_row, 'phone') and phone_row.phone:
                                    customer_phone = phone_row.phone
                                    break
            except Exception as customer_error:
                # Just log the error and continue with defaults
                frappe.log_error(f"Error getting customer details: {str(customer_error)}", "Cashfree Payment Debug")
        
        # Provide defaults if still missing
        if not customer_name:
            customer_name = "Customer"
        if not customer_email:
            customer_email = "customer@example.com"
        if not customer_phone:
            customer_phone = "9999999999"
        
        # Get currency safely
        currency = "INR"  # Default
        if hasattr(reference_doc, 'currency') and reference_doc.currency:
            currency = reference_doc.currency
        
        # Get description
        description = f"Payment for {reference_doctype} {reference_docname}"
        if hasattr(reference_doc, 'description') and reference_doc.description:
            description = reference_doc.description
        
        # Get Cashfree settings
        try:
            cashfree_settings = frappe.get_single("Cashfree Settings")
            if not cashfree_settings:
                return {
                    "status": "Error",
                    "message": _("Cashfree Settings not found"),
                    "error": "Please configure Cashfree Settings first"
                }
        except Exception as settings_error:
            return {
                "status": "Error",
                "message": _("Error retrieving Cashfree settings"),
                "error": str(settings_error)
            }
        
        # Check for required settings
        api_key = getattr(cashfree_settings, 'api_key', None)
        if not api_key:
            return {
                "status": "Error",
                "message": _("Cashfree API key not configured"),
                "error": "Please configure your Cashfree API key in Cashfree Settings"
            }
        
        # Safely get secret key
        try:
            # The get_password method might throw an error
            secret_key = cashfree_settings.get_password("secret_key")
            if not secret_key:
                return {
                    "status": "Error",
                    "message": _("Cashfree Secret key not configured"),
                    "error": "Please configure your Cashfree Secret key in Cashfree Settings"
                }
        except Exception as secret_error:
            return {
                "status": "Error",
                "message": _("Error retrieving Cashfree secret key"),
                "error": str(secret_error)
            }
        
        # Create a unique order ID (ensure no special chars)
        safe_ref_name = ''.join(c for c in reference_docname if c.isalnum())
        order_id = f"CF{safe_ref_name}"[:20]
        
        # Create return URLs
        base_url = get_url()
        
        # Safely get redirect URL with fallbacks
        redirect_url = None
        if isinstance(data, dict):
            redirect_url = data.get("redirect_url")
        
        if not redirect_url and hasattr(cashfree_settings, 'redirect_url'):
            redirect_url = cashfree_settings.redirect_url
            
        return_url = redirect_url or f"{base_url}/api/method/cashfree.api.payment_callback"
        
        # Safely get webhook URL
        webhook_url = None
        if hasattr(cashfree_settings, 'webhook_url'):
            webhook_url = cashfree_settings.webhook_url
            
        notify_url = webhook_url or f"{base_url}/api/method/cashfree.api.webhook_handler"
        
        # Determine API endpoint based on mode
        mode = getattr(cashfree_settings, 'mode', 'TEST')
        api_base_url = "https://sandbox.cashfree.com/pg" if mode == "TEST" else "https://api.cashfree.com/pg"
        
        # Prepare the order request
        # First, sanitize any values that might cause issues
        safe_customer_id = ''.join(c for c in reference_docname if c.isalnum())[:15]
        
        order_data = {
            "order_id": order_id,
            "order_amount": float(amount),
            "order_currency": currency,
            "order_note": description,
            "customer_details": {
                "customer_id": f"CUST{safe_customer_id}",
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone
            },
            "order_meta": {
                "return_url": f"{return_url}?order_id={order_id}",
                "notify_url": notify_url,
                "payment_methods": ""  # Leave empty for all payment methods
            }
        }
        
        # Log the request data without risking JSON serialization errors
        frappe.log_error(
            f"Cashfree order data: order_id={order_id}, amount={amount}, currency={currency}",
            "Cashfree Payment Debug"
        )
        
        # Make the API request to Cashfree
        headers = {
            "x-api-version": "2022-09-01",
            "x-client-id": api_key,
            "x-client-secret": secret_key,
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{api_base_url}/orders", 
                headers=headers,
                json=order_data,
                timeout=30  # Add timeout to prevent hanging
            )
        except requests.exceptions.RequestException as req_error:
            return {
                "status": "Error",
                "message": _("Error connecting to payment gateway"),
                "error": str(req_error)
            }
        
        # Create request log with minimal risk of serialization errors
        frappe.log_error(
            f"Cashfree API Response: Status={response.status_code}, Text={response.text[:500]}",
            "Cashfree Payment Log"
        )
        
        # Process response
        if response.status_code >= 200 and response.status_code < 300:
            try:
                response_data = response.json()
                
                # Check if payment_link exists in the response
                payment_link = response_data.get("payment_link")
                if not payment_link:
                    return {
                        "status": "Error",
                        "message": _("Invalid response from payment gateway"),
                        "error": "No payment link received from Cashfree",
                        "response": response_data
                    }
                
                # Save payment details for future reference
                try:
                    payment_request = frappe.new_doc("Payment Request")
                    payment_request.payment_gateway = "Cashfree"
                    payment_request.payment_gateway_account = "Cashfree"
                    payment_request.payment_request_type = "Outward"
                    payment_request.reference_doctype = reference_doctype
                    payment_request.reference_name = reference_docname
                    payment_request.grand_total = amount
                    payment_request.currency = currency
                    payment_request.email_to = customer_email
                    payment_request.subject = f"Payment Request for {reference_docname}"
                    payment_request.message = description
                    payment_request.status = "Initiated"
                    
                    # Safely store gateway data
                    gateway_data = json.dumps({
                        "order_id": order_id,
                        "payment_link": payment_link
                    })
                    payment_request.gateway_data = gateway_data
                    
                    payment_request.flags.ignore_permissions = True
                    payment_request.save()
                except Exception as pr_error:
                    # Log error but continue - the payment might still work
                    frappe.log_error(f"Error creating Payment Request: {str(pr_error)}", "Cashfree Payment Error")
                
                return {
                    "status": "Success",
                    "message": _("Payment initiated successfully"),
                    "payment_url": payment_link,
                    "order_id": order_id,
                    "reference_name": reference_docname
                }
            except Exception as resp_error:
                return {
                    "status": "Error",
                    "message": _("Error processing payment gateway response"),
                    "error": str(resp_error),
                    "response_text": response.text
                }
        else:
            error_msg = response.text
            
            return {
                "status": "Error",
                "message": _("Failed to initiate payment"),
                "error": error_msg,
                "details": {
                    "status_code": response.status_code
                }
            }
        
    except Exception as e:
        # Log the error
        frappe.log_error(traceback.format_exc(), "Cashfree Payment Critical Error")
        
        # Return error response
        return {
            "status": "Error",
            "message": _("An error occurred while processing your payment"),
            "error": str(e)
        }

# The rest of the functions (payment_callback, webhook_handler, etc.) would follow
# but for now we're focusing on fixing the make_payment function