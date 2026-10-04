frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.is_new()) return;
		const closed = frm.doc.sp_stage === "Closed";
		const group = __("Site");

		if (!closed) {
			frm.add_custom_button(__("Send Materials"), () => make_stock_entry(frm, "Material Issue"), group);
			frm.add_custom_button(__("Return Materials"), () => make_stock_entry(frm, "Material Receipt"), group);
			frm.add_custom_button(
				__("Daily Attendance"),
				() =>
					frappe.new_doc("Site Attendance", {
						project: frm.doc.name,
						attendance_date: frappe.datetime.get_today(),
					}),
				group
			);
			frm.add_custom_button(
				__("Weekly Wage Sheet"),
				() => frappe.new_doc("Weekly Wage Sheet", { project: frm.doc.name }),
				group
			);
			if (["In Progress", "Completed"].includes(frm.doc.sp_stage)) {
				frm.add_custom_button(__("Close Project"), () => close_project(frm), group);
			}
		}

		const colours = {
			Scoping: "gray",
			"Contract Sent": "orange",
			"Contract Signed": "blue",
			"In Progress": "yellow",
			Completed: "green",
			Closed: "darkgrey",
		};
		if (frm.doc.sp_stage) {
			frm.page.set_indicator(__(frm.doc.sp_stage), colours[frm.doc.sp_stage] || "gray");
		}

		render_material_movements(frm);
	},
});

frappe.ui.form.on("Project Scope Item", {
	qty: calc_scope,
	rate: calc_scope,
	sp_scope_items_remove: calc_scope,
});

frappe.ui.form.on("Project Crew Member", {
	worker(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.worker) return;
		frappe.db
			.get_value("Site Worker", row.worker, ["default_daily_rate", "skill"])
			.then(({ message }) => {
				if (!row.daily_rate) frappe.model.set_value(cdt, cdn, "daily_rate", message.default_daily_rate);
				if (!row.role || row.role === "Labourer") frappe.model.set_value(cdt, cdn, "role", message.skill);
				if (!row.joined_on) frappe.model.set_value(cdt, cdn, "joined_on", frappe.datetime.get_today());
			});
	},
});

frappe.ui.form.on("Project Activity", {
	status(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const today = frappe.datetime.get_today();
		if (row.status === "In Progress" && !row.started_on) frappe.model.set_value(cdt, cdn, "started_on", today);
		if (row.status === "Done" && !row.completed_on) frappe.model.set_value(cdt, cdn, "completed_on", today);
	},
});

function calc_scope(frm, cdt, cdn) {
	if (cdt && cdn && locals[cdt][cdn]) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	}
	const total = (frm.doc.sp_scope_items || []).reduce((s, r) => s + flt(r.qty) * flt(r.rate), 0);
	frm.set_value("sp_scoped_total", total);
}

function make_stock_entry(frm, purpose) {
	frappe.model.with_doctype("Stock Entry", () => {
		const se = frappe.model.get_new_doc("Stock Entry");
		se.stock_entry_type = purpose;
		se.purpose = purpose;
		se.company = frm.doc.company;
		se.project = frm.doc.name;
		se.remarks =
			(purpose === "Material Issue" ? __("Sent to site: {0}") : __("Returned from site: {0}")).replace(
				"{0}",
				frm.doc.project_name
			);
		frappe.set_route("Form", "Stock Entry", se.name);
	});
}

function close_project(frm) {
	const open = (frm.doc.sp_activities || []).filter((r) => r.status !== "Done");
	const d = new frappe.ui.Dialog({
		title: __("Close Project"),
		fields: [
			{
				fieldtype: "HTML",
				options: open.length
					? `<div class="alert alert-warning">${__("Activities not yet Done")}: ${open
							.map((r) => frappe.utils.escape_html(r.activity))
							.join(", ")}</div>`
					: "",
			},
			{ fieldname: "closure_notes", fieldtype: "Small Text", label: __("Closure Notes"), default: frm.doc.sp_closure_notes },
		],
		primary_action_label: __("Close Project"),
		primary_action(values) {
			frappe
				.call("site_projects.project.close_project", {
					project: frm.doc.name,
					closure_notes: values.closure_notes,
				})
				.then(() => {
					d.hide();
					frm.reload_doc();
				});
		},
	});
	d.show();
}

function render_material_movements(frm) {
	const field = frm.get_field("sp_materials_html");
	if (!field) return;
	frappe.call("site_projects.project.get_material_movements", { project: frm.doc.name }).then(({ message }) => {
		const rows = message || [];
		if (!rows.length) {
			field.html(`<p class="text-muted">${__("No materials have been sent to this project yet.")}</p>`);
			return;
		}
		const fmt = (v) => format_currency(v, frappe.defaults.get_default("currency"));
		let body = "";
		let last = null;
		for (const r of rows) {
			const is_return = r.purpose === "Material Receipt";
			const head = r.name !== last;
			last = r.name;
			body += `<tr${head ? ' style="border-top:2px solid var(--border-color)"' : ""}>
				<td>${head ? frappe.datetime.str_to_user(r.posting_date) : ""}</td>
				<td>${head ? `<a href="/app/stock-entry/${encodeURIComponent(r.name)}">${r.name}</a>` : ""}</td>
				<td>${head ? (is_return ? `<span class="indicator-pill green">${__("Returned")}</span>` : `<span class="indicator-pill orange">${__("Sent")}</span>`) : ""}</td>
				<td>${frappe.utils.escape_html(r.item_name || r.item_code)}</td>
				<td class="text-right">${is_return ? "-" : ""}${format_number(r.qty)} ${r.uom || ""}</td>
				<td class="text-right">${fmt(r.basic_rate)}</td>
				<td class="text-right">${is_return ? "-" : ""}${fmt(r.amount)}</td>
			</tr>`;
		}
		field.html(`
			<div class="table-responsive">
			<table class="table table-sm table-bordered">
				<thead><tr>
					<th>${__("Date")}</th><th>${__("Entry")}</th><th></th><th>${__("Item")}</th>
					<th class="text-right">${__("Qty")}</th><th class="text-right">${__("Rate")}</th>
					<th class="text-right">${__("Value")}</th>
				</tr></thead>
				<tbody>${body}</tbody>
				<tfoot><tr>
					<th colspan="6" class="text-right">${__("Net value on site")}</th>
					<th class="text-right">${fmt(flt(frm.doc.sp_material_issued) - flt(frm.doc.sp_material_returned))}</th>
				</tr></tfoot>
			</table></div>`);
	});
}
