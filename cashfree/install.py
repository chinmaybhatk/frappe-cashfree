# -*- coding: utf-8 -*-
# Copyright (c) 2025, walue.biz and Contributors
# See license.txt

import frappe
from frappe.model.document import Document

# Custom implementation for create_payment_gateway since it's not available in Frappe v15
def create_payment_gateway(gateway):
    """Create Payment Gateway in Frappe"""
    if not frappe.db.exists("Payment Gateway", gateway):
        payment_gateway = frappe.get_doc({
            "doctype": "Payment Gateway",
            "gateway": gateway
        })
        payment_gateway.insert(ignore_permissions=True)

def after_install():
    """
    Setup Cashfree integration after installation
    """
    try:
        # Create Payment Gateway for Cashfree if not exists
        if not frappe.db.exists("Payment Gateway", {"gateway": "Cashfree"}):
            create_payment_gateway("Cashfree")
            frappe.db.commit()
        
        # Create Cashfree Settings if not exists
        if not frappe.db.exists("Cashfree Settings"):
            settings = frappe.new_doc("Cashfree Settings")
            settings.api_key = ""  # To be filled by user
            settings.secret_key = ""  # To be filled by user
            settings.mode = "TEST"
            settings.payment_capture = 1
            settings.save(ignore_permissions=True)
            frappe.db.commit()
            
        # Create Payment Gateway Account if not exists
        if not frappe.db.exists("Payment Gateway Account", {"payment_gateway": "Cashfree"}):
            account = frappe.new_doc("Payment Gateway Account")
            account.payment_gateway = "Cashfree"
            account.currency = "INR"
            account.payment_account = get_default_bank_account()
            account.is_default = 0
            account.save(ignore_permissions=True)
            frappe.db.commit()
            
    except Exception as e:
        frappe.log_error(
            title="Cashfree Integration Setup Error",
            message=frappe.get_traceback()
        )

def get_default_bank_account():
    """Get default bank account for payment gateway"""
    try:
        # Try to find a bank account
        bank_accounts = frappe.get_list(
            "Account", 
            filters={
                "account_type": "Bank",
                "is_group": 0,
                "company": frappe.defaults.get_user_default("Company")
            }, 
            limit=1
        )
        
        if bank_accounts:
            return bank_accounts[0].name
            
        # If no bank account found, return empty
        return ""
        
    except Exception:
        return ""