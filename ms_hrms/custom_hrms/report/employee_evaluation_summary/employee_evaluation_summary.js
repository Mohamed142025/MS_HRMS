frappe.query_reports["Employee Evaluation Summary"] = {
	filters: [
		{ fieldname: "payroll_period", label: __("الفترة"), fieldtype: "Link", options: "Payroll Period" },
		{ fieldname: "department", label: __("القسم"), fieldtype: "Link", options: "Department" },
		{
			fieldname: "status",
			label: __("الحالة"),
			fieldtype: "Select",
			options: ["", "بانتظار تقييم المدير", "بانتظار الموارد البشرية", "معتمد"],
		},
	],
};
