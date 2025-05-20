# -*- coding: utf-8 -*-
# Copyright (c) 2025, walue.biz and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils import get_url
from frappe import _

# Custom implementation for create_payment_gateway since it's not available in Frappe v15
def create_payment_gateway(gateway):
    """Create Payment Gateway and Gateway Account in Frappe"""
    if not frappe.db.exists("Payment Gateway", gateway):
        payment_gateway = frappe.get_doc({
            "doctype": "Payment Gateway",
            "gateway": gateway
        })
        payment_gateway.insert(ignore_permissions=True)

class CashfreeSettings(Document):
    supported_currencies = ["INR"]
    
    def validate(self):
        create_payment_gateway('Cashfree')
        self.validate_credentials()
    
    def validate_credentials(self):
        """Validate API credentials"""
        if not self.get('api_key') or not self.get('secret_key'):
            frappe.throw(_("API Key and Secret Key are required."))
    
    def get_payment_url(self, **kwargs):
        """Return payment url with several payment options"""
        return get_url(f"/api/method/cashfree.cashfree.api.make_payment?reference_doctype={kwargs.get('reference_doctype')}&reference_docname={kwargs.get('reference_docname')}")
    
    def get_api_url(self):
        """Return Cashfree API URL based on the mode"""
        if self.mode == "PRODUCTION":
            return "https://api.cashfree.com"
        else:
            return "https://sandbox.cashfree.com"