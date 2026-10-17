frappe.listview_settings["Employee Evaluation"] = {
	add_fields: ["status"],
	has_indicator_for_draft: 1,
	has_indicator_for_cancelled: 1,
	get_indicator(doc) {
		const colors = {
			"بانتظار تقييم المدير": "orange",
			"بانتظار الموارد البشرية": "blue",
			معتمد: "green",
			ملغي: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
	onload(listview) {
		if (!frappe.model.can_create("Employee Evaluation")) return;
		listview.page.add_inner_button(__("إنشاء تقييمات الفترة"), () => {
			frappe.prompt(
				{
					fieldname: "payroll_period",
					fieldtype: "Link",
					options: "Payroll Period",
					label: __("الفترة"),
					reqd: 1,
				},
				({ payroll_period }) => {
					frappe
						.call({
							method: "ms_hrms.custom_hrms.doctype.employee_evaluation.employee_evaluation.create_evaluations",
							args: { payroll_period },
							freeze: true,
							freeze_message: __("جاري إنشاء التقييمات..."),
						})
						.then(({ message: r }) => {
							const list = (title, names) =>
								names.length
									? `<p><b>${title} (${names.length})</b><br>${names
											.map((n) => frappe.utils.escape_html(n))
											.join("<br>")}</p>`
									: "";
							frappe.msgprint({
								title: __("تقييمات الفترة {0}", [payroll_period]),
								indicator: "green",
								message:
									`<p>${__("أُنشئ {0} تقييم.", [r.created.length])}</p>` +
									list(__("بدون قالب تقييم، فلم يُنشأ لهم تقييم"), r.no_template) +
									list(__("بدون مقيِّم له مستخدم: حدد المقيِّم في التقييم"), r.no_evaluator) +
									list(__("بدون مبلغ حافز في تعيين هيكل الراتب"), r.no_incentive),
							});
							listview.refresh();
						});
				},
				__("إنشاء تقييمات الفترة"),
				__("إنشاء")
			);
		});
	},
};
