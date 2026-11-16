// Copyright (c) 2026, Mohamed Sayed and contributors
// For license information, please see license.txt

frappe.ui.form.on("Annual Increment", {
	setup(frm) {
		frm.set_query("department", () => ({ filters: { company: frm.doc.company } }));
		frm.set_query("employee", () => ({ filters: { company: frm.doc.company, status: "Active" } }));
		frm.set_query("salary_component", "components", () => ({ filters: { disabled: 0 } }));
	},

	refresh(frm) {
		frm.events.toggle_current_amount(frm);
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(__("Old and New Salaries"), () =>
				frappe.set_route("query-report", "Annual Increment Comparison", { annual_increment: frm.doc.name })
			);
		}
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Employees"), () => {
				frm.call({ doc: frm.doc, method: "get_employees", freeze: true })
					.then(() => frm.events.get_salary_components(frm))
					.then(() => frm.dirty());
			});
		}
	},

	apply_to(frm) {
		frm.set_value({ employee: null, department: null, grade: null });
		frm.events.toggle_current_amount(frm);
	},

	// The current amount is one employee's; for a department or a grade it is not shown.
	toggle_current_amount(frm) {
		const grid = frm.fields_dict.components.grid;
		grid.update_docfield_property("current_amount", "hidden", frm.doc.apply_to !== "Employee");
		grid.update_docfield_property("current_amount", "in_list_view", frm.doc.apply_to === "Employee" ? 1 : 0);
		grid.visible_columns = null;
		grid.reset_grid?.();
		frm.refresh_field("components");
	},

	// The employee's salary components fill the table, at 0 until an increase is entered.
	employee(frm) {
		if (frm.doc.employee) frm.events.get_salary_components(frm);
	},

	get_salary_components(frm) {
		return frm.call({ doc: frm.doc, method: "get_salary_components", freeze: true }).then(() => {
			frm.refresh_field("components");
			frm.refresh_field("employees");
		});
	},

	// What submitting does, before it is done.
	before_submit(frm) {
		const rows = frm.doc.employees || [];
		const toCancel = rows.filter((row) => row.assignments_to_cancel);
		let message = __("Submitting gives {0} employees a new salary structure and a new Salary Structure Assignment from {1}.", [
			rows.length,
			frappe.datetime.str_to_user(frm.doc.effective_date),
		]);
		if (toCancel.length) {
			const list = toCancel
				.map((row) => `<li>${frappe.utils.escape_html(row.employee_name || row.employee)}: ${frappe.utils.escape_html(row.assignments_to_cancel).replace(/\n/g, "، ")}</li>`)
				.join("");
			message += `<br><br>${__("These assignments, from the effective date on, will be cancelled:")}<ul>${list}</ul>`;
		}
		message += `<br>${__("Continue?")}`;
		return new Promise((resolve, reject) => {
			frappe.confirm(message, resolve, () => reject(new Error(__("Not submitted"))));
		});
	},
});
