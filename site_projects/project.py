"""Site workflow hooks and helpers for the standard ERPNext Project."""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

STAGE_ORDER = ["Scoping", "Contract Sent", "Contract Signed", "In Progress", "Completed", "Closed"]


def validate(doc, method=None):
	_calculate_scope(doc)
	_sync_foreman_into_crew(doc)
	_validate_crew(doc)
	_validate_activities(doc)
	_validate_stage(doc)
	_set_site_costs(doc)


def _calculate_scope(doc):
	total = 0
	for row in doc.get("sp_scope_items") or []:
		row.amount = flt(row.qty) * flt(row.rate)
		total += row.amount
	doc.sp_scoped_total = total
	if doc.get("sp_scope_items"):
		doc.estimated_costing = total


def _sync_foreman_into_crew(doc):
	if not doc.sp_foreman:
		return
	for row in doc.get("sp_crew") or []:
		if row.worker == doc.sp_foreman:
			row.role = "Foreman"
			return
	worker = frappe.db.get_value("Site Worker", doc.sp_foreman, ["full_name", "default_daily_rate"], as_dict=True)
	doc.append(
		"sp_crew",
		{
			"worker": doc.sp_foreman,
			"worker_name": worker.full_name,
			"role": "Foreman",
			"daily_rate": worker.default_daily_rate,
			"joined_on": today(),
		},
	)


def _validate_crew(doc):
	seen = set()
	for row in doc.get("sp_crew") or []:
		if row.worker in seen:
			frappe.throw(_("Row {0}: {1} is listed twice in the crew").format(row.idx, row.worker_name or row.worker))
		seen.add(row.worker)
		if row.joined_on and row.left_on and getdate(row.left_on) < getdate(row.joined_on):
			frappe.throw(_("Row {0}: Left On cannot be before Joined On").format(row.idx))


def _validate_activities(doc):
	for row in doc.get("sp_activities") or []:
		if row.completed_on:
			row.status = "Done"
			if not row.started_on:
				row.started_on = row.completed_on
		elif row.status == "Done":
			row.completed_on = today()
			row.started_on = row.started_on or row.completed_on
		elif row.started_on and row.status == "Not Started":
			row.status = "In Progress"
		if row.started_on and row.completed_on and getdate(row.completed_on) < getdate(row.started_on):
			frappe.throw(_("Activity row {0}: Completed On cannot be before Started On").format(row.idx))


def _validate_stage(doc):
	stage = doc.sp_stage or "Scoping"
	idx = STAGE_ORDER.index(stage)

	if idx >= STAGE_ORDER.index("Contract Signed"):
		missing = []
		if not doc.sp_contract_file:
			missing.append(_("Signed Contract attachment"))
		if not doc.sp_contract_signed_on:
			missing.append(_("Contract Signed On"))
		if missing:
			frappe.throw(
				_("Before moving to {0}, fill in: {1} (Scope & Contract tab)").format(
					frappe.bold(stage), ", ".join(missing)
				),
				title=_("Contract Required"),
			)

	if stage == "In Progress" and not doc.actual_start_date:
		doc.actual_start_date = today()

	if stage == "Closed":
		before = doc.get_doc_before_save()
		if not before or before.sp_stage != "Closed":
			_validate_can_close(doc)
		doc.sp_closed_on = doc.sp_closed_on or today()
		doc.actual_end_date = doc.actual_end_date or doc.sp_closed_on
		doc.status = "Completed"
		doc.percent_complete = 100 if doc.percent_complete_method == "Manual" else doc.percent_complete
	elif doc.sp_closed_on:
		doc.sp_closed_on = None


def _validate_can_close(doc):
	problems = []

	open_activities = [r.activity for r in doc.get("sp_activities") or [] if r.status != "Done"]
	if open_activities:
		problems.append(_("Activities not marked Done: {0}").format(", ".join(open_activities)))

	draft_att = frappe.get_all("Site Attendance", {"project": doc.name, "docstatus": 0}, pluck="name")
	if draft_att:
		problems.append(_("Attendance registers still in draft: {0}").format(", ".join(draft_att)))

	unpaid = frappe.get_all(
		"Site Attendance",
		{"project": doc.name, "docstatus": 1, "total_wages": [">", 0], "wage_sheet": ["is", "not set"]},
		pluck="name",
	)
	if unpaid:
		problems.append(_("Attendance not yet on a submitted wage sheet: {0}").format(", ".join(unpaid)))

	draft_sheets = frappe.get_all("Weekly Wage Sheet", {"project": doc.name, "docstatus": 0}, pluck="name")
	if draft_sheets:
		problems.append(_("Wage sheets still in draft: {0}").format(", ".join(draft_sheets)))

	if problems:
		frappe.throw(
			"<br>".join(["• " + p for p in problems]),
			title=_("Project cannot be closed yet"),
		)


def _set_site_costs(doc):
	if doc.is_new():
		return
	costs = get_site_costs(doc.name)
	doc.update(costs)
	doc.sp_cost_variance = flt(doc.sp_scoped_total) - flt(doc.sp_actual_cost)


def get_site_costs(project):
	issued, returned = frappe.db.sql(
		"""
		select
			ifnull(sum(case when se.purpose = 'Material Issue' then sed.amount else 0 end), 0),
			ifnull(sum(case when se.purpose = 'Material Receipt' then sed.amount else 0 end), 0)
		from `tabStock Entry` se
		join `tabStock Entry Detail` sed on sed.parent = se.name
		where se.docstatus = 1 and se.project = %s
			and se.purpose in ('Material Issue', 'Material Receipt')
		""",
		project,
	)[0]
	labour = frappe.db.sql(
		"select ifnull(sum(total_amount), 0) from `tabWeekly Wage Sheet` where docstatus = 1 and project = %s",
		project,
	)[0][0]
	return {
		"sp_material_issued": flt(issued),
		"sp_material_returned": flt(returned),
		"sp_labour_cost": flt(labour),
		"sp_actual_cost": flt(issued) - flt(returned) + flt(labour),
	}


def update_site_costs(project):
	"""Refresh the cost fields without re-running the full Project save."""
	if not project:
		return
	costs = get_site_costs(project)
	scoped = frappe.db.get_value("Project", project, "sp_scoped_total")
	costs["sp_cost_variance"] = flt(scoped) - costs["sp_actual_cost"]
	frappe.db.set_value("Project", project, costs, update_modified=False)


def on_stock_entry_change(doc, method=None):
	if doc.project and doc.purpose in ("Material Issue", "Material Receipt"):
		update_site_costs(doc.project)


@frappe.whitelist()
def get_material_movements(project):
	frappe.has_permission("Project", "read", project, throw=True)
	rows = frappe.db.sql(
		"""
		select se.name, se.posting_date, se.purpose, se.remarks,
			sed.item_code, sed.item_name, sed.qty, sed.uom, sed.basic_rate, sed.amount,
			coalesce(sed.s_warehouse, sed.t_warehouse) as warehouse
		from `tabStock Entry` se
		join `tabStock Entry Detail` sed on sed.parent = se.name
		where se.docstatus = 1 and se.project = %s
			and se.purpose in ('Material Issue', 'Material Receipt')
		order by se.posting_date, se.posting_time, se.name, sed.idx
		""",
		project,
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def close_project(project, closure_notes=None):
	doc = frappe.get_doc("Project", project)
	doc.check_permission("write")
	if closure_notes:
		doc.sp_closure_notes = closure_notes
	doc.sp_stage = "Closed"
	doc.save()
	return doc.name
