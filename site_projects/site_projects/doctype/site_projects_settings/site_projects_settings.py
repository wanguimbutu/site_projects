# Copyright (c) 2026, wangui and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class SiteProjectsSettings(Document):
	def validate(self):
		seen = set()
		for row in self.company_accounts:
			if row.company in seen:
				frappe.throw(_("Row {0}: {1} is listed twice").format(row.idx, row.company))
			seen.add(row.company)
			self.validate_row(row)

	def validate_row(self, row):
		def account(fieldname):
			return frappe.get_cached_value(
				"Account", row.get(fieldname), ["company", "report_type", "account_type", "is_group"], as_dict=True
			)

		label = lambda f: _(row.meta.get_label(f))
		for f in ("project_cost_account", "cost_of_sales_account", "income_account"):
			acc = account(f)
			if acc.company != row.company:
				frappe.throw(_("Row {0}: {1} must belong to {2}").format(row.idx, label(f), row.company))
			if acc.is_group:
				frappe.throw(_("Row {0}: {1} cannot be a group account").format(row.idx, label(f)))

		cost = account("project_cost_account")
		if cost.report_type != "Balance Sheet":
			frappe.throw(_("Row {0}: Project Cost Account must be a balance sheet account").format(row.idx))
		if cost.account_type == "Stock":
			# ERPNext refuses a Stock-type account as the difference account on a Material Issue
			frappe.throw(_("Row {0}: Project Cost Account cannot have Account Type 'Stock'").format(row.idx))
		for f in ("cost_of_sales_account", "income_account"):
			if account(f).report_type != "Profit and Loss":
				frappe.throw(_("Row {0}: {1} must be a profit and loss account").format(row.idx, label(f)))

		if frappe.db.get_value("Item", row.final_invoice_item, "is_stock_item"):
			frappe.throw(_("Row {0}: Final Valuation Item must be a non-stock item").format(row.idx))
