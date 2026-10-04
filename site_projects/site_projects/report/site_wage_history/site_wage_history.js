// Copyright (c) 2026, wangui and contributors
// For license information, please see license.txt

frappe.query_reports["Site Wage History"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "project", label: __("Project"), fieldtype: "Link", options: "Project" },
		{ fieldname: "worker", label: __("Worker"), fieldtype: "Link", options: "Site Worker" },
		{
			fieldname: "payment_status",
			label: __("Payment Status"),
			fieldtype: "Select",
			options: "\nPaid\nUnpaid",
		},
		{ fieldname: "include_absent", label: __("Include Absent"), fieldtype: "Check" },
	],
};
