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
            f"Cashfree API Status: {response.status_code}",
            "Cashfree Payment"
        )
        
        # Process response
        if response.status_code >= 200 and response.status_code < 300:
            try:
                response_data = response.json()
                
                # Get payment link from response
                payment_link = response_data.get("payment_link")
                if not payment_link:
                    return {
                        "status": "Error",
                        "message": _("Invalid response from payment gateway"),
                        "error": "No payment link received"
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
                    
                    # Store minimal gateway data to avoid issues
                    payment_request.gateway_data = json.dumps({
                        "order_id": order_id,
                        "payment_link": payment_link
                    })
                    
                    payment_request.flags.ignore_permissions = True
                    payment_request.save()
                except Exception as pr_error:
                    # Just log error but continue - payment might still work
                    frappe.log_error(f"Error creating Payment Request: {str(pr_error)}", "Cashfree Payment Error")
                
                # Return success with payment URL
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
                    "error": str(resp_error)
                }
        else:
            # Handle error response
            return {
                "status": "Error",
                "message": _("Failed to initiate payment"),
                "error": f"Status code: {response.status_code}"
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

@frappe.whitelist(allow_guest=True)
def payment_callback():
    """Handle the redirect after payment completion"""
    try:
        # Get callback data
        data = frappe.form_dict
        order_id = data.get("order_id")
        
        if not order_id:
            frappe.throw(_("No order ID received in callback"))
        
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
        
        # Verify payment status
        payment_status = verify_payment(order_id)
        
        if payment_status.get("order_status") == "PAID":
            # Payment successful
            payment_request.status = "Paid"
            payment_request.flags.ignore_permissions = True
            payment_request.save()
            
            frappe.msgprint(_("Payment completed successfully!"))
            
            # Redirect to success page or back to the document
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
        frappe.log_error(f"Error in payment_callback: {str(e)}", "Cashfree Callback Error")
        
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
        
        # Process based on event type
        if event_type == "ORDER_PAID":
            # Payment successful
            update_payment_status(order_id, "Paid")
        elif event_type == "PAYMENT_FAILED":
            # Payment failed
            update_payment_status(order_id, "Failed")
        
        return {"status": "Success"}
        
    except Exception as e:
        frappe.log_error(f"Error in webhook_handler: {str(e)}", "Cashfree Webhook Error")
        
        return {
            "status": "Error",
            "message": str(e)
        }

def verify_payment(order_id):
    """Verify the payment status with Cashfree"""
    try:
        cashfree_settings = frappe.get_single("Cashfree Settings")
        
        # Determine API endpoint based on mode
        api_base_url = "https://sandbox.cashfree.com/pg" if cashfree_settings.mode == "TEST" else "https://api.cashfree.com/pg"
        
        # Make the API request to Cashfree
        headers = {
            "x-api-version": "2022-09-01",
            "x-client-id": cashfree_settings.api_key,
            "x-client-secret": cashfree_settings.get_password("secret_key"),
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{api_base_url}/orders/{order_id}",
            headers=headers
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            return response.json()
        else:
            frappe.log_error(f"Payment verification failed: Status {response.status_code}", "Cashfree Payment Error")
            return {"order_status": "ERROR"}
        
    except Exception as e:
        frappe.log_error(f"Error verifying payment: {str(e)}", "Cashfree Payment Error")
        return {"order_status": "ERROR"}

def update_payment_status(order_id, status):
    """Update payment request status"""
    payment_requests = frappe.get_all(
        "Payment Request",
        filters={"gateway_data": ["like", f"%{order_id}%"]},
        fields=["name"]
    )
    
    if not payment_requests:
        frappe.log_error(f"No payment request found for order {order_id}", "Cashfree Status Update Error")
        return
    
    try:
        payment_request = frappe.get_doc("Payment Request", payment_requests[0].name)
        payment_request.status = status
        payment_request.flags.ignore_permissions = True
        payment_request.save()
        
        # If payment successful, create payment entry if needed
        if status == "Paid":
            reference_doctype = payment_request.reference_doctype
            reference_name = payment_request.reference_name
            
            # Update the reference document if appropriate
            # This depends on your specific workflow
            
            frappe.log_error(f"Payment for {reference_doctype} {reference_name} marked as {status}", "Cashfree Payment Success")
    except Exception as e:
        frappe.log_error(f"Error updating payment status: {str(e)}", "Cashfree Status Update Error")