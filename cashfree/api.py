import frappe
import json
import traceback
from frappe import _
from frappe.utils import get_url
from frappe.integrations.utils import create_request_log

@frappe.whitelist(allow_guest=True)
def make_payment():
    try:
        # Get payment data from the request
        data = frappe.form_dict
        
        # Get Cashfree payment gateway settings
        cashfree_settings = frappe.get_doc("Cashfree Settings")
        if not cashfree_settings:
            frappe.throw(_("Cashfree Settings not found. Please configure Cashfree Settings first."))
        
        # Get reference document
        reference_doctype = data.get("reference_doctype")
        reference_docname = data.get("reference_docname")
        
        if not reference_doctype or not reference_docname:
            frappe.throw(_("Missing reference document details"))
        
        reference_doc = frappe.get_doc(reference_doctype, reference_docname)
        
        # Create payment request log
        request_log = create_request_log(data, "Host", "Cashfree")
        
        # Process payment
        # Here you would implement your Cashfree payment processing logic
        # For example:
        payment_data = {
            "appId": cashfree_settings.app_id,
            "orderId": reference_doc.name,
            "orderAmount": data.get("amount"),
            "orderCurrency": data.get("currency", "INR"),
            "customerName": data.get("payer_name"),
            "customerEmail": data.get("payer_email"),
            "customerPhone": data.get("payer_phone"),
            "returnUrl": get_url(f"/api/method/cashfree.api.payment_callback?order_id={reference_doc.name}")
        }
        
        # Here you would typically make API calls to Cashfree
        # This is a placeholder for your actual implementation
        
        return {
            "status": "Success",
            "message": _("Payment initiated"),
            "payment_url": "YOUR_PAYMENT_URL",  # Replace with actual URL from Cashfree
            "reference_name": reference_docname
        }
        
    except Exception as e:
        # Proper error logging
        frappe.logger().error(f"Error in make_payment: {str(e)}")
        frappe.logger().error(traceback.format_exc())
        
        # Return error response
        return {
            "status": "Error",
            "message": _("An error occurred while processing your payment"),
            "error": str(e)
        }

@frappe.whitelist(allow_guest=True)
def payment_callback():
    """Handle the payment callback from Cashfree"""
    try:
        data = frappe.request.args
        
        # Verify the payment
        # Implement your verification logic here
        
        # Update the reference document
        order_id = data.get("order_id")
        if order_id:
            # Find the reference document
            # Update its status based on payment response
            pass
        
        return {
            "status": "Success",
            "message": _("Payment processed successfully")
        }
        
    except Exception as e:
        frappe.logger().error(f"Error in payment_callback: {str(e)}")
        frappe.logger().error(traceback.format_exc())
        
        return {
            "status": "Error",
            "message": _("Error processing payment callback"),
            "error": str(e)
        }