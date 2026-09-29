"""How Frappe HR appears on the desk, kept in ms_hrms so Frappe HR's own files stay as
released.

- The "HR" desktop icon, which groups the HR workspaces and opens HR Setup, belongs to
  ms_hrms (desktop_icon/hr.json). Frappe HR ships its own "Frappe HR" icon, which opens
  a People workspace this site does not have; it is hidden, and any HR workspace icon it
  would group goes under "HR".
- The desk's app switcher opens HR Setup for Frappe HR instead of that missing workspace.

Icons are written with frappe.db.set_value: saving a standard icon in developer mode
would write its file back into the app it belongs to.
"""

import frappe

HR_ICON = "HR"
HR_ROUTE = "/desk/hr-setup"
FRAPPE_HR_ICON = "Frappe HR"


def after_migrate():
	if frappe.db.exists("Desktop Icon", HR_ICON):
		if frappe.db.get_value("Desktop Icon", HR_ICON, "app") != "ms_hrms":
			frappe.db.set_value("Desktop Icon", HR_ICON, "app", "ms_hrms", update_modified=False)
		for icon in frappe.get_all("Desktop Icon", filters={"parent_icon": FRAPPE_HR_ICON}, pluck="name"):
			frappe.db.set_value("Desktop Icon", icon, "parent_icon", HR_ICON, update_modified=False)

	if frappe.db.exists("Desktop Icon", FRAPPE_HR_ICON) and not frappe.db.get_value(
		"Desktop Icon", FRAPPE_HR_ICON, "hidden"
	):
		frappe.db.set_value("Desktop Icon", FRAPPE_HR_ICON, "hidden", 1, update_modified=False)

	frappe.cache.delete_key("desktop_icons")
	frappe.cache.delete_key("bootinfo")


def boot_session(bootinfo):
	for app in bootinfo.get("app_data") or []:
		if app.get("app_name") == "hrms":
			app["app_route"] = HR_ROUTE
