// Bulk import of attendance kept before the system was in use, then draft wage sheets per week.
frappe.provide("site_projects");

site_projects.TEMPLATE_COLUMNS = ["Date", "Worker", "Status", "Clock In", "Clock Out", "Daily Rate", "Role", "Remarks"];

site_projects.download_attendance_template = function (project) {
	const rows = [site_projects.TEMPLATE_COLUMNS];
	const today = frappe.datetime.str_to_user(frappe.datetime.get_today());
	const add_examples = (crew) => {
		(crew.length ? crew : [{ worker_name: "Jane Doe", daily_rate: 800 }]).forEach((c, i) => {
			rows.push([today, c.worker_name || c.worker, i % 2 ? "Half Day" : "Present", "", "", c.daily_rate || "", c.role || "", ""]);
		});
		frappe.tools.downloadify(rows, null, __("Attendance Import Template"));
	};
	if (!project) return add_examples([]);
	frappe.db.get_doc("Project", project).then((p) => add_examples(p.sp_crew || []));
};

site_projects.import_attendance = function (project, on_done) {
	const d = new frappe.ui.Dialog({
		title: __("Import Past Attendance"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				options: `<p class="text-muted small">${__(
					"One row per worker per day. <b>Date</b> and <b>Worker</b> (name, worker code or ID number) are required. " +
						"<b>Status</b> is Present, Half Day or Absent (P / H / A, 1 / 0.5 / 0 also work). " +
						"Clock In/Out are optional. Daily Rate is optional and falls back to the project crew rate, then the worker's default. " +
						"Nothing is imported until every line is valid."
				)}</p>`,
			},
			{ fieldname: "project", fieldtype: "Link", options: "Project", label: __("Project"), reqd: 1, default: project, read_only: !!project },
			{
				fieldname: "template",
				fieldtype: "Button",
				label: __("Download Template"),
				click: () => site_projects.download_attendance_template(d.get_value("project")),
			},
			{ fieldname: "file_url", fieldtype: "Attach", label: __("File (.csv or .xlsx)"), reqd: 1 },
			{
				fieldname: "create_missing_workers",
				fieldtype: "Check",
				label: __("Create workers not yet in the system"),
				description: __("Otherwise unknown names are reported as errors"),
			},
			{ fieldname: "result", fieldtype: "HTML" },
		],
		primary_action_label: __("Check File"),
		primary_action(values) {
			run(values, 1);
		},
		secondary_action_label: __("Import"),
		secondary_action() {
			const values = d.get_values();
			if (!values) return;
			frappe.confirm(__("Create and submit attendance registers from this file?"), () => run(values, 0));
		},
	});

	const run = (values, dry_run) => {
		frappe
			.call({
				method: "site_projects.attendance_import.import_attendance",
				args: { ...values, dry_run },
				freeze: true,
				freeze_message: dry_run ? __("Checking file...") : __("Importing attendance..."),
			})
			.then(({ message: s }) => {
				d.fields_dict.result.$wrapper.html(render_summary(s, dry_run));
				if (!dry_run && s.created.length) {
					d.set_primary_action(__("Create Wage Sheets"), () => {
						d.hide();
						site_projects.make_wage_sheets(values.project, s.from_date, s.to_date, on_done);
					});
					d.get_secondary_btn().addClass("hide");
					on_done && on_done();
				}
			});
	};
	d.show();
};

function render_summary(s, dry_run) {
	const money = (v) => format_currency(v, frappe.defaults.get_default("currency"));
	if (s.errors.length) {
		return `<div class="alert alert-danger">
			<b>${__("{0} problem(s) found. Nothing was imported.", [s.errors.length])}</b>
			<ul class="mt-2 mb-0" style="max-height:260px;overflow:auto">${s.errors
				.map((e) => `<li>${frappe.utils.escape_html(e)}</li>`)
				.join("")}</ul></div>`;
	}
	const range = s.from_date
		? `${frappe.datetime.str_to_user(s.from_date)} – ${frappe.datetime.str_to_user(s.to_date)}`
		: "";
	const new_workers = s.new_workers.length
		? `<li>${__("New workers to be created")}: ${s.new_workers.map(frappe.utils.escape_html).join(", ")}</li>`
		: "";
	const head = dry_run
		? `<b>${__("File looks good.")}</b> ${__("Click Import to create the registers.")}`
		: `<b>${__("{0} registers imported and submitted.", [s.created.length])}</b> ${__(
				"Click Create Wage Sheets to prepare the weekly pay."
		  )}`;
	return `<div class="alert alert-success">${head}<ul class="mt-2 mb-0">
		<li>${__("Lines")}: ${s.lines} · ${__("Days")}: ${s.days} (${range})</li>
		<li>${__("Total wages")}: ${money(s.total_wages)}</li>${new_workers}</ul></div>`;
}

site_projects.make_wage_sheets = function (project, from_date, to_date, on_done) {
	const d = new frappe.ui.Dialog({
		title: __("Create Weekly Wage Sheets"),
		fields: [
			{ fieldname: "project", fieldtype: "Link", options: "Project", label: __("Project"), reqd: 1, default: project },
			{ fieldname: "from_date", fieldtype: "Date", label: __("From"), reqd: 1, default: from_date },
			{ fieldname: "to_date", fieldtype: "Date", label: __("To"), reqd: 1, default: to_date || frappe.datetime.get_today() },
			{
				fieldname: "week_starts_on",
				fieldtype: "Select",
				label: __("Pay week starts on"),
				options: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
				default: "Monday",
			},
		],
		primary_action_label: __("Create Draft Wage Sheets"),
		primary_action(values) {
			frappe
				.call({ method: "site_projects.attendance_import.make_wage_sheets", args: values, freeze: true })
				.then(({ message: r }) => {
					d.hide();
					const money = (v) => format_currency(v, frappe.defaults.get_default("currency"));
					const list = r.created
						.map((c) => `<li><a href="/app/weekly-wage-sheet/${c.name}">${c.name}</a> · ${c.week} · ${money(c.total)}</li>`)
						.join("");
					const skipped = r.skipped.length
						? `<p class="mt-3 text-muted">${__("Skipped")}:</p><ul>${r.skipped
								.map((x) => `<li>${frappe.utils.escape_html(x)}</li>`)
								.join("")}</ul>`
						: "";
					frappe.msgprint({
						title: __("Wage Sheets"),
						indicator: r.created.length ? "green" : "orange",
						message:
							(r.created.length
								? `<p>${__("Draft wage sheets created. Review each one, add payment references and submit.")}</p><ul>${list}</ul>`
								: `<p>${__("No weeks with unpaid attendance were found.")}</p>`) + skipped,
					});
					on_done && on_done();
				});
		},
	});
	d.show();
};

// --- entry points
frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.sp_stage === "Closed") return;
		frm.add_custom_button(__("Import Past Attendance"), () => site_projects.import_attendance(frm.doc.name, () => frm.reload_doc()), __("Site"));
		frm.add_custom_button(__("Create Wage Sheets"), () => site_projects.make_wage_sheets(frm.doc.name), __("Site"));
	},
});

if (!frappe.listview_settings["Site Attendance"]) frappe.listview_settings["Site Attendance"] = {};
Object.assign(frappe.listview_settings["Site Attendance"], {
	onload(listview) {
		if (!frappe.user.has_role(["Projects Manager", "System Manager"])) return;
		listview.page.add_inner_button(__("Import Past Attendance"), () =>
			site_projects.import_attendance(null, () => listview.refresh())
		);
	},
});
