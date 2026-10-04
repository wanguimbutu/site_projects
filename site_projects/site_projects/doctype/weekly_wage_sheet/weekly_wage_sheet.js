// Copyright (c) 2026, wangui and contributors
// For license information, please see license.txt

frappe.ui.form.on("Weekly Wage Sheet", {
	setup(frm) {
		const account_query = (types) => () => ({
			filters: { company: frm.doc.company, is_group: 0, ...(types ? { account_type: ["in", types] } : {}) },
		});
		frm.set_query("expense_account", () => ({
			filters: { company: frm.doc.company, is_group: 0, root_type: "Expense" },
		}));
		frm.set_query("payment_account", account_query(["Cash", "Bank"]));
	},

	refresh(frm) {
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
