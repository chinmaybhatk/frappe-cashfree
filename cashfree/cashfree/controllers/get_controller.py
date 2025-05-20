# -*- coding: utf-8 -*-
from __future__ import unicode_literals

def get_controller(payment_gateway):
    """Get payment gateway controller"""
    if payment_gateway == "Cashfree":
        return "cashfree.doctype.cashfree_settings.cashfree_settings.CashfreeSettings"
    return None