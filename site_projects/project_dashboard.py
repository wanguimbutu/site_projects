from frappe import _


def get_dashboard_data(data):
	data["transactions"].insert(0, {"label": _("Site"), "items": ["Site Attendance", "Weekly Wage Sheet"]})
	return data
