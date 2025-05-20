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

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/cashfree/css/cashfree.css"
# app_include_js = "/assets/cashfree/js/cashfree.js"

# include js, css files in header of web template
# web_include_css = "/assets/cashfree/css/cashfree.css"
# web_include_js = "/assets/cashfree/js/cashfree.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "cashfree/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Payment Request": "public/js/payment_request.js"
}

# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Website Route Rules
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

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "cashfree.install.before_install"
after_install = "cashfree.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "cashfree.uninstall.before_uninstall"
# after_uninstall = "cashfree.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "cashfree.utils.before_app_install"
# after_app_install = "cashfree.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "cashfree.utils.before_app_uninstall"
# after_app_uninstall = "cashfree.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "cashfree.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"cashfree.tasks.all"
# 	],
# 	"daily": [
# 		"cashfree.tasks.daily"
# 	],
# 	"hourly": [
# 		"cashfree.tasks.hourly"
# 	],
# 	"weekly": [
# 		"cashfree.tasks.weekly"
# 	],
# 	"monthly": [
# 		"cashfree.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "cashfree.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "cashfree.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "cashfree.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Request Events
# ----------------
# before_request = ["cashfree.utils.before_request"]
# after_request = ["cashfree.utils.after_request"]

# Job Events
# ----------
# before_job = ["cashfree.utils.before_job"]
# after_job = ["cashfree.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and Authorization
# --------------------------------

# auth_hooks = [
# 	"cashfree.auth.validate"
# ]

# Fixtures (exports/imports)
fixtures = [
    {"dt": "Custom Field", "filters": [["fieldname", "in", ["cashfree_settings"]]]},
    {"dt": "Payment Gateway"}
]

# Integrations
get_payment_gateway_controller = "cashfree.controllers.get_controller"