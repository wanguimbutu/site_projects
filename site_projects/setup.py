import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

STAGES = "Scoping\nContract Sent\nContract Signed\nIn Progress\nCompleted\nClosed"


def get_project_custom_fields():
	fields = [
		dict(fieldname="sp_stage", label="Site Stage", fieldtype="Select", options=STAGES,
			default="Scoping", insert_after="status", in_list_view=1, in_standard_filter=1,
			allow_on_submit=0, translatable=0),
	]

	chain = [
		# --- Scope & Contract
		dict(fieldname="sp_tab_scope", label="Scope & Contract", fieldtype="Tab Break"),
		dict(fieldname="sp_scope_section", label="Scoped Cost", fieldtype="Section Break",
			description="What we estimated the job would cost when it was scoped out"),
		dict(fieldname="sp_scope_items", label="Scope Items", fieldtype="Table", options="Project Scope Item"),
		dict(fieldname="sp_scoped_total", label="Scoped Total", fieldtype="Currency", read_only=1,
			options="Company:company:default_currency"),
		dict(fieldname="sp_contract_section", label="Contract", fieldtype="Section Break"),
		dict(fieldname="sp_contract_value", label="Contract Value", fieldtype="Currency",
			options="Company:company:default_currency"),
		dict(fieldname="sp_contract_sent_on", label="Contract Received On", fieldtype="Date"),
		dict(fieldname="sp_contract_signed_on", label="Contract Signed On", fieldtype="Date"),
		dict(fieldname="sp_contract_cb", fieldtype="Column Break"),
		dict(fieldname="sp_contract_file", label="Signed Contract", fieldtype="Attach"),
		dict(fieldname="sp_contract_signed_by", label="Signed By (Client)", fieldtype="Data"),
		dict(fieldname="sp_contract_notes", label="Contract Notes", fieldtype="Small Text"),
		# --- Crew
		dict(fieldname="sp_tab_crew", label="Crew", fieldtype="Tab Break"),
		dict(fieldname="sp_foreman", label="Foreman", fieldtype="Link", options="Site Worker"),
		dict(fieldname="sp_foreman_name", label="Foreman Name", fieldtype="Data",
			fetch_from="sp_foreman.full_name", read_only=1),
		dict(fieldname="sp_crew_section", label="Crew on this Project", fieldtype="Section Break",
			description="Only workers listed here (and not marked as left) are loaded into the daily register"),
		dict(fieldname="sp_crew", label="Crew", fieldtype="Table", options="Project Crew Member"),
		# --- Progress & Feedback
		dict(fieldname="sp_tab_progress", label="Progress & Feedback", fieldtype="Tab Break"),
		dict(fieldname="sp_activities", label="Activities / Milestones", fieldtype="Table",
			options="Project Activity"),
		dict(fieldname="sp_feedback_section", label="Feedback & Reviews", fieldtype="Section Break"),
		dict(fieldname="sp_feedback", label="Feedback", fieldtype="Table", options="Project Feedback"),
		dict(fieldname="sp_closure_section", label="Closure", fieldtype="Section Break"),
		dict(fieldname="sp_closed_on", label="Closed On", fieldtype="Date", read_only=1),
		dict(fieldname="sp_closure_cb", fieldtype="Column Break"),
		dict(fieldname="sp_closure_notes", label="Closure Notes", fieldtype="Small Text"),
		# --- Site Costs
		dict(fieldname="sp_tab_costs", label="Site Costs", fieldtype="Tab Break"),
		dict(fieldname="sp_material_issued", label="Materials Sent to Site", fieldtype="Currency",
			read_only=1, options="Company:company:default_currency"),
		dict(fieldname="sp_material_returned", label="Materials Returned", fieldtype="Currency",
			read_only=1, options="Company:company:default_currency"),
		dict(fieldname="sp_labour_cost", label="Wages Paid", fieldtype="Currency", read_only=1,
			options="Company:company:default_currency"),
		dict(fieldname="sp_costs_cb", fieldtype="Column Break"),
		dict(fieldname="sp_actual_cost", label="Actual Cost (Net Materials + Wages)", fieldtype="Currency",
			read_only=1, options="Company:company:default_currency"),
		dict(fieldname="sp_cost_variance", label="Scoped minus Actual", fieldtype="Currency", read_only=1,
			options="Company:company:default_currency",
			description="Positive means the job came in under the scoped cost"),
		dict(fieldname="sp_materials_section", label="Material Movements", fieldtype="Section Break"),
		dict(fieldname="sp_materials_html", label="Material Movements", fieldtype="HTML"),
	]

	prev = "message"
	for f in chain:
		f["insert_after"] = prev
		prev = f["fieldname"]
		fields.append(f)

	return {"Project": fields}


CHILD_DOCTYPES = ("project_scope_item", "project_crew_member", "project_activity", "project_feedback", "site_worker")


def setup():
	# the Project custom fields point at these; make sure they exist even if module sync was skipped
	for dt in CHILD_DOCTYPES:
		frappe.reload_doc("site_projects", "doctype", dt)

	if not frappe.db.exists("Role", "Site Foreman"):
		frappe.get_doc({"doctype": "Role", "role_name": "Site Foreman", "desk_access": 1}).insert(
			ignore_permissions=True
		)
	create_custom_fields(get_project_custom_fields(), update=True)
