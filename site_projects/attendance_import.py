"""Bulk import of attendance kept on paper / spreadsheets before the system was in use."""

import datetime
from collections import OrderedDict

import frappe
from frappe import _
from frappe.utils import add_days, cstr, flt, getdate, nowdate

from site_projects.site_projects.doctype.site_attendance.site_attendance import get_crew_rates

TEMPLATE_COLUMNS = ["Date", "Worker", "Status", "Clock In", "Clock Out", "Daily Rate", "Role", "Remarks"]

STATUS_MAP = {
	"present": "Present", "p": "Present", "1": "Present", "1.0": "Present", "yes": "Present", "y": "Present",
	"x": "Present", "✓": "Present", "full": "Present", "full day": "Present",
	"half day": "Half Day", "half": "Half Day", "h": "Half Day", "0.5": "Half Day", "½": "Half Day", "1/2": "Half Day",
	"absent": "Absent", "a": "Absent", "0": "Absent", "0.0": "Absent", "no": "Absent", "n": "Absent",
}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _check_access():
	if not frappe.has_permission("Site Attendance", "submit"):
		frappe.throw(_("You are not allowed to submit attendance"), frappe.PermissionError)
	if 1 not in frappe.new_doc("Site Attendance").get_permlevel_access():
		frappe.throw(
			_("Only a Projects Manager can import past attendance, because it sets times and rates directly."),
			frappe.PermissionError,
		)


def _read_rows(file_url):
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	ext = (file_doc.file_name or file_url).rsplit(".", 1)[-1].lower()
	if ext == "xlsx":
		from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

		rows = read_xlsx_file_from_attached_file(fcontent=file_doc.get_content())
	elif ext == "csv":
		from frappe.utils.csvutils import read_csv_content

		rows = read_csv_content(file_doc.get_content())
	else:
		frappe.throw(_("Upload a .csv or .xlsx file"))

	rows = [r for r in rows if any(cstr(c).strip() for c in r)]
	if not rows:
		frappe.throw(_("The file is empty"))

	header = [cstr(h).strip().lower() for h in rows[0]]
	for required in ("date", "worker"):
		if required not in header:
			frappe.throw(_("Column {0} is missing. Download the template to see the expected columns.").format(required.title()))
	col = {name: header.index(name.lower()) if name.lower() in header else None for name in TEMPLATE_COLUMNS}

	out = []
	for line_no, r in enumerate(rows[1:], start=2):
		get = lambda name: r[col[name]] if col[name] is not None and col[name] < len(r) else None  # noqa: E731
		out.append({"line": line_no, **{name: get(name) for name in TEMPLATE_COLUMNS}})
	return out


def _parse_date(value):
	if isinstance(value, datetime.datetime):
		return value.date()
	if isinstance(value, datetime.date):
		return value
	return getdate(cstr(value).strip())


def _parse_time(value):
	if value in (None, ""):
		return None
	if isinstance(value, datetime.datetime):
		return value.strftime("%H:%M:%S")
	if isinstance(value, datetime.time):
		return value.strftime("%H:%M:%S")
	if isinstance(value, (int, float)):  # Excel fraction of a day
		seconds = round(flt(value) * 86400)
		return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
	text = cstr(value).strip().upper().replace(".", ":")
	for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
		try:
			return datetime.datetime.strptime(text, fmt).strftime("%H:%M:%S")
		except ValueError:
			continue
	raise ValueError(value)


def _worker_lookup():
	workers = frappe.get_all("Site Worker", fields=["name", "full_name", "id_number", "default_daily_rate", "skill"])
	by_key = {}
	for w in workers:
		for key in (w.name, w.id_number, w.full_name):
			if key:
				by_key.setdefault(cstr(key).strip().lower(), []).append(w)
	return by_key


