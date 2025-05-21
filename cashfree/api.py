# Update cashfree/api.py
import frappe
import requests
import json
from frappe import _
from frappe.utils import get_url, cint

@frappe.whitelist(allow_guest=True)
def create_cashfree_order(amount=None, order_id=None, customer_details=None, order_meta=None, reference_doctype=None, reference_name=None):
    """Create a Cashfree order and return the payment link"""
    try:
        # Get data from form_dict if not provided
        if amount is None:
            amount = frappe.form_dict.get("amount")
        if reference_doctype is None:
            reference_doctype = frappe.form_dict.get("reference_doctype")
        if reference_name is None:
            reference_name = frappe.form_dict.get("reference_name")
            
        # Convert to float and ensure it's not None
        if amount:
            amount = float(amount)
        else:
            amount = 100  # Set a default amount if not provided
            
        settings = frappe.get_doc("Cashfree Settings")
        
        # Generate a unique order ID if not provided
        if not order_id:
            # Use reference doc if available or generate a hash
            if reference_doctype and reference_name:
                order_id = f"{reference_doctype}-{reference_name}-{frappe.utils.random_string(5)}"
            else:
                order_id = f"CF-{frappe.utils.random_string(10)}"
        
        # Get customer details
        if not customer_details:
            customer_details = {
                "customer_id": frappe.session.user,
                "customer_name": frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user.split('@')[0],
                "customer_email": frappe.session.user,
                "customer_phone": frappe.db.get_value("User", frappe.session.user, "mobile_no") or "9999999999"
            }
        
        # Prepare order data
        order_data = {
            "order_id": order_id,
            "order_amount": float(amount),
            "order_currency": "INR",
            "customer_details": customer_details,
            "order_meta": order_meta or {},
            "order_note": f"Payment for {reference_doctype or 'order'} {reference_name or ''}",
            "order_tags": {"source": "frappe"}
        }
        
        # Add return URLs
        site_url = frappe.utils.get_url()
        order_data["order_tags"].update({
            "return_url": f"{site_url}/api/method/cashfree.api.handle_return?order_id={order_id}"
        })
        
        # API endpoints
        if settings.mode == "TEST":
            api_url = "https://sandbox.cashfree.com/pg/orders"
        else:
            api_url = "https://api.cashfree.com/pg/orders"
        
        # Make API request to create order
        headers = {
            "x-api-version": "2022-09-01",
            "x-client-id": settings.api_key,
            "x-client-secret": settings.get_password("secret_key"),
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            api_url, 
            headers=headers,
            json=order_data
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Log order creation for debugging
            frappe.logger().debug(f"Cashfree order created: {result}")
            
            # Create a Payment Request record
            payment_request = frappe.new_doc("Payment Request")
            
            # Set reference document if provided
            if reference_doctype and reference_name:
                payment_request.reference_doctype = reference_doctype
                payment_request.reference_name = reference_name
            
            payment_request.payment_request_type = "Inward"
            payment_request.currency = "INR"
            payment_request.grand_total = amount
            payment_request.payment_gateway = "Cashfree"
            payment_request.payment_gateway_account = frappe.db.get_value(
                "Payment Gateway Account",
                {"payment_gateway": "Cashfree", "currency": "INR"},
                "name"
            )
            payment_request.email_to = customer_details.get("customer_email")
            payment_request.subject = _("Payment Request for Order {0}").format(order_id)
            payment_request.message = _("Please click the link below to make your payment")
            
            # Store Cashfree order ID in payment request as a custom field
            # If the custom field doesn't exist, we'll attach it as a property
            payment_request.order_id = order_id
            payment_request.payment_url = result.get("payment_link")
            
            # Save and submit the payment request
            payment_request.save(ignore_permissions=True)
            payment_request.submit()
            
            # Return the payment link for redirection
            return {
                "success": True,
                "payment_link": result.get("payment_link"),
                "order_id": order_id,
                "payment_request": payment_request.name
            }
        else:
            frappe.log_error(
                title="Cashfree Order Creation Failed",
                message=f"Status Code: {response.status_code}, Response: {response.text}"
            )
            return {
                "success": False,
                "message": f"Failed to create Cashfree order: {response.text}"
            }
            
    except Exception as e:
        frappe.log_error(title="Cashfree Payment Error", message=str(e))
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def handle_return():
    """Handle return from Cashfree payment page"""
    try:
        order_id = frappe.form_dict.get("order_id")
        
        # Verify the payment status
        settings = frappe.get_doc("Cashfree Settings")
        
        # API endpoints
        if settings.mode == "TEST":
            api_url = f"https://sandbox.cashfree.com/pg/orders/{order_id}"
        else:
            api_url = f"https://api.cashfree.com/pg/orders/{order_id}"
        
        # Make API request to get order status
        headers = {
            "x-api-version": "2022-09-01",
            "x-client-id": settings.api_key,
            "x-client-secret": settings.get_password("secret_key"),
            "Content-Type": "application/json"
        }
        
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            
            # Get payment request by order_id (stored as a custom field or property)
            payment_request_name = frappe.db.get_value(
                "Payment Request", 
                {"order_id": order_id}, 
                "name"
            )
            
            if not payment_request_name:
                # Try a different approach if the custom field doesn't exist
                # This is a fallback and may not work in all cases
                payment_requests = frappe.get_all(
                    "Payment Request", 
                    filters={"status": ["in", ["Initiated", "Requested"]]},
                    fields=["name", "creation"],
                    order_by="creation desc",
                    limit=5
                )
                
                if payment_requests:
                    payment_request_name = payment_requests[0].name
            
            if payment_request_name:
                payment_request = frappe.get_doc("Payment Request", payment_request_name)
                
                # Update payment request status based on order status
                if result.get("order_status") == "PAID":
                    # Set as paid
                    payment_request.status = "Paid"
                    payment_request.save(ignore_permissions=True)
                    
                    # Create payment entry if needed
                    if hasattr(payment_request, 'set_as_paid'):
                        payment_entry = payment_request.set_as_paid()
                    
                    # Redirect to success page
                    success_url = "/payment-success"
                    if payment_request.reference_doctype and payment_request.reference_name:
                        success_url += f"?reference_doctype={payment_request.reference_doctype}&reference_name={payment_request.reference_name}"
                    
                    frappe.local.response["type"] = "redirect"
                    frappe.local.response["location"] = success_url
                else:
                    # Set as failed
                    payment_request.status = "Failed"
                    payment_request.save(ignore_permissions=True)
                    
                    # Redirect to failure page
                    frappe.local.response["type"] = "redirect"
                    frappe.local.response["location"] = "/payment-failed?order_id=" + order_id
            else:
                # Redirect to error page
                frappe.local.response["type"] = "redirect"
                frappe.local.response["location"] = "/payment-error?order_id=" + order_id
        else:
            # Redirect to error page
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/payment-error?order_id=" + order_id
            
    except Exception as e:
        frappe.log_error(title="Cashfree Return Handler Error", message=str(e))
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-error"


@frappe.whitelist(allow_guest=True)
def redirect_to_payment():
    """Create order and redirect to Cashfree payment page"""
    try:
        amount = frappe.form_dict.get("amount")
        reference_doctype = frappe.form_dict.get("reference_doctype")
        reference_name = frappe.form_dict.get("reference_name")
        
        # Create order
        result = create_cashfree_order(
            amount=amount,
            reference_doctype=reference_doctype,
            reference_name=reference_name
        )
        
        if result.get("success") and result.get("payment_link"):
            # Redirect to payment page
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = result.get("payment_link")
        else:
            # Show error
            frappe.respond_as_web_page(
                _("Payment Error"),
                _("Unable to initiate payment. Please try again later."),
                success=False,
                http_status_code=500
            )
    except Exception as e:
        frappe.log_error(title="Cashfree Redirect Error", message=str(e))
        frappe.respond_as_web_page(
            _("Payment Error"),
            _("An error occurred during payment initiation. Please try again."),
            success=False,
            http_status_code=500
        )


# Keep the original make_payment function for backward compatibility
# But modify it to use the new redirect approach
@frappe.whitelist(allow_guest=True)
def make_payment(checkout_data=None):
    """Legacy function for backward compatibility"""
    try:
        # Extract data
        if isinstance(checkout_data, str):
            checkout_data = json.loads(checkout_data)
        elif checkout_data is None:
            checkout_data = frappe.form_dict
            
        # Extract key values
        amount = checkout_data.get("amount")
        reference_doctype = checkout_data.get("reference_doctype")
        reference_name = checkout_data.get("reference_name")
        
        # Create cashfree order using the new method
        result = create_cashfree_order(
            amount=amount,
            reference_doctype=reference_doctype,
            reference_name=reference_name
        )
        
        # Check if we should redirect or return JSON
        is_api_call = frappe.local.request.path.startswith('/api/')
        
        if result.get("success"):
            if is_api_call:
                # Return JSON response for API calls
                return result
            else:
                # Redirect for web requests
                frappe.local.response["type"] = "redirect"
                frappe.local.response["location"] = result.get("payment_link")
                return
        else:
            # Return error response
            if is_api_call:
                return result
            else:
                frappe.respond_as_web_page(
                    _("Payment Error"),
                    _("Unable to initiate payment. Please try again later."),
                    success=False,
                    http_status_code=500
                )
                
    except Exception as e:
        frappe.log_error(title="Legacy Payment Function Error", message=str(e))
        raise