@frappe.whitelist(allow_guest=True)
def make_payment(checkout_data=None):
    """Create payment request and redirect to payment page"""
    try:
        # Log for debugging
        frappe.logger().debug(f"make_payment called with: {checkout_data}, form_dict: {frappe.form_dict}")
        
        # Process input data
        if checkout_data is None:
            checkout_data = frappe.form_dict
            
        if isinstance(checkout_data, str):
            checkout_data = json.loads(checkout_data)
            
        if checkout_data is None or not isinstance(checkout_data, dict):
            checkout_data = {}
            
        # Extract reference document information
        reference_doctype = checkout_data.get("reference_doctype")
        reference_name = checkout_data.get("reference_name")
        
        # If no reference document, create a temporary Sales Order
        if not reference_doctype or not reference_name:
            frappe.logger().debug("No reference document provided, creating temporary Sales Order")
            
            # Find or create a customer
            customer_email = frappe.session.user if frappe.session.user != "Guest" else "guest@example.com"
            customer = frappe.db.get_value("Customer", {"email_id": customer_email}, "name")
            
            if not customer:
                customers = frappe.get_all("Customer", limit=1)
                if customers:
                    customer = customers[0].name
                else:
                    # Create a default customer if none exists
                    cust = frappe.new_doc("Customer")
                    cust.customer_name = "Website Customer"
                    cust.customer_type = "Individual"
                    cust.customer_group = frappe.db.get_default("Customer Group") or "All Customer Groups"
                    cust.territory = frappe.db.get_default("Territory") or "All Territories"
                    cust.save(ignore_permissions=True)
                    customer = cust.name
            
            # Create a Sales Order
            so = frappe.new_doc("Sales Order")
            so.customer = customer
            so.order_type = "Shopping Cart"
            so.company = frappe.db.get_default("Company")
            so.transaction_date = frappe.utils.today()
            so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
            
            # Add at least one item
            amount = float(checkout_data.get("amount") or 100)
            item_code = None
            
            # Try to find a valid item
            items = frappe.get_all("Item", 
                filters={"is_stock_item": 0}, 
                fields=["name"], 
                limit=1)
                
            if items:
                item_code = items[0].name
            else:
                # If no item found, create a service item
                item = frappe.new_doc("Item")
                item.item_code = "PAYMENT-SERVICE"
                item.item_name = "Payment Service"
                item.item_group = frappe.db.get_default("Item Group") or "All Item Groups"
                item.is_stock_item = 0
                item.stock_uom = "Nos"
                item.save(ignore_permissions=True)
                item_code = item.name
            
            # Add item to order
            so.append("items", {
                "item_code": item_code,
                "qty": 1,
                "rate": amount,
                "amount": amount,
                "delivery_date": frappe.utils.add_days(frappe.utils.today(), 7)
            })
            
            # Set totals
            so.grand_total = amount
            so.rounded_total = amount
            so.base_grand_total = amount
            so.base_rounded_total = amount
            
            # Save the Sales Order
            so.save(ignore_permissions=True)
            frappe.db.commit()
            
            # Update checkout data with new reference
            reference_doctype = "Sales Order"
            reference_name = so.name
            checkout_data["reference_doctype"] = reference_doctype
            checkout_data["reference_name"] = reference_name
            
            frappe.logger().debug(f"Created temporary Sales Order: {reference_name}")
        
        # Create Payment Request
        payment_request = frappe.new_doc("Payment Request")
        payment_request.reference_doctype = reference_doctype
        payment_request.reference_name = reference_name
        payment_request.payment_request_type = "Inward"
        payment_request.currency = checkout_data.get("currency") or "INR"
        payment_request.grand_total = float(checkout_data.get("amount") or 100)
        
        # Set gateway details
        payment_request.payment_gateway = "Cashfree"
        payment_request.payment_gateway_account = frappe.db.get_value(
            "Payment Gateway Account",
            {"payment_gateway": "Cashfree", "currency": payment_request.currency},
            "name"
        )
        
        # Set email and messages
        payment_request.email_to = checkout_data.get("email") or frappe.session.user
        payment_request.subject = f"Payment Request for {reference_doctype} {reference_name}"
        payment_request.message = "Please click the link below to make your payment"
        
        # Save and submit
        payment_request.save(ignore_permissions=True)
        payment_request.submit()
        
        # Get controller and create payment
        controller = frappe.get_doc("Payment Gateway", "Cashfree").get_controller()
        
        payment_url = controller.get_payment_url(**{
            "amount": payment_request.grand_total,
            "currency": payment_request.currency,
            "reference_doctype": payment_request.reference_doctype,
            "reference_docname": payment_request.reference_name,
            "payer_email": payment_request.email_to,
            "payer_name": frappe.db.get_value("User", frappe.session.user, "full_name") or "Customer",
            "order_id": payment_request.name,
            "payment_gateway": payment_request.payment_gateway
        })
        
        # Check if this is an API call or web request
        is_api = frappe.local.request.path.startswith('/api/')
        
        if is_api:
            return {
                "success": True,
                "payment_url": payment_url,
                "payment_request": payment_request.name
            }
        else:
            # Redirect to payment page
            frappe.local.response["type"] = "redirect"
            frappe.local.response["location"] = payment_url
    
    except Exception as e:
        frappe.logger().error(f"Error in make_payment: {str(e)}", traceback=True)
        return {
            "success": False,
            "message": str(e)
        }