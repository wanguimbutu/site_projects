from frappe import _


def get_dashboard_data(data):
	data["transactions"].insert(0, {"label": _("Site"), "items": ["Site Attendance", "Weekly Wage Sheet"]})
	data["transactions"].insert(1, {"label": _("Billing"), "items": ["Project Interim Invoice"]})
	return data
