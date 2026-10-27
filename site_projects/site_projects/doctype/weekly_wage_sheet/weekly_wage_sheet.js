// Copyright (c) 2026, wangui and contributors
// For license information, please see license.txt

frappe.provide("site_projects");

site_projects.export_wage_sheets = function (names) {
	window.open(
		"/api/method/site_projects.wage_export.export_wage_sheets?names=" + encodeURIComponent(JSON.stringify(names))
	);
};

frappe.ui.form.on("Weekly Wage Sheet", {
	setup(frm) {
		const account_query = (types) => () => ({
			filters: { company: frm.doc.company, is_group: 0, ...(types ? { account_type: ["in", types] } : {}) },
		});
		// Expense, or a balance-sheet project cost account (e.g. 201165) so wages are released with the final invoice
		frm.set_query("expense_account", () => ({
			filters: { company: frm.doc.company, is_group: 0, root_type: ["in", ["Expense", "Asset"]] },
		}));
		frm.set_query("payment_account", account_query(["Cash", "Bank"]));
	},

	refresh(frm) {
		if (!frm.is_new() && frm.doc.entries?.length) {
			frm.add_custom_button(__("Export to Excel"), () => {
				if (frm.is_dirty()) {
					frappe.msgprint(__("Save the wage sheet first"));
					return;
				}
				site_projects.export_wage_sheets([frm.doc.name]);
			});
		}
		if (frm.doc.docstatus === 0 && frm.doc.project && frm.doc.from_date) {
			frm.add_custom_button(__("Get Attendance"), () => {
				frm.call("build_from_attendance").then(() => {
					frm.refresh_fields();
					frm.dirty();
				});
			}).addClass("btn-primary");
		}
	},

	from_date(frm) {
		if (frm.doc.from_date) {
			frm.set_value("to_date", frappe.datetime.add_days(frm.doc.from_date, 6));
		}
	},
});
