app_name = "site_projects"
app_title = "Site Projects"
app_publisher = "wangui"
app_description = "Site project booking, crew attendance, weekly wages, materials and closure"
app_email = "wanguimbutu@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "site_projects",
# 		"logo": "/assets/site_projects/logo.png",
# 		"title": "Site Projects",
# 		"route": "/site_projects",
# 		"has_permission": "site_projects.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/site_projects/css/site_projects.css"
# app_include_js = "/assets/site_projects/js/site_projects.js"

# include js, css files in header of web template
# web_include_css = "/assets/site_projects/css/site_projects.css"
# web_include_js = "/assets/site_projects/js/site_projects.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "site_projects/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "site_projects/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "site_projects.utils.jinja_methods",
# 	"filters": "site_projects.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "site_projects.install.before_install"
# after_install = "site_projects.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "site_projects.uninstall.before_uninstall"
# after_uninstall = "site_projects.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "site_projects.utils.before_app_install"
# after_app_install = "site_projects.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "site_projects.utils.before_app_uninstall"
# after_app_uninstall = "site_projects.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "site_projects.notifications.get_notification_config"

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
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"site_projects.tasks.all"
# 	],
# 	"daily": [
# 		"site_projects.tasks.daily"
# 	],
# 	"hourly": [
# 		"site_projects.tasks.hourly"
# 	],
# 	"weekly": [
# 		"site_projects.tasks.weekly"
# 	],
# 	"monthly": [
# 		"site_projects.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "site_projects.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "site_projects.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "site_projects.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["site_projects.utils.before_request"]
# after_request = ["site_projects.utils.after_request"]

# Job Events
# ----------
# before_job = ["site_projects.utils.before_job"]
# after_job = ["site_projects.utils.after_job"]

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

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"site_projects.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# --- Site Projects wiring -------------------------------------------------

after_install = "site_projects.setup.setup"
after_migrate = "site_projects.setup.setup"

doctype_js = {"Project": "public/js/project.js"}

doc_events = {
	"Project": {
		"validate": "site_projects.project.validate",
	},
	"Stock Entry": {
		"on_submit": "site_projects.project.on_stock_entry_change",
		"on_cancel": "site_projects.project.on_stock_entry_change",
	},
}

override_doctype_dashboards = {
	"Project": "site_projects.project_dashboard.get_dashboard_data",
}
