import frappe
import json
from frappe import _
from cashfree.api import make_payment

no_cache = True

def get_context(context):
    # Get parameters from query string
    context.no_breadcrumbs = True
    context.show_sidebar = False
    return context

@frappe.whitelist(allow_guest=True)
def process_checkout():
    """Process the checkout and redirect to payment gateway"""
    try:
        # Get form data
        form_data = frappe.form_dict
        
        # Create payment request
        payment_request = make_payment(form_data)
        
        # Redirect to payment URL
        if payment_request.payment_url:
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = payment_request.payment_url
        else:
            frappe.respond_as_web_page(_("Payment Error"),
                _("Could not generate payment URL. Please contact administrator."),
                success=False, http_status_code=501)
    except Exception as e:
        frappe.log_error(title="Checkout Error", message=str(e))
        frappe.respond_as_web_page(_("Payment Error"),
            _("An error occurred during checkout. Please try again."),
            success=False, http_status_code=500)