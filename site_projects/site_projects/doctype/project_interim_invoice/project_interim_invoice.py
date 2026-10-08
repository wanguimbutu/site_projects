# Copyright (c) 2026, wangui and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from site_projects.billing import block_issue_after_final_invoice, get_project_accounts, get_project_cost_center


class ProjectInterimInvoice(Document):
	def validate(self):
		if frappe.db.get_value("Project", self.project, "sp_stage") == "Closed":
			frappe.throw(_("Project {0} is closed").format(self.project))
		for row in self.items:
			row.amount = flt(row.qty) * flt(row.rate)
		self.total_qty = sum(flt(r.qty) for r in self.items)
		self.total_amount = sum(flt(r.amount) for r in self.items)

	def before_submit(self):
		get_project_accounts(self.company)
		block_issue_after_final_invoice(self.project)

	def on_submit(self):
		se = self.make_material_issue()
		# write the actual stock cost back so the interim value can be compared with cost
		by_idx = {r.idx: r for r in se.items}
		for row in self.items:
			issued = by_idx.get(row.idx)
			if issued:
				row.db_set({"valuation_rate": issued.basic_rate, "cost_amount": issued.amount})
		self.db_set({"stock_entry": se.name, "total_cost": sum(flt(r.amount) for r in se.items)})

	def on_cancel(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.flags.ignore_links = True
				se.cancel()

	def make_material_issue(self):
		accounts = get_project_accounts(self.company)
		cost_center = get_project_cost_center(self.project, self.company)
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Issue"
		se.purpose = "Material Issue"
		se.company = self.company
		se.project = self.project
		se.posting_date = self.posting_date
		se.set_posting_time = 1
		se.from_warehouse = self.source_warehouse
		se.remarks = _("Sent to site: {0} (interim invoice {1})").format(self.project_name, self.name)
		for row in self.items:
			se.append(
				"items",
				{
					"item_code": row.item_code,
					"qty": row.qty,
					"s_warehouse": self.source_warehouse,
					"expense_account": accounts.project_cost_account,
					"cost_center": cost_center,
					"project": self.project,
				},
			)
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		return se


@frappe.whitelist()
def get_item_rate(item_code):
	"""Default billing rate: the item's price on the default selling price list, else its standard rate."""
	price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list")
	rate = None
	if price_list:
		rate = frappe.db.get_value(
			"Item Price", {"item_code": item_code, "price_list": price_list, "selling": 1}, "price_list_rate"
		)
	return flt(rate) or flt(frappe.db.get_value("Item", item_code, "standard_rate"))
