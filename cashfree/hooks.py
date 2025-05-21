# -*- coding: utf-8 -*-
from __future__ import unicode_literals

app_name = "cashfree"
app_title = "Cashfree Integration"
app_publisher = "walue.biz"
app_description = "Cashfree Payment Gateway Integration for Frappe"
app_icon = "octicon octicon-credit-card"
app_color = "#25C4B9"
app_email = "chinmaybhatk@gmail.com"
app_license = "MIT"

# Doctype hooks
doctype_js = {
    "Payment Request": "public/js/payment_request.js"
}

# Website
website_route_rules = [
    {"from_route": "/api/method/cashfree.api.make_payment", "to_route": "cashfree.api.make_payment"},
    {"from_route": "/api/method/cashfree.api.handle_redirect", "to_route": "cashfree.api.handle_redirect"},
    {"from_route": "/api/method/cashfree.api.handle_webhook", "to_route": "cashfree.api.handle_webhook"}
]

# Whitelisted methods
whitelisted_methods = {
    "cashfree.api.make_payment": True,
    "cashfree.api.handle_redirect": True,
    "cashfree.api.handle_webhook": True,
    "cashfree.api.get_payment_status": True
}

# Installation
after_install = "cashfree.install.after_install"

# Fixtures
fixtures = [
    {"dt": "Custom Field", "filters": [["fieldname", "in", ["cashfree_settings"]]]},
    {"dt": "Payment Gateway"}
]

# Integrations
get_payment_gateway_controller = "cashfree.cashfree.controllers.get_controller"

payment_gateway_controllers = {
    "Cashfree": "cashfree.controller.CashfreeController"
}
# Add the following to hooks.py:

# Add to hooks.py
web_include_js = [
    "/assets/cashfree/js/cashfree_checkout.js",
    "/assets/cashfree/js/custom_checkout.js"
]
website_route_rules = [
    {"from_route": "/payment-success", "to_route": "payment_success"},
    {"from_route": "/payment-failure", "to_route": "payment_failure"}
]