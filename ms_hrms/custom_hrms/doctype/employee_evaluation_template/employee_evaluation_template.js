// An item's part is chosen from the parts defined above it.
frappe.ui.form.on("Employee Evaluation Template", {
	refresh: set_part_options,
	parts_remove: set_part_options,
});

frappe.ui.form.on("Employee Evaluation Template Part", {
	part_name: set_part_options,
});

function set_part_options(frm) {
	const names = (frm.doc.parts || []).map((row) => row.part_name).filter(Boolean);
	frm.fields_dict.items.grid.update_docfield_property("part", "options", names);
}
