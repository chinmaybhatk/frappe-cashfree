frappe.ui.form.on('Payment Request', {
    refresh: function(frm) {
        // Add a custom button for Cashfree payment link
        if(frm.doc.status !== 'Paid' && frm.doc.payment_gateway === 'Cashfree') {
            frm.add_custom_button(__('Generate Cashfree Payment Link'), function() {
                frappe.call({
                    method: 'cashfree.make_payment',
                    args: {
                        'reference_doctype': frm.doc.reference_doctype,
                        'reference_docname': frm.doc.reference_docname
                    },
                    callback: function(r) {
                        if(r.message && r.message.redirect_to) {
                            window.open(r.message.redirect_to, '_blank');
                        }
                    }
                });
            }).addClass('btn-primary');
        }
        
        // Show payment status button for completed payments
        if(frm.doc.status === 'Paid' && frm.doc.payment_gateway === 'Cashfree') {
            frm.add_custom_button(__('View Cashfree Payment'), function() {
                frappe.call({
                    method: 'frappe.client.get_list',
                    args: {
                        doctype: 'Integration Request',
                        filters: {
                            'reference_doctype': 'Payment Request',
                            'reference_docname': frm.doc.name,
                            'status': 'Completed',
                            'service_name': 'Cashfree'
                        },
                        fields: ['data'],
                        limit: 1
                    },
                    callback: function(r) {
                        if(r.message && r.message.length) {
                            let data = JSON.parse(r.message[0].data);
                            let dialog = new frappe.ui.Dialog({
                                title: __('Cashfree Payment Details'),
                                fields: [
                                    {fieldname: 'order_id', label: __('Order ID'), fieldtype: 'Data', read_only: 1, default: data.order_id},
                                    {fieldname: 'cf_payment_id', label: __('Cashfree Payment ID'), fieldtype: 'Data', read_only: 1, default: data.cf_payment_id},
                                    {fieldname: 'order_amount', label: __('Amount'), fieldtype: 'Currency', read_only: 1, default: data.order_amount},
                                    {fieldname: 'order_status', label: __('Status'), fieldtype: 'Data', read_only: 1, default: data.order_status},
                                    {fieldname: 'payment_method', label: __('Payment Method'), fieldtype: 'Data', read_only: 1, default: data.payment_method},
                                    {fieldname: 'transaction_time', label: __('Transaction Time'), fieldtype: 'Data', read_only: 1, default: data.transaction_time}
                                ]
                            });
                            dialog.show();
                        } else {
                            frappe.msgprint(__('No payment details found'));
                        }
                    }
                });
            });
        }
    },
    
    payment_gateway: function(frm) {
        // When payment gateway is changed to Cashfree
        if(frm.doc.payment_gateway === 'Cashfree') {
            // You can add any Cashfree-specific logic here if needed
            frm.refresh();
        }
    }
});