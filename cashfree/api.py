import frappe
import json
import requests
import traceback
from frappe import _
from frappe.utils import get_url

@frappe.whitelist(allow_guest=True)
def make_payment():
    """Create a new payment order with Cashfree"""
    try:
        # Get payment data from the request
        data = frappe.form_dict if hasattr(frappe, 'form_dict') else {}
        
        # Log incoming data for debugging (limited size)
        frappe.log_error(
            f"Payment request for doctype: {data.get('reference_doctype')}, name: {data.get('reference_docname')}",
            "Cashfree Payment Debug"
        )
        
        # Get reference document info
        reference_doctype = data.get("reference_doctype")
        reference_docname = data.get("reference_docname")
        
        if not reference_doctype or not reference_docname:
            return {
                "status": "Error",
                "message": _("Missing reference document information"),
                "error": "Required fields reference_doctype and reference_docname are missing"
            }
        
        # Get reference document to extract payment details
        try:
            reference_doc = frappe.get_doc(reference_doctype, reference_docname)
        except Exception as doc_error:
            return {
                "status": "Error",
                "message": _("Could not retrieve reference document"),
                "error": str(doc_error)
            }
        
        # Extract payment amount from the reference document
        amount = 0
        amount_field_found = False
        
        # Check for common amount fields
        for field in ['grand_total', 'amount', 'total', 'outstanding_amount']:
            if hasattr(reference_doc, field) and getattr(reference_doc, field) is not None:
                amount = float(getattr(reference_doc, field))
                amount_field_found = True
                break
        
        # If no amount field found, check for amount in request data
        if not amount_field_found and data.get("amount"):
            try:
                amount = float(data.get("amount"))
                amount_field_found = True
            except (ValueError, TypeError):
                pass
        
        if not amount_field_found or amount <= 0:
            return {
                "status": "Error",
                "message": _("Could not determine payment amount"),
                "error": "No valid amount field found in the document or request"
            }
        
        # Get customer details with fallbacks
        customer_name = "Customer"
        customer_email = "customer@example.com"
        customer_phone = "9999999999"
        
        # Try to get from document direct fields first
        for name_field in ['customer_name', 'contact_display', 'customer', 'party_name', 'owner']:
            if hasattr(reference_doc, name_field) and getattr(reference_doc, name_field):
                customer_name = getattr(reference_doc, name_field)
                break
                
        for email_field in ['contact_email', 'email', 'email_id', 'owner']:
            if hasattr(reference_doc, email_field) and getattr(reference_doc, email_field):
                customer_email = getattr(reference_doc, email_field)
                break
                
        for phone_field in ['contact_phone', 'phone', 'mobile_no', 'contact_mobile']:
            if hasattr(reference_doc, phone_field) and getattr(reference_doc, phone_field):
                customer_phone = getattr(reference_doc, phone_field)
                break
        
        # Get currency with fallback
        currency = "INR"
        if hasattr(reference_doc, 'currency') and reference_doc.currency:
            currency = reference_doc.currency
        
        # Get description with fallback
        description = f"Payment for {reference_doctype} {reference_docname}"
        if hasattr(reference_doc, 'description') and reference_doc.description:
            description = reference_doc.description
        
        # Get Cashfree settings
        try:
            cashfree_settings = frappe.get_single("Cashfree Settings")
        except Exception as settings_error:
            return {
                "status": "Error",
                "message": _("Error retrieving Cashfree settings"),
                "error": str(settings_error)
            }
        
        # Check API credentials
        api_key = getattr(cashfree_settings, 'api_key', None)
        if not api_key:
            return {
                "status": "Error",
                "message": _("Cashfree API key not configured"),
                "error": "Please configure your Cashfree API key in Cashfree Settings"
            }
        
        # Get secret key
        try:
            secret_key = cashfree_settings.get_password("secret_key")
            if not secret_key:
                return {
                    "status": "Error",
                    "message": _("Cashfree Secret key not configured"),
                    "error": "Please configure your Cashfree Secret key in Cashfree Settings"
                }
        except Exception:
            return {
                "status": "Error",
                "message": _("Error retrieving Cashfree secret key"),
                "error": "Please check your Cashfree settings"
            }
        
        # Create a unique order ID (ensure no special chars)
        safe_ref_name = ''.join(c for c in reference_docname if c.isalnum())
        order_id = f"CF{safe_ref_name}"[:20]
        
        # Get URLs
        base_url = get_url()
        return_url = data.get("redirect_url") or getattr(cashfree_settings, 'redirect_url', None) or f"{base_url}/api/method/cashfree.api.payment_callback"
        notify_url = getattr(cashfree_settings, 'webhook_url', None) or f"{base_url}/api/method/cashfree.api.webhook_handler"
        
        # Determine API endpoint based on mode
        mode = getattr(cashfree_settings, 'mode', 'TEST')
        api_base_url = "https://sandbox.cashfree.com/pg" if mode == "TEST" else "https://api.cashfree.com/pg"
        
        # Prepare order data
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
                "notify_url": notify_url
            }
        }
        
        # Make API request
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
                timeout=30
            )
        except requests.exceptions.RequestException as req_error:
            return {
                "status": "Error",
                "message": _("Error connecting to payment gateway"),
                "error": str(req_error)
            }
        
        # Log minimal info to avoid truncation
        frappe.log_error(
            f"Cashfree API Response Status: {response.status_code}",
            "Cashfree Payment"
        )
        
        # Process response
        if response.status_code >= 200 and response.status_code < 300:
            try:
                response_data = response.json()
                
                # Log response structure for debugging
                keys = list(response_data.keys())
                frappe.log_error(f"Response keys: {', '.join(keys)}", "Cashfree Response Debug")
                
                # Get payment link or payment session id from response
                # The field name depends on the Cashfree API version
                payment_link = response_data.get("payment_link")
                
                # If no payment_link, check if it's a newer Cashfree API that returns cf_payment_link
                if not payment_link:
                    payment_link = response_data.get("cf_payment_link")
                
                # If still no payment_link, try to construct it from the order_token
                if not payment_link and response_data.get("order_token"):
                    order_token = response_data.get("order_token")
                    if mode == "TEST":
                        payment_link = f"https://payments-test.cashfree.com/order/#/{order_token}"
                    else:
                        payment_link = f"https://payments.cashfree.com/order/#/{order_token}"
                
                # In case payment link isn't available, check for session_id
                # which can be used directly with the Cashfree Checkout JS
                session_id = response_data.get("payment_session_id")
                
                if not payment_link and not session_id:
                    # Log full response for debugging but limited size
                    resp_sample = str(response_data)[:100] + "..." if len(str(response_data)) > 100 else str(response_data)
                    frappe.log_error(f"No payment link in response: {resp_sample}", "Cashfree Response Error")
                    
                    return {
                        "status": "Error",
                        "message": _("Invalid response from payment gateway"),
                        "error": "No payment link received",
                        "response_sample": resp_sample
                    }
                
                # Create payment request
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
                    
                    # Store relevant gateway data
                    gateway_data = {
                        "order_id": order_id,
                    }
                    
                    if payment_link:
                        gateway_data["payment_link"] = payment_link
                    
                    if session_id:
                        gateway_data["session_id"] = session_id
                    
                    # Include order token if available
                    if response_data.get("order_token"):
                        gateway_data["order_token"] = response_data.get("order_token")
                    
                    payment_request.gateway_data = json.dumps(gateway_data)
                    payment_request.flags.ignore_permissions = True
                    payment_request.save()
                except Exception as pr_error:
                    # Just log error but continue - payment might still work
                    frappe.log_error(f"Error creating Payment Request: {str(pr_error)}", "Cashfree Payment Error")
                
                # Return success response with whatever payment info we have
                result = {
                    "status": "Success",
                    "message": _("Payment initiated successfully"),
                    "order_id": order_id,
                    "reference_name": reference_docname
                }
                
                if payment_link:
                    result["payment_url"] = payment_link
                
                if session_id:
                    result["session_id"] = session_id
                
                return result
            except Exception as resp_error:
                # Log the error for debugging
                frappe.log_error(f"Error processing Cashfree response: {str(resp_error)}", "Cashfree Response Error")
                
                # Try to provide a usable response even with error
                try:
                    # Extract raw order ID from response if possible
                    order_info = response.json()
                    if isinstance(order_info, dict) and order_info.get("order_id"):
                        # Create a fallback payment request
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
                        payment_request.gateway_data = json.dumps({"order_id": order_id})
                        payment_request.flags.ignore_permissions = True
                        payment_request.save()
                        
                        # Provide a generic payment URL based on order_id
                        payment_url = f"https://payments.cashfree.com/order/?pid={order_info.get('order_id')}"
                        
                        return {
                            "status": "Success",
                            "message": _("Payment initiated successfully (fallback mode)"),
                            "payment_url": payment_url,
                            "order_id": order_id,
                            "reference_name": reference_docname
                        }
                except:
                    pass
                
                return {
                    "status": "Error",
                    "message": _("Error processing payment gateway response"),
                    "error": str(resp_error)
                }
        else:
            # Handle error response
            error_msg = response.text[:100] if response.text else f"HTTP {response.status_code}"
            frappe.log_error(f"Cashfree error: {error_msg}", "Cashfree Payment Error")
            
            return {
                "status": "Error",
                "message": _("Failed to initiate payment"),
                "error": f"Status code: {response.status_code}",
                "details": error_msg
            }
        
    except Exception as e:
        # Log the error
        frappe.log_error(f"Critical error: {str(e)}", "Cashfree Payment Error")
        
        # Return error response
        return {
            "status": "Error",
            "message": _("An error occurred while processing your payment"),
            "error": str(e)
        }

# The rest of the callbacks and webhook handling functions remain the same