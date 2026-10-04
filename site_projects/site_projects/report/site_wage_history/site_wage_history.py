# Copyright (c) 2026, wangui and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "attendance_date", "fieldtype": "Date", "width": 100},
		{"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 140},
		{"label": _("Worker"), "fieldname": "worker", "fieldtype": "Link", "options": "Site Worker", "width": 110},
		{"label": _("Name"), "fieldname": "worker_name", "fieldtype": "Data", "width": 170},
		{"label": _("Role"), "fieldname": "role", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 85},
		{"label": _("In"), "fieldname": "clock_in", "fieldtype": "Time", "width": 80},
		{"label": _("Out"), "fieldname": "clock_out", "fieldtype": "Time", "width": 80},
		{"label": _("Hours"), "fieldname": "hours", "fieldtype": "Float", "width": 70},
		{"label": _("Days"), "fieldname": "day_fraction", "fieldtype": "Float", "width": 60},
		{"label": _("Daily Rate"), "fieldname": "daily_rate", "fieldtype": "Currency", "width": 100},
		{"label": _("Wage"), "fieldname": "wage", "fieldtype": "Currency", "width": 100},
		{"label": _("Wage Sheet"), "fieldname": "wage_sheet", "fieldtype": "Link", "options": "Weekly Wage Sheet", "width": 140},
		{"label": _("Register"), "fieldname": "register", "fieldtype": "Link", "options": "Site Attendance", "width": 140},
	]


def get_data(filters):
	conditions = ["sa.docstatus = 1"]
	if filters.from_date:
		conditions.append("sa.attendance_date >= %(from_date)s")
	if filters.to_date:
		conditions.append("sa.attendance_date <= %(to_date)s")
	if filters.project:
		conditions.append("sa.project = %(project)s")
	if filters.worker:
		conditions.append("e.worker = %(worker)s")
	if filters.payment_status == "Paid":
		conditions.append("ifnull(sa.wage_sheet, '') != ''")
	elif filters.payment_status == "Unpaid":
		conditions.append("ifnull(sa.wage_sheet, '') = '' and e.wage > 0")
	if not filters.include_absent:
		conditions.append("e.status != 'Absent'")

	return frappe.db.sql(
		f"""
		select sa.attendance_date, sa.project, e.worker, e.worker_name, e.role, e.status,
			e.clock_in, e.clock_out, e.hours, e.day_fraction, e.daily_rate, e.wage,
			sa.wage_sheet, sa.name as register
		from `tabSite Attendance` sa
		join `tabSite Attendance Entry` e on e.parent = sa.name and e.parenttype = 'Site Attendance'
		where {" and ".join(conditions)}
		order by sa.attendance_date desc, sa.project, e.idx
		""",
		filters,
		as_dict=True,
	)
