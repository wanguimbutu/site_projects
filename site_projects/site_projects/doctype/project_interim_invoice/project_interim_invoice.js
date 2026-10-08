// Copyright (c) 2026, wangui and contributors
// For license information, please see license.txt

frappe.ui.form.on("Project Interim Invoice", {
	setup(frm) {
		frm.set_query("source_warehouse", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));
		frm.set_query("item_code", "items", () => ({
			filters: { is_stock_item: 1, disabled: 0 },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.stock_entry) {
			frm.add_custom_button(__("Material Issue"), () =>
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry)
			);
		}
		if (frm.doc.docstatus === 0) {
			frm.set_intro(
				__("Internal only. Submitting issues these materials from stores and holds their cost against the project; nothing is billed to the customer."),
				"blue"
			);
		}
	},
});

frappe.ui.form.on("Project Interim Invoice Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) return;
		if (!row.qty) frappe.model.set_value(cdt, cdn, "qty", 1);
		frappe
			.call("site_projects.site_projects.doctype.project_interim_invoice.project_interim_invoice.get_item_rate", {
				item_code: row.item_code,
			})
			.then(({ message }) => frappe.model.set_value(cdt, cdn, "rate", message));
	},
	qty: calc_totals,
	rate: calc_totals,
	items_remove: calc_totals,
});

function calc_totals(frm, cdt, cdn) {
	if (cdt && cdn && locals[cdt][cdn]) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	}
	frm.set_value("total_qty", (frm.doc.items || []).reduce((s, r) => s + flt(r.qty), 0));
	frm.set_value("total_amount", (frm.doc.items || []).reduce((s, r) => s + flt(r.qty) * flt(r.rate), 0));
}
