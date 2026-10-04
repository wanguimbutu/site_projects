// Copyright (c) 2026, wangui and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Attendance", {
	setup(frm) {
		frm.set_query("project", () => ({
			filters: { sp_stage: ["not in", ["Closed"]] },
		}));
	},

	refresh(frm) {
		if (frm.doc.docstatus !== 0) return;

		frm.add_custom_button(__("Load Crew"), () => {
			if (!frm.doc.project) {
				frappe.msgprint(__("Select a project first"));
				return;
			}
			frm.call("load_crew").then((r) => {
				frm.refresh_field("entries");
				frm.dirty();
				frappe.show_alert(__("{0} crew member(s) added", [r.message || 0]));
			});
		});

		if (frm.is_new() || !frm.doc.entries?.length) return;

		const is_today = frm.doc.attendance_date === frappe.datetime.get_today();
		if (!is_today) {
			frm.dashboard.set_headline(
				__("Clock buttons only work on the day of the register. Past times can be corrected by a Projects Manager."),
				"orange"
			);
			return;
		}

		const not_in = frm.doc.entries.filter((r) => !r.clock_in);
		const not_out = frm.doc.entries.filter((r) => r.clock_in && !r.clock_out);

		if (not_in.length) {
			frm.add_custom_button(__("Clock In"), () => clock_dialog(frm, "in", not_in)).addClass("btn-primary");
		}
		if (not_out.length) {
			frm.add_custom_button(__("Clock Out"), () => clock_dialog(frm, "out", not_out)).addClass(
				not_in.length ? "" : "btn-primary"
			);
		}
	},

	project(frm) {
		if (frm.doc.project && !(frm.doc.entries || []).length) {
			frm.trigger("refresh");
		}
	},
});

function clock_dialog(frm, action, rows) {
	const label = action === "in" ? __("Clock In") : __("Clock Out");
	const d = new frappe.ui.Dialog({
		title: label,
		fields: [
			{
				fieldname: "workers",
				fieldtype: "MultiCheck",
				label: __("Workers"),
				select_all: 1,
				columns: 1,
				options: rows.map((r) => ({
					label: `${r.worker_name || r.worker}${r.clock_in ? " (in " + r.clock_in.slice(0, 5) + ")" : ""}`,
					value: r.worker,
				})),
			},
		],
		primary_action_label: label,
		primary_action(values) {
			if (!values.workers?.length) {
				frappe.msgprint(__("Tick at least one worker"));
				return;
			}
			d.hide();
			get_location().then((location) => {
				frm.call("clock", { workers: values.workers, action, location }).then((r) => {
					frm.reload_doc();
					frappe.show_alert({
						message: __("{0}: {1}", [label, (r.message || []).join(", ")]),
						indicator: "green",
					});
				});
			});
		},
	});
	d.show();
}

function get_location() {
	return new Promise((resolve) => {
		if (!navigator.geolocation) return resolve(null);
		navigator.geolocation.getCurrentPosition(
			(pos) => resolve(`${pos.coords.latitude.toFixed(5)},${pos.coords.longitude.toFixed(5)}`),
			() => resolve(null),
			{ timeout: 8000 }
		);
	});
}