def _validate(project, rows, create_missing_workers):
	errors = []
	lookup = _worker_lookup()
	crew = get_crew_rates(project)
	valid_roles = frappe.get_meta("Site Attendance Entry").get_field("role").options.split("\n")
	new_workers = OrderedDict()
	registers = OrderedDict()

	for row in rows:
		line = row["line"]
		err = lambda msg: errors.append(_("Line {0}: {1}").format(line, msg))  # noqa: E731

		try:
			date = _parse_date(row["Date"])
		except Exception:
			err(_("cannot read date '{0}'").format(row["Date"]))
			continue
		if date > getdate(nowdate()):
			err(_("{0} is in the future").format(date))
			continue

		worker_text = cstr(row["Worker"]).strip()
		if not worker_text:
			err(_("worker is blank"))
			continue
		matches = lookup.get(worker_text.lower(), [])
		if len(matches) > 1:
			err(_("'{0}' matches more than one worker ({1}); use the worker code or ID number").format(
				worker_text, ", ".join(m.name for m in matches)))
			continue
		worker = matches[0] if matches else None
		if not worker:
			if not create_missing_workers:
				err(_("worker '{0}' not found (tick 'Create missing workers' or add them first)").format(worker_text))
				continue
			worker = new_workers.setdefault(
				worker_text.lower(),
				frappe._dict(name=None, full_name=worker_text, default_daily_rate=0, skill=None),
			)

		try:
			clock_in, clock_out = _parse_time(row["Clock In"]), _parse_time(row["Clock Out"])
		except ValueError as e:
			err(_("cannot read time '{0}'").format(e.args[0]))
			continue
		if clock_out and not clock_in:
			err(_("has a Clock Out but no Clock In"))
			continue
		if clock_in and not clock_out:
			err(_("has a Clock In but no Clock Out"))
			continue

		status_text = cstr(row["Status"]).strip().lower()
		if status_text:
			status = STATUS_MAP.get(status_text) or (status_text.title() if status_text.title() in ("Present", "Half Day", "Absent") else None)
			if not status:
				err(_("unknown status '{0}' (use Present, Half Day or Absent)").format(row["Status"]))
				continue
		elif clock_in:
			status = "Present"
		else:
			err(_("needs a Status or Clock In/Out times"))
			continue

		role = cstr(row["Role"]).strip()
		if role and role not in valid_roles:
			err(_("unknown role '{0}'").format(role))
			continue

		rate = flt(row["Daily Rate"]) if cstr(row["Daily Rate"]).strip() else None
		if rate is None:
			member = crew.get(worker.name) if worker.name else None
			rate = flt(member.daily_rate) if member else flt(worker.default_daily_rate)
		if status != "Absent" and not rate:
			err(_("no Daily Rate for {0} (add it to the file, the project crew or the worker)").format(worker.full_name))
			continue
		if worker.name is None and not worker.default_daily_rate:
			worker.default_daily_rate = rate
			worker.skill = role or None

		key = worker.name or ("new:" + worker_text.lower())
		entries = registers.setdefault(date, OrderedDict())
		if key in entries:
			err(_("{0} appears twice on {1}").format(worker.full_name, frappe.format(date, "Date")))
			continue
		entries[key] = frappe._dict(
			worker_key=key, worker_name=worker.full_name, status=status, clock_in=clock_in, clock_out=clock_out,
			daily_rate=rate, role=role or (crew[worker.name].role if worker.name in crew else worker.skill),
			remarks=cstr(row["Remarks"]).strip() or None,
		)

	for date, entries in registers.items():
		if not any(e.status != "Absent" for e in entries.values()):
			errors.append(_("{0}: nobody is present").format(frappe.format(date, "Date")))

	if registers:
		existing = frappe.get_all(
			"Site Attendance",
			{"project": project, "docstatus": ["<", 2], "attendance_date": ["in", list(registers)]},
			["name", "attendance_date"],
		)
		for e in existing:
			errors.append(_("{0}: a register already exists ({1})").format(frappe.format(e.attendance_date, "Date"), e.name))

	return errors, registers, new_workers


