# Copyright (c) 2026, wangui and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, getdate, now_datetime, nowdate, time_diff_in_hours

DAY_FRACTION = {"Present": 1.0, "Half Day": 0.5, "Absent": 0.0}
MANUAL_TIME_FIELDS = ("clock_in", "clock_out", "clock_in_location", "clock_out_location")


class SiteAttendance(Document):
	def validate(self):
		self.validate_project()
		self.validate_duplicate_register()
		self.strip_manual_times_on_new()
		self.validate_entries()
		self.calculate_totals()

	def before_submit(self):
		not_out = [
			r.worker_name or r.worker
			for r in self.entries
			if r.clock_in and not r.clock_out and r.status != "Absent"
		]
		if not_out:
			frappe.throw(
				_("These workers have not clocked out: {0}. Clock them out or mark them Absent before submitting.").format(
					", ".join(not_out)
				),
				title=_("Missing Clock Out"),
			)
		if not any(r.status != "Absent" for r in self.entries):
			frappe.throw(_("No one is marked present on this register"))

	def before_cancel(self):
		if self.wage_sheet and frappe.db.get_value("Weekly Wage Sheet", self.wage_sheet, "docstatus") == 1:
			frappe.throw(
				_("This register has been paid on Wage Sheet {0}. Cancel that wage sheet first.").format(
					frappe.bold(self.wage_sheet)
				)
			)

	def validate_project(self):
		stage = frappe.db.get_value("Project", self.project, "sp_stage")
		if stage == "Closed":
			frappe.throw(_("Project {0} is closed").format(self.project))
		if getdate(self.attendance_date) > getdate(nowdate()):
			frappe.throw(_("Attendance cannot be recorded for a future date"))

	def validate_duplicate_register(self):
		existing = frappe.db.get_value(
			"Site Attendance",
			{
				"project": self.project,
				"attendance_date": self.attendance_date,
				"docstatus": ["<", 2],
				"name": ["!=", self.name],
			},
		)
		if existing:
			frappe.throw(
				_("An attendance register for {0} on {1} already exists: {2}").format(
					self.project, frappe.format(self.attendance_date, "Date"), existing
				)
			)

	def strip_manual_times_on_new(self):
		"""Frappe does not reset high-permlevel child fields on new docs, so do it here."""
		if not self.is_new() or self.flags.ignore_permissions or frappe.session.user == "Administrator":
			return
		if 1 in self.get_permlevel_access():
			return
		for row in self.entries:
			for f in MANUAL_TIME_FIELDS:
				row.set(f, None)
		self.set_rates_from_crew(force=True)

	def validate_entries(self):
		before = self.get_doc_before_save()
		had_clock_in = {r.name for r in before.entries if r.clock_in} if before else set()
		seen = set()
		for row in self.entries:
			if row.worker in seen:
				frappe.throw(_("Row {0}: {1} appears twice").format(row.idx, row.worker_name or row.worker))
			seen.add(row.worker)

			if not row.clock_in:
				row.clock_out = None
				row.status = "Absent"
			elif row.status == "Absent" and row.name not in had_clock_in:
				# times just entered: assume present. An existing clock-in later marked Absent stays Absent.
				row.status = "Present"

			row.hours = 0
			if row.clock_in and row.clock_out:
				start = get_datetime(f"{self.attendance_date} {row.clock_in}")
				end = get_datetime(f"{self.attendance_date} {row.clock_out}")
				if end < start:
					frappe.throw(_("Row {0}: Clock Out cannot be before Clock In").format(row.idx))
				row.hours = time_diff_in_hours(end, start)

		self.set_rates_from_crew()

		for row in self.entries:
			row.day_fraction = DAY_FRACTION.get(row.status, 0)
			row.wage = flt(row.daily_rate) * row.day_fraction

	def set_rates_from_crew(self, force=False):
		crew = get_crew_rates(self.project)
		for row in self.entries:
			if force or not row.daily_rate:
				info = crew.get(row.worker)
				if info:
					row.daily_rate = info.daily_rate
					row.role = row.role or info.role
				else:
					row.daily_rate = frappe.db.get_value("Site Worker", row.worker, "default_daily_rate")

	def calculate_totals(self):
		self.total_present = len([r for r in self.entries if r.status != "Absent"])
		self.total_payable_days = sum(flt(r.day_fraction) for r in self.entries)
		self.total_wages = sum(flt(r.wage) for r in self.entries)

	@frappe.whitelist()
	def load_crew(self):
		existing = {r.worker for r in self.entries}
		added = 0
		for member in get_active_crew(self.project, self.attendance_date):
			if member.worker in existing:
				continue
			self.append(
				"entries",
				{
					"worker": member.worker,
					"worker_name": member.worker_name,
					"role": member.role,
					"daily_rate": member.daily_rate,
					"status": "Absent",
				},
			)
			added += 1
		return added

	@frappe.whitelist()
	def clock(self, workers, action, location=None):
		"""Stamp server time on the selected workers. Called on a saved draft."""
		if self.docstatus != 0:
			frappe.throw(_("Register is already submitted"))
		if action not in ("in", "out"):
			frappe.throw(_("Invalid action"))
		if getdate(self.attendance_date) != getdate(nowdate()):
			frappe.throw(_("Clocking can only be done on the day of the register. Ask a Projects Manager to correct past times."))
		self.check_permission("write")

		workers = frappe.parse_json(workers) if isinstance(workers, str) else workers
		now = now_datetime().strftime("%H:%M:%S")
		done = []
		for row in self.entries:
			if row.worker not in workers:
				continue
			if action == "in" and not row.clock_in:
				row.clock_in = now
				row.clock_in_location = location
				row.status = "Present"
				done.append(row.worker_name)
			elif action == "out" and row.clock_in and not row.clock_out:
				row.clock_out = now
				row.clock_out_location = location
				done.append(row.worker_name)

		# permission already checked above; bypass only the permlevel reset so server time sticks
		self.flags.ignore_permissions = True
		self.save()
		return done


def get_crew_rates(project):
	rows = frappe.get_all(
		"Project Crew Member",
		filters={"parent": project, "parenttype": "Project", "parentfield": "sp_crew"},
		fields=["worker", "role", "daily_rate"],
	)
	return {r.worker: r for r in rows}


def get_active_crew(project, on_date):
	on_date = getdate(on_date)
	rows = frappe.get_all(
		"Project Crew Member",
		filters={"parent": project, "parenttype": "Project", "parentfield": "sp_crew"},
		fields=["worker", "worker_name", "role", "daily_rate", "joined_on", "left_on"],
		order_by="idx",
	)
	return [
		r
		for r in rows
		if (not r.joined_on or getdate(r.joined_on) <= on_date) and (not r.left_on or getdate(r.left_on) >= on_date)
	]
