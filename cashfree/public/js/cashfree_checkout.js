// Cashfree Payment Handler for Webshop Checkout
frappe.provide("erpnext.shopping_cart");

// Store the original payment handler
if (!erpnext.shopping_cart.original_payment) {
    erpnext.shopping_cart.original_payment = erpnext.shopping_cart.payment;
}

// Override the default payment handler
erpnext.shopping_cart.payment = Class.extend({
    init: function(options) {
        $.extend(this, options);
    },

    make_payment: function() {
        var me = this;
        var payment_method = $('input[name="payment_method"]:checked').val();
        
        // If Cashfree is selected
        if (payment_method === "Cashfree") {
            this.process_cashfree_payment();
        } else {
            // For other payment methods, use the original handler
            var original = new erpnext.shopping_cart.original_payment(this.options);
            original.make_payment();
        }
    },

    process_cashfree_payment: function() {
        var me = this;
        
        // Show loading indicator
        frappe.show_alert({
            message: __("Initializing payment..."),
            indicator: "blue"
        });
        
        // Get customer details from the form
        var customer_name = $('input[name="customer_name"]').val();
        var customer_email = $('input[name="email"]').val();
        var customer_phone = $('input[name="phone"]').val();
        
        // Call the Cashfree payment API
        frappe.call({
            method: "cashfree.api.make_payment",
            args: {
                reference_doctype: "Sales Order",
                reference_docname: me.order_id,
                amount: me.amount,
                currency: me.currency || "INR",
                payer_name: customer_name || "Customer",
                payer_email: customer_email || "customer@example.com",
                payer_phone: customer_phone || "9999999999",
                description: "Payment for order " + me.order_id,
                redirect_url: "/payment-success"
            },
            freeze: true,
            freeze_message: __("Setting up secure payment..."),
            callback: function(r) {
                if (r.message && r.message.status === "Success" && r.message.payment_url) {
                    // Log for debugging
                    console.log("Cashfree payment URL:", r.message.payment_url);
                    
                    // Show success alert
                    frappe.show_alert({
                        message: __("Redirecting to payment gateway..."),
                        indicator: "green"
                    });
                    
                    // Redirect to Cashfree
                    setTimeout(function() {
                        window.location.href = r.message.payment_url;
                    }, 1000);
                    
                } else {
                    // Show error message
                    frappe.msgprint({
                        title: __("Payment Error"),
                        message: r.message && r.message.error ? r.message.error : __("Could not initialize payment"),
                        indicator: "red"
                    });
                    
                    console.error("Cashfree error:", r.message);
                }
            }
        });
    }
});