@frappe.whitelist()
def import_attendance(project, file_url, create_missing_workers=0, dry_run=0):
	"""Validate the whole file first; create and submit one register per date only if every line is valid."""
	_check_access()
	frappe.has_permission("Project", "read", project, throw=True)
	if frappe.db.get_value("Project", project, "sp_stage") == "Closed":
		frappe.throw(_("Project {0} is closed").format(project))

	create_missing_workers = frappe.utils.cint(create_missing_workers)
	rows = _read_rows(file_url)
	errors, registers, new_workers = _validate(project, rows, create_missing_workers)

	summary = {
		"lines": len(rows),
		"days": len(registers),
		"new_workers": [w.full_name for w in new_workers.values()],
		"from_date": str(min(registers)) if registers else None,
		"to_date": str(max(registers)) if registers else None,
		"total_wages": sum(
			flt(e.daily_rate) * {"Present": 1, "Half Day": 0.5}.get(e.status, 0)
			for entries in registers.values() for e in entries.values()
		),
		"errors": errors,
		"created": [],
	}
	if errors or frappe.utils.cint(dry_run):
		return summary

	for key, w in new_workers.items():
		doc = frappe.get_doc(
			doctype="Site Worker", full_name=w.full_name, default_daily_rate=w.default_daily_rate,
			skill=w.skill or "Labourer",
		).insert()
		w.name = doc.name

	def worker_name_for(key):
		return new_workers[key[4:]].name if key.startswith("new:") else key

	for date, entries in sorted(registers.items()):
		doc = frappe.get_doc(
			doctype="Site Attendance",
			project=project,
			attendance_date=date,
			backfilled=1,
			entries=[
				{
					"worker": worker_name_for(e.worker_key),
					"status": e.status,
					"clock_in": e.clock_in,
					"clock_out": e.clock_out,
					"daily_rate": e.daily_rate,
					"role": e.role,
					"remarks": e.remarks or _("Imported from old records"),
				}
				for e in entries.values()
			],
		)
		doc.insert()
		doc.submit()
		summary["created"].append(doc.name)

	frappe.msgprint(
		_("{0} attendance registers imported").format(len(summary["created"])), indicator="green", alert=True
	)
	return summary


@frappe.whitelist()
def make_wage_sheets(project, from_date, to_date, week_starts_on="Monday"):
	"""Create one draft Weekly Wage Sheet per week that has unpaid, submitted attendance."""
	if not frappe.has_permission("Weekly Wage Sheet", "create"):
		frappe.throw(_("You are not allowed to create wage sheets"), frappe.PermissionError)
	if week_starts_on not in WEEKDAYS:
		frappe.throw(_("Invalid week start day"))

	from_date, to_date = getdate(from_date), getdate(to_date)
	start = add_days(from_date, -((from_date.weekday() - WEEKDAYS.index(week_starts_on)) % 7))

	created, skipped = [], []
	while getdate(start) <= to_date:
		week_end = add_days(start, 6)
		label = f"{frappe.format(start, 'Date')} – {frappe.format(week_end, 'Date')}"
		clash = frappe.db.sql(
			"""select name from `tabWeekly Wage Sheet` where project = %s and docstatus < 2
			and from_date <= %s and to_date >= %s limit 1""",
			(project, week_end, start),
		)
		has_unpaid = frappe.db.exists(
			"Site Attendance",
			{"project": project, "docstatus": 1, "wage_sheet": ["is", "not set"],
			 "total_wages": [">", 0], "attendance_date": ["between", [start, week_end]]},
		)
		if clash:
			skipped.append(_("{0}: already covered by {1}").format(label, clash[0][0]))
		elif has_unpaid:
			sheet = frappe.get_doc(doctype="Weekly Wage Sheet", project=project, from_date=start, to_date=week_end)
			sheet.insert()
			created.append({"name": sheet.name, "week": label, "total": sheet.total_amount})
		start = add_days(start, 7)

	frappe.clear_messages()  # drop per-sheet "draft attendance" notes; summary is returned instead
	return {"created": created, "skipped": skipped}
