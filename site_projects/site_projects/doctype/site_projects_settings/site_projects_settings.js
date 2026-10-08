// Copyright (c) 2026, wangui and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Projects Settings", {
	setup(frm) {
		const query = (extra) => (doc, cdt, cdn) => ({
			filters: { company: locals[cdt][cdn].company, is_group: 0, ...extra },
		});
		frm.set_query("project_cost_account", "company_accounts", query({ report_type: "Balance Sheet", account_type: ["!=", "Stock"] }));
		frm.set_query("cost_of_sales_account", "company_accounts", query({ report_type: "Profit and Loss" }));
		frm.set_query("income_account", "company_accounts", query({ root_type: "Income" }));
		frm.set_query("final_invoice_item", "company_accounts", () => ({ filters: { is_stock_item: 0, disabled: 0 } }));
	},
});
