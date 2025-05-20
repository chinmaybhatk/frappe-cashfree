# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from .. import __version__ as app_version

app_name = "cashfree"
app_title = "Cashfree Integration"
app_publisher = "walue.biz"
app_description = "Cashfree Payment Gateway Integration for Frappe"
app_icon = "octicon octicon-credit-card"
app_color = "#25C4B9"
app_email = "chinmaybhatk@gmail.com"
app_license = "MIT"

# Hooks
fixtures = [
    {"dt": "Custom Field", "filters": [["fieldname", "in", ["cashfree_settings"]]]},
    {"dt": "Payment Gateway"}
]

# Doctype hooks
doctype_js = {
    "Payment Request": "public/js/payment_request.js"
}

# Include in global search
global_search_doctypes = {
    "Default": [
        {"doctype": "Cashfree Settings"}
    ]
}

# Website
website_route_rules = [
    {"from_route": "/api/method/cashfree.make_payment", "to_route": "cashfree.make_payment"},
    {"from_route": "/api/method/cashfree.handle_redirect", "to_route": "cashfree.handle_redirect"},
    {"from_route": "/api/method/cashfree.handle_webhook", "to_route": "cashfree.handle_webhook"}
]

# Whitelisted methods
whitelisted_methods = {
    "cashfree.make_payment": True,
    "cashfree.handle_redirect": True,
    "cashfree.handle_webhook": True,
    "cashfree.get_payment_status": True
}

# Installation
after_install = "cashfree.cashfree.install.after_install"

# Integrations
get_payment_gateway_controller = "cashfree.cashfree.get_controller"

def get_controller(payment_gateway):
    """Get payment gateway controller"""
    if payment_gateway == "Cashfree":
        return "cashfree.CashfreeSettings"
    return None