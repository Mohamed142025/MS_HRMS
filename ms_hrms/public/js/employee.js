// The phone the employee checks in from in the app (checkin_guard.py): HR resets it when
// the employee changes phones, and the next one they check in from is registered.
frappe.ui.form.on("Employee", {
	refresh(frm) {
		if (frm.is_new() || !frm.doc.custom_checkin_device_name) return;
		if (!frappe.user.has_role(["HR Manager", "HR User", "System Manager"])) return;
		frm.add_custom_button(__("Reset Check-in Device"), () =>
			frappe.confirm(
				__("Reset {0}'s check-in device? The next phone they check in from will be registered.", [frm.doc.employee_name]),
				() =>
					frappe.call({
						method: "ms_hrms.checkin_guard.reset_device",
						args: { employee: frm.doc.name },
						freeze: true,
						callback: () => frm.reload_doc(),
					})
			)
		);
	},
});
