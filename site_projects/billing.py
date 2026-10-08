"""Project costing and billing.

Materials sent to a site are held in a balance-sheet "project cost" account
(tagged with the project) instead of Stock Adjustment. When the final
valuation is invoiced, the project's held balance is moved to Cost of Sales
so revenue and cost land in the same period.
"""

import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form

FINAL_INVOICE_FLAG = "sp_is_final_project_invoice"


def get_project_accounts(company, throw=True):
	row = frappe.db.get_value(
		"Site Project Accounts",
		{"parent": "Site Projects Settings", "company": company},
		["project_cost_account", "cost_of_sales_account", "income_account", "final_invoice_item"],
		as_dict=True,
	)
	if not row and throw:
		frappe.throw(
			_("Project accounts are not set up for {0}. Add a row in {1}.").format(
				frappe.bold(company), get_link_to_form("Site Projects Settings", "Site Projects Settings")
			),
			title=_("Project Accounts Missing"),
		)
	return row


def get_project_cost_center(project, company):
	return frappe.db.get_value("Project", project, "cost_center") or frappe.get_cached_value(
		"Company", company, "cost_center"
	)


def get_held_cost(project, account):
	"""Net balance of the project cost account for this project (materials, returns, wages)."""
	return flt(
		frappe.db.sql(
			"""
			select sum(debit - credit) from `tabGL Entry`
			where account = %s and project = %s and is_cancelled = 0
			""",
			(account, project),
		)[0][0]
	)


def get_final_invoice(project, submitted_only=False):
	filters = {"project": project, FINAL_INVOICE_FLAG: 1, "docstatus": 1 if submitted_only else ["<", 2]}
	return frappe.db.get_value("Sales Invoice", filters, "name")


# --- Stock Entry


def set_project_cost_account(doc, method=None):
	"""Send project material issues/returns to the project cost account, not Stock Adjustment."""
	if not doc.project or doc.purpose not in ("Material Issue", "Material Receipt"):
		return
	accounts = get_project_accounts(doc.company, throw=False)
	if not accounts:
		return
	if doc.purpose == "Material Issue" and doc.docstatus == 0:
		block_issue_after_final_invoice(doc.project)
	cost_center = get_project_cost_center(doc.project, doc.company)
	for row in doc.items:
		row.expense_account = accounts.project_cost_account
		row.cost_center = row.cost_center or cost_center
		row.project = row.project or doc.project


# --- Final invoice


@frappe.whitelist()
def make_final_invoice(project, valuation):
	valuation = flt(valuation)
	if valuation <= 0:
		frappe.throw(_("Final valuation must be greater than zero"))

	proj = frappe.get_doc("Project", project)
	proj.check_permission("read")
	frappe.has_permission("Sales Invoice", "create", throw=True)
	if not proj.customer:
		frappe.throw(_("Set the Customer on project {0} first").format(project))

	existing = get_final_invoice(project)
	if existing:
		frappe.throw(
			_("Project {0} already has a final invoice: {1}").format(project, get_link_to_form("Sales Invoice", existing))
		)

	accounts = get_project_accounts(proj.company)
	cost_center = get_project_cost_center(project, proj.company)
	interim = frappe.get_all(
		"Project Interim Invoice",
		{"project": project, "docstatus": 1},
		["name", "posting_date"],
		order_by="posting_date, name",
	)
	description = _("Final valuation for {0}").format(proj.project_name)
	if interim:
		description += "<br>" + _("Interim invoices: {0}").format(", ".join(i.name for i in interim))

	si = frappe.new_doc("Sales Invoice")
	si.customer = proj.customer
	si.company = proj.company
	si.project = project
	si.cost_center = cost_center
	si.set(FINAL_INVOICE_FLAG, 1)
	si.append(
		"items",
		{
			"item_code": accounts.final_invoice_item,
			"qty": 1,
			"rate": valuation,
			"description": description,
			"income_account": accounts.income_account,
			"cost_center": cost_center,
			"project": project,
		},
	)
	si.set_missing_values()
	# set_missing_values pulls item defaults; the configured sales account wins
	si.items[0].income_account = accounts.income_account
	si.items[0].rate = valuation
	si.calculate_taxes_and_totals()
	si.insert()

	frappe.db.set_value("Project", project, "sp_final_valuation", valuation, update_modified=False)
	return si.name


def release_project_cost(doc, method=None):
	"""On final invoice submit: move the project's held cost to Cost of Sales."""
	if not doc.get(FINAL_INVOICE_FLAG) or not doc.project:
		return
	accounts = get_project_accounts(doc.company)
	held = get_held_cost(doc.project, accounts.project_cost_account)
	if held:
		cost_center = get_project_cost_center(doc.project, doc.company)
		debit, credit = (accounts.cost_of_sales_account, accounts.project_cost_account)
		if held < 0:  # more returned than issued; reverse the direction
			debit, credit = credit, debit
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = doc.company
		je.posting_date = doc.posting_date
		je.user_remark = _("Project costs for {0} moved to Cost of Sales on final invoice {1}").format(
			doc.project, doc.name
		)
		for account, field in ((debit, "debit_in_account_currency"), (credit, "credit_in_account_currency")):
			je.append(
				"accounts",
				{"account": account, field: abs(held), "project": doc.project, "cost_center": cost_center},
			)
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()
		doc.db_set("sp_cost_release_entry", je.name)

	frappe.db.set_value(
		"Project",
		doc.project,
		{"sp_final_invoice": doc.name, "sp_final_valuation": doc.net_total},
		update_modified=False,
	)


def reverse_project_cost_release(doc, method=None):
	if not doc.get(FINAL_INVOICE_FLAG) or not doc.project:
		return
	if doc.get("sp_cost_release_entry"):
		je = frappe.get_doc("Journal Entry", doc.sp_cost_release_entry)
		if je.docstatus == 1:
			je.flags.ignore_links = True
			je.flags.ignore_permissions = True
			je.cancel()
	if frappe.db.get_value("Project", doc.project, "sp_final_invoice") == doc.name:
		frappe.db.set_value("Project", doc.project, "sp_final_invoice", None, update_modified=False)


def block_issue_after_final_invoice(project):
	final = get_final_invoice(project, submitted_only=True)
	if final:
		frappe.throw(
			_(
				"Project {0} has already been invoiced ({1}). Cancel the final invoice before sending more materials against it."
			).format(project, get_link_to_form("Sales Invoice", final))
		)
