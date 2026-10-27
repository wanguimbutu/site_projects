frappe.provide("site_projects");

frappe.listview_settings["Weekly Wage Sheet"] = {
	onload(listview) {
		listview.page.add_actions_menu_item(__("Export to Excel"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) {
				frappe.msgprint(__("Tick the wage sheets to export"));
				return;
			}
			window.open(
				"/api/method/site_projects.wage_export.export_wage_sheets?names=" +
					encodeURIComponent(JSON.stringify(names))
			);
		});
	},
};
