// Copyright (c) 2026, Mohamed Sayed and contributors
// For license information, please see license.txt

frappe.query_reports["Annual Increment Comparison"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
		{
			fieldname: "annual_increment",
			label: __("Annual Increment"),
			fieldtype: "Link",
			options: "Annual Increment",
			get_query: () => ({ filters: { docstatus: 1 } }),
		},
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
		{ fieldname: "grade", label: __("Grade"), fieldtype: "Link", options: "Employee Grade" },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "show_components", label: __("Show Components"), fieldtype: "Check", default: 1 },
	],

	// Increases in green, decreases in red.
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && /_(diff|pct)$/.test(column.fieldname) && data[column.fieldname]) {
			const color = data[column.fieldname] > 0 ? "var(--green-600)" : "var(--red-600)";
			value = `<span style="color:${color};font-weight:600">${value}</span>`;
		}
		return value;
	},
};
