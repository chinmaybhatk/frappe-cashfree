import frappe
import json
import traceback
from frappe import _
from frappe.utils import get_url

# If your code needs to handle payments, you may need these imports:
from frappe.integrations.utils import create_request_log, create_payment_gateway_controller
from frappe.utils.data import nowdate

@frappe.whitelist(allow_guest=True)
def make_payment():
    try:
        # Instead of trying to get the controller directly from the Payment Gateway doc,
        # Use Frappe's built-in method to create the controller
        payment_gateway = "Cashfree"
        data = frappe.form_dict
        
        # Create a Payment Gateway Controller
        controller = create_payment_gateway_controller(payment_gateway)
        
        # Your payment processing logic
        # For example:
        reference_doc = frappe.get_doc(data.get("reference_doctype"), data.get("reference_docname"))
        
        # Process payment with controller
        response = controller.process_payment(reference_doc, data)
        
        return response
        
    except Exception as e:
        # Proper error logging without the unsupported 'traceback' parameter
        frappe.logger().error(f"Error in make_payment: {str(e)}")
        frappe.logger().error(traceback.format_exc())  # Log the traceback separately
        
        # Create an error response
        return {
            "status": "Error",
            "message": _("An error occurred while processing your payment"),
            "error": str(e)
        }