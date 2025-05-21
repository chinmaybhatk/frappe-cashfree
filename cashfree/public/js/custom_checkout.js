frappe.ready(function() {
    if ($("#checkout-payment").length) {
        // Add Cashfree details to the method selector
        if ($('[name="payment_method"][value="Cashfree"]').length === 0) {
            var cashfreeOption = `
                <div class="form-group">
                    <div class="radio">
                        <input type="radio" name="payment_method" id="cashfree" value="Cashfree">
                        <label for="cashfree" class="control-label">
                            Pay with Cashfree
                            <i class="fa fa-credit-card"></i>
                        </label>
                    </div>
                </div>
            `;
            $("#payment-options").append(cashfreeOption);
        }
    }
});