frappe.query_reports["Daily Shift Attendance"] = {
	filters: [
		{
			fieldname: "date",
			label: __("Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
		{ fieldname: "shift_type", label: __("Shift Type"), fieldtype: "Link", options: "Shift Type" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			// Who has not come in, by default: not in yet, or absent.
			options: [
				{ value: "missing", label: __("Not in yet or absent") },
				{ value: "", label: __("All") },
				{ value: "not_in", label: __("Not in yet") },
				{ value: "absent", label: __("Absent") },
				{ value: "permission", label: __("Late arrival permission") },
				{ value: "upcoming", label: __("Shift not started") },
				{ value: "present", label: __("Present") },
				{ value: "on_duty", label: __("On duty") },
				{ value: "on_leave", label: __("On Leave") },
				{ value: "holiday", label: __("Holiday") },
				{ value: "no_shift", label: __("No shift") },
			],
			default: "missing",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data)
		if (column.fieldname === "status_label" && data) {
			const color = { not_in: "red", absent: "red", permission: "orange", upcoming: "blue", present: "green", no_shift: "gray" }[data.status] || "gray"
			value = `<span class="indicator-pill ${color}">${value}</span>`
		}
		if (column.fieldname === "phone" && data?.phone) {
			value = `<a href="tel:${encodeURIComponent(data.phone)}">${frappe.utils.escape_html(data.phone)}</a>`
		}
		return value
	},
}
