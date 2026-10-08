# Copyright (c) 2026, wangui and contributors
# For license information, please see license.txt

from collections import OrderedDict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, format_date, getdate

from site_projects.billing import get_project_accounts
from site_projects.project import update_site_costs


class WeeklyWageSheet(Document):
	def validate(self):
		if not self.to_date:
			self.to_date = add_days(self.from_date, 6)
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("Week To cannot be before Week From"))
		self.validate_overlap()
		if self.post_journal_entry and not self.expense_account and self.company:
			accounts = get_project_accounts(self.company, throw=False)
			self.expense_account = accounts and accounts.project_cost_account
		if self.docstatus == 0:
			self.build_from_attendance()

	def before_submit(self):
		self.build_from_attendance()
		if not self.entries:
			frappe.throw(_("No unpaid attendance found for this project and week"))

	def on_submit(self):
		for name in self.get_attendance_names():
			frappe.db.set_value("Site Attendance", name, "wage_sheet", self.name, update_modified=False)
		if self.post_journal_entry:
			self.make_journal_entry()
		update_site_costs(self.project)

	def on_cancel(self):
		# paid registers point back at this sheet; cancelling unlinks them instead of blocking
		self.ignore_linked_doctypes = ("Site Attendance",)
		frappe.db.sql(
			"update `tabSite Attendance` set wage_sheet = null where wage_sheet = %s",
			self.name,
		)
		if self.journal_entry:
			je = frappe.get_doc("Journal Entry", self.journal_entry)
			if je.docstatus == 1:
				je.flags.ignore_links = True
				je.cancel()
		update_site_costs(self.project)

	def validate_overlap(self):
		clash = frappe.db.sql(
			"""
			select name from `tabWeekly Wage Sheet`
			where project = %(project)s and docstatus < 2 and name != %(name)s
				and from_date <= %(to_date)s and to_date >= %(from_date)s
			limit 1
			""",
			{"project": self.project, "name": self.name or "", "from_date": self.from_date, "to_date": self.to_date},
		)
		if clash:
			frappe.throw(
				_("Wage Sheet {0} already covers part of this period for {1}").format(clash[0][0], self.project)
			)

	def get_attendance_names(self):
		return [n for n in (self.attendance_list or "").split("\n") if n]

	@frappe.whitelist()
	def build_from_attendance(self):
		"""Rebuild the wage lines from submitted, unpaid attendance in the week.

		Payment references typed against a worker are kept across rebuilds.
		"""
		kept = {r.worker: (r.payment_reference, r.remarks) for r in self.entries}

		rows = frappe.db.sql(
			"""
			select sa.name, sa.attendance_date, e.worker, e.worker_name, e.status, e.day_fraction, e.wage
			from `tabSite Attendance` sa
			join `tabSite Attendance Entry` e on e.parent = sa.name and e.parenttype = 'Site Attendance'
			where sa.docstatus = 1 and sa.project = %(project)s
				and sa.attendance_date between %(from_date)s and %(to_date)s
				and (sa.wage_sheet is null or sa.wage_sheet = '' or sa.wage_sheet = %(name)s)
			order by sa.attendance_date, e.idx
			""",
			{"project": self.project, "from_date": self.from_date, "to_date": self.to_date, "name": self.name or ""},
			as_dict=True,
		)

		registers = []
		workers = OrderedDict()
		for r in rows:
			if r.name not in registers:
				registers.append(r.name)
			if not flt(r.day_fraction):
				continue
			w = workers.setdefault(r.worker, {"worker_name": r.worker_name, "days": 0, "amount": 0, "breakdown": []})
			w["days"] += flt(r.day_fraction)
			w["amount"] += flt(r.wage)
			w["breakdown"].append(
				"{0} {1}".format(format_date(r.attendance_date, "EEE dd-MM"), "½" if r.status == "Half Day" else "✓")
			)

		self.set("entries", [])
		for worker, w in workers.items():
			ref, remarks = kept.get(worker, (None, None))
			info = frappe.db.get_value("Site Worker", worker, ["mpesa_number", "phone"], as_dict=True) or {}
			self.append(
				"entries",
				{
					"worker": worker,
					"worker_name": w["worker_name"],
					"mpesa_number": info.get("mpesa_number") or info.get("phone"),
					"days_worked": w["days"],
					"amount": w["amount"],
					"day_breakdown": ", ".join(w["breakdown"]),
					"payment_reference": ref,
					"remarks": remarks,
				},
			)

		self.attendance_list = "\n".join(registers)
		self.total_workers = len(self.entries)
		self.total_days = sum(flt(r.days_worked) for r in self.entries)
		self.total_amount = sum(flt(r.amount) for r in self.entries)

		drafts = frappe.get_all(
			"Site Attendance",
			{
				"project": self.project,
				"docstatus": 0,
				"attendance_date": ["between", [self.from_date, self.to_date]],
			},
			pluck="name",
		)
		if drafts:
			frappe.msgprint(
				_("These attendance registers are still in draft and are NOT included: {0}").format(", ".join(drafts)),
				indicator="orange",
				title=_("Unsubmitted Attendance"),
			)

	def make_journal_entry(self):
		company = self.company or frappe.db.get_value("Project", self.project, "company")
		cost_center = frappe.db.get_value("Project", self.project, "cost_center") or frappe.get_cached_value(
			"Company", company, "cost_center"
		)
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = company
		je.posting_date = self.payment_date or self.to_date
		je.user_remark = _("Site wages {0} to {1} for project {2} ({3})").format(
			format_date(self.from_date), format_date(self.to_date), self.project, self.name
		)
		je.append(
			"accounts",
			{
				"account": self.expense_account,
				"debit_in_account_currency": self.total_amount,
				"project": self.project,
				"cost_center": cost_center,
			},
		)
		je.append(
			"accounts",
			{
				"account": self.payment_account,
				"credit_in_account_currency": self.total_amount,
				"cost_center": cost_center,
			},
		)
		je.flags.ignore_permissions = True
		je.insert()
		je.submit()
		self.db_set("journal_entry", je.name)
