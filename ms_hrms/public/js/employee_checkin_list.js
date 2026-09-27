// «استيراد البصمة»: the device's sheet as it is, through Biometric Import. HRMS's own list
// settings (Fetch Shifts, the off-shift indicator) are kept.
(() => {
	const settings = (frappe.listview_settings["Employee Checkin"] ||= {});
	const hrms_onload = settings.onload;
	settings.onload = function (list) {
		if (hrms_onload) hrms_onload.call(this, list);
		if (!frappe.model.can_create("Biometric Import")) return;
		list.page.add_inner_button(__("استيراد البصمة"), () => frappe.new_doc("Biometric Import"));
	};
})();
