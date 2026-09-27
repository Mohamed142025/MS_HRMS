frappe.listview_settings["Biometric Import"] = {
	add_fields: ["status", "pending"],
	get_indicator(doc) {
		const colors = { "مسودة": "gray", "جاري الاستيراد": "blue", "تم الاستيراد": "green", "مستني أكواد": "orange" };
		return [__(doc.status), colors[doc.status] || "gray", `status,=,${doc.status}`];
	},
};
