"""Check-ins from the employee app: at the site's time, and from the employee's own phone.

- Time: an employee checking themselves in is checked in at the site's clock (Africa/Cairo,
  synchronised), whatever their phone's clock says. HR adding a check-in for an employee,
  and the biometric device's imports, keep the time they give.
- Device: the app keeps a random id for the phone it runs on. The first phone an employee
  opens the app on (or checks in from) becomes their registered device (Employee > App
  Check-in Device). On another phone the app is closed to them and a check-in is blocked
  or, as HR Settings may say instead, recorded and marked for review, until HR resets the
  registered device on the employee. The desk is not affected.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

DEVICE_FIELD = "custom_checkin_device"
DEVICE_NAME_FIELD = "custom_checkin_device_name"
DEVICE_SINCE_FIELD = "custom_checkin_device_since"
POLICY_FIELD = "custom_checkin_other_device"
BLOCK = "Block the App and Check-in"
REVIEW = "Allow and Mark for Review"
# The values before they were named for what they do.
OLD_VALUES = {"Block": BLOCK, "Record for Review": REVIEW}


def setup():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Employee": [
				{
					"fieldname": "custom_checkin_device_section",
					"fieldtype": "Section Break",
					"label": "App Check-in Device",
					"insert_after": "attendance_device_id",
					"collapsible": 1,
					"description": "The phone the employee checks in from in the app: the first one they check in from. HR resets it when the employee changes phones.",
				},
				{
					"fieldname": DEVICE_NAME_FIELD,
					"fieldtype": "Data",
					"label": "Registered Device",
					"read_only": 1,
					"insert_after": "custom_checkin_device_section",
				},
				{
					"fieldname": DEVICE_SINCE_FIELD,
					"fieldtype": "Datetime",
					"label": "Registered On",
					"read_only": 1,
					"insert_after": DEVICE_NAME_FIELD,
				},
				{
					"fieldname": DEVICE_FIELD,
					"fieldtype": "Data",
					"label": "Registered Device ID",
					"read_only": 1,
					"hidden": 1,
					"insert_after": DEVICE_SINCE_FIELD,
				},
			],
			"Employee Checkin": [
				{
					"fieldname": "custom_device_check",
					"fieldtype": "Select",
					"label": "Device Check",
					"options": "\nRegistered Device\nDevice Registered Now\nOther Device",
					"read_only": 1,
					"in_standard_filter": 1,
					"insert_after": "device_id",
				},
				{
					"fieldname": "custom_app_device_name",
					"fieldtype": "Data",
					"label": "App Device",
					"read_only": 1,
					"insert_after": "custom_device_check",
				},
				{
					"fieldname": "custom_app_device",
					"fieldtype": "Data",
					"label": "App Device ID",
					"read_only": 1,
					"hidden": 1,
					"insert_after": "custom_app_device_name",
				},
			],
			"HR Settings": [
				{
					"fieldname": POLICY_FIELD,
					"fieldtype": "Select",
					"label": "Check-in From Another Phone",
					"options": f"{BLOCK}\n{REVIEW}",
					"default": BLOCK,
					"description": "When an employee opens the app on a phone other than their registered one. Blocked: the app is closed to them and they cannot check in until HR resets their device. Allowed: they use the app and check in, and the check-in is marked Other Device for HR to review.",
					"insert_after": "allow_geolocation_tracking",
				},
			],
		},
		update=True,
	)
	value = frappe.db.get_single_value("HR Settings", POLICY_FIELD)
	if value not in (BLOCK, REVIEW):
		frappe.db.set_single_value("HR Settings", POLICY_FIELD, OLD_VALUES.get(value, BLOCK))


def is_self_checkin(doc):
	"""An employee checking themselves in (the app), not HR nor an import."""
	user = frappe.session.user
	return (
		user not in ("Administrator", "Guest")
		and not doc.get("custom_biometric_import")
		and frappe.db.get_value("Employee", doc.employee, "user_id") == user
	)


def device_state(employee, device):
	"""registered, new (no registered phone yet) or other."""
	registered = frappe.db.get_value("Employee", employee, DEVICE_FIELD)
	if not registered:
		return "new"
	return "registered" if device and device == registered else "other"


def before_insert(doc, method=None):
	if not is_self_checkin(doc):
		return
	# The site's clock, not the phone's.
	doc.time = now_datetime()

	device = (doc.get("custom_app_device") or "").strip()[:140]
	doc.custom_app_device = device
	if not device:
		# An app version from before devices were checked: reopened, it sends one.
		frappe.throw(_("Close the app and open it again, then check in."))
	doc.custom_app_device_name = (doc.get("custom_app_device_name") or "").strip()[:140]
	state = device_state(doc.employee, device)

	if state == "new":
		register(doc.employee, device, doc.custom_app_device_name)
		doc.custom_device_check = "Device Registered Now"
	elif state == "registered":
		doc.custom_device_check = "Registered Device"
	else:
		if frappe.db.get_single_value("HR Settings", POLICY_FIELD) != REVIEW:
			# Recorded on the employee for HR, apart from this request, which fails.
			frappe.enqueue(
				record_blocked_attempt,
				queue="short",
				employee=doc.employee,
				device_name=doc.custom_app_device_name,
				log_type=doc.log_type,
			)
			frappe.throw(
				_("This phone is not your registered device for check-in. Ask HR to register it."),
				title=_("Another Phone"),
			)
		doc.custom_device_check = "Other Device"


def register(employee, device, device_name):
	frappe.db.set_value(
		"Employee",
		employee,
		{DEVICE_FIELD: device, DEVICE_NAME_FIELD: (device_name or "")[:140], DEVICE_SINCE_FIELD: now_datetime()},
		update_modified=False,
	)


@frappe.whitelist(methods=["POST"])
def register_device(device=None, device_name=None):
	"""When the app opens: the phone becomes the employee's registered device for check-in
	if they have none yet. On another phone the app is closed to them (blocked), unless HR
	Settings records check-ins from other phones for review instead. Returns the phone's
	state: registered (this phone), new (registered now) or other."""
	from hrms.api import get_current_employee

	device = (device or "").strip()[:140]
	employee = get_current_employee()
	if not employee or not device:
		return {"state": None, "blocked": False}
	state = device_state(employee, device)
	if state == "new":
		register(employee, device, device_name)
	blocked = state == "other" and frappe.db.get_single_value("HR Settings", POLICY_FIELD) != REVIEW
	if blocked:
		frappe.get_doc("Employee", employee).add_comment(
			"Info", _("App opened on another phone ({0}) and closed to the employee.").format(device_name or _("unknown"))
		)
	return {"state": state, "blocked": blocked}


def record_blocked_attempt(employee, device_name, log_type):
	frappe.get_doc("Employee", employee).add_comment(
		"Info",
		_("Check-in ({0}) blocked: from another phone ({1}).").format(_(log_type or "IN"), device_name or _("unknown")),
	)


@frappe.whitelist()
def get_checkin_context(device=None):
	"""For the app's check-in sheet: the site's time, and whether this phone may check in."""
	from hrms.api import get_current_employee

	employee = get_current_employee()
	state = device_state(employee, device) if employee else "new"
	return {
		"now": str(now_datetime()),
		"device": state,
		"blocked": state == "other" and frappe.db.get_single_value("HR Settings", POLICY_FIELD) != REVIEW,
	}


@frappe.whitelist(methods=["POST"])
def reset_device(employee):
	"""HR: the employee's next check-in registers the phone it is made from."""
	from ms_hrms.request_approvers import sees_all

	if not sees_all(frappe.session.user):
		frappe.throw(_("Only HR may reset an employee's check-in device."), frappe.PermissionError)
	old = frappe.db.get_value("Employee", employee, DEVICE_NAME_FIELD)
	frappe.db.set_value("Employee", employee, {DEVICE_FIELD: None, DEVICE_NAME_FIELD: None, DEVICE_SINCE_FIELD: None})
	frappe.get_doc("Employee", employee).add_comment(
		"Info", _("Check-in device reset (was {0}). The next phone checked in from is registered.").format(old or _("none"))
	)
