# cashfree/controller.py
import frappe
import json
import requests
from frappe import _

class CashfreeController:
    def __init__(self, gateway_settings, gateway_controller):
        self.settings = frappe.get_doc("Cashfree Settings")
        self.gateway_settings = gateway_settings
        self.gateway_controller = gateway_controller
    
    def validate_transaction_currency(self, currency):
        if currency not in ["INR"]:
            frappe.throw(_("Please select Indian Rupees (INR) as currency"))
        return True
    
    def get_payment_url(self, **kwargs):
        """Create Cashfree order and return payment URL"""
        try:
            # Create an order ID
            order_id = "CF-" + kwargs.get("reference_docname") + "-" + frappe.utils.random_string(5)
            
            # Get customer details
            customer_email = kwargs.get("payer_email") or frappe.session.user
            customer_name = kwargs.get("payer_name") or frappe.db.get_value("User", frappe.session.user, "full_name")
            customer_phone = frappe.db.get_value("User", frappe.session.user, "mobile_no") or "9999999999"
            
            # Create customer details object
            customer_details = {
                "customer_id": frappe.session.user,
                "customer_name": customer_name,
                "customer_email": customer_email,
                "customer_phone": customer_phone
            }
            
            # Prepare order data
            site_url = frappe.utils.get_url()
            return_url = f"{site_url}/api/method/cashfree.controller.handle_payment_return"
            
            order_data = {
                "order_id": order_id,
                "order_amount": float(kwargs.get("amount")),
                "order_currency": kwargs.get("currency"),
                "customer_details": customer_details,
                "order_meta": {
                    "reference_doctype": kwargs.get("reference_doctype"),
                    "reference_docname": kwargs.get("reference_docname"),
                    "payment_reference": kwargs.get("reference_docname")
                },
                "order_note": f"Payment for {kwargs.get('reference_doctype')} {kwargs.get('reference_docname')}",
                "order_tags": {
                    "source": "erpnext",
                    "return_url": return_url
                }
            }
            
            # Select API endpoint based on mode
            if self.settings.mode == "TEST":
                api_url = "https://sandbox.cashfree.com/pg/orders"
            else:
                api_url = "https://api.cashfree.com/pg/orders"
            
            # Prepare headers
            headers = {
                "x-api-version": "2022-09-01",
                "x-client-id": self.settings.api_key,
                "x-client-secret": self.settings.get_password("secret_key"),
                "Content-Type": "application/json"
            }
            
            # Make API request
            response = requests.post(
                api_url,
                headers=headers,
                json=order_data
            )
            
            # Process response
            if response.status_code == 200:
                result = response.json()
                
                # Store order ID for verification
                frappe.db.set_value(
                    "Payment Request",
                    kwargs.get("order_id"),
                    "transaction_reference",
                    order_id
                )
                
                return result.get("payment_link")
            else:
                frappe.log_error(
                    title="Cashfree Order Creation Failed",
                    message=f"Status Code: {response.status_code}, Response: {response.text}"
                )
                return None
                
        except Exception as e:
            frappe.log_error(title="Cashfree Payment Error", message=str(e))
            return None
    
    def on_payment_authorized(self, status=None, order_id=None):
        """Handle payment success"""
        if not order_id:
            frappe.log_error("No order ID provided for payment verification", "Cashfree")
            return {
                "status": "Failed",
                "message": "No order ID provided"
            }
        
        try:
            # Verify payment status with Cashfree
            if self.settings.mode == "TEST":
                api_url = f"https://sandbox.cashfree.com/pg/orders/{order_id}"
            else:
                api_url = f"https://api.cashfree.com/pg/orders/{order_id}"
            
            headers = {
                "x-api-version": "2022-09-01",
                "x-client-id": self.settings.api_key,
                "x-client-secret": self.settings.get_password("secret_key"),
                "Content-Type": "application/json"
            }
            
            response = requests.get(api_url, headers=headers)
            
            if response.status_code == 200:
                result = response.json()
                
                # Check payment status
                if result.get("order_status") == "PAID":
                    payment_status = "Completed"
                    return {
                        "status": "Completed",
                        "data": result
                    }
                else:
                    return {
                        "status": "Failed",
                        "data": result
                    }
            else:
                return {
                    "status": "Failed",
                    "message": f"Failed to verify payment: {response.text}"
                }
                
        except Exception as e:
            frappe.log_error(title="Cashfree Payment Verification Error", message=str(e))
            return {
                "status": "Failed",
                "message": str(e)
            }


@frappe.whitelist(allow_guest=True)
def handle_payment_return():
    """Handle return from Cashfree payment page"""
    try:
        # Extract order_id
        order_id = frappe.form_dict.get("order_id")
        
        if not order_id:
            # Try to extract from other parameters
            for key in frappe.form_dict:
                if key.startswith("CF-"):
                    order_id = key
                    break
        
        if not order_id:
            frappe.log_error("No order ID found in return parameters", "Cashfree Return Error")
            frappe.redirect_to_message(
                _("Payment Failed"),
                _("We couldn't verify your payment. Please try again or contact support.")
            )
            return
            
        # Get Cashfree settings
        settings = frappe.get_doc("Cashfree Settings")
        
        # Verify payment with Cashfree
        if settings.mode == "TEST":
            api_url = f"https://sandbox.cashfree.com/pg/orders/{order_id}"
        else:
            api_url = f"https://api.cashfree.com/pg/orders/{order_id}"
            
        headers = {
            "x-api-version": "2022-09-01",
            "x-client-id": settings.api_key,
            "x-client-secret": settings.get_password("secret_key"),
            "Content-Type": "application/json"
        }
        
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            
            # Extract reference
            order_meta = result.get("order_meta", {})
            reference_doctype = order_meta.get("reference_doctype")
            reference_docname = order_meta.get("reference_docname")
            
            # Find payment request
            payment_requests = frappe.get_all(
                "Payment Request",
                filters={
                    "reference_doctype": reference_doctype,
                    "reference_name": reference_docname,
                    "docstatus": 1,
                    "status": ["!=", "Paid"]
                },
                fields=["name"],
                order_by="creation desc",
                limit=1
            )
            
            if payment_requests:
                payment_request = frappe.get_doc("Payment Request", payment_requests[0].name)
                
                # Update status based on payment status
                if result.get("order_status") == "PAID":
                    # Mark as paid
                    payment_request.run_method("set_as_paid")
                    
                    # Redirect to success page
                    frappe.local.response["type"] = "redirect"
                    frappe.local.response["location"] = f"/{reference_doctype.lower().replace(' ', '-')}/{reference_docname}"
                else:
                    # Redirect to failure page
                    frappe.local.response["type"] = "redirect"
                    frappe.local.response["location"] = f"/{reference_doctype.lower().replace(' ', '-')}/{reference_docname}?payment_failed=1"
            else:
                # Redirect to home
                frappe.local.response["type"] = "redirect"
                frappe.local.response["location"] = "/"
        else:
            # Redirect to home with error
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = "/?payment_error=1"
            
    except Exception as e:
        frappe.log_error(title="Cashfree Return Handler Error", message=str(e))
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/?payment_error=1"