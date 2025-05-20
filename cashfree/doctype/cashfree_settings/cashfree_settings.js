// Copyright (c) 2025, walue.biz and contributors
// For license information, please see license.txt

frappe.ui.form.on('Cashfree Settings', {
    refresh: function(frm) {
        frm.add_custom_button(__('Create Payment Gateway Account'), function() {
            frappe.call({
                method: "frappe.client.insert",
                args: {
                    doc: {
                        doctype: "Payment Gateway Account",
                        payment_gateway: "Cashfree",
                        currency: "INR",
                        payment_account: frm.doc.payment_account || "",
                        is_default: 0
                    }
                },
                callback: function(r) {
                    if(!r.exc) {
                        frappe.msgprint(__("Payment Gateway Account created"));
                    }
                }
            });
        });
    },
});