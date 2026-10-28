"""Who has not come in: the employee app's Not Checked In screen, the Daily Shift
Attendance report and the notification to HR after each shift starts.

For a day, every active employee is looked at with their shift: the Shift Assignment
active that day or, without one, the Default Shift on the employee. Employees with
neither are counted apart ("no shift"). With a shift, an employee is:

- holiday: the day is a holiday on the shift's holiday list, or the employee's;
- on leave: an approved leave covers the day, or attendance says On Leave;
- on duty: an approved Attendance Request covers the day (on duty, work from home);
- present: a check-in from the shift's check-in window (its start less "Begin check-in
  before shift start time", to its end), or Present / Half Day / Work From Home
  attendance;
- upcoming: the shift has not started yet;
- permission: an approved Late Arrival permission that day, until it ends;
- not in: none of the above once the shift has started (absent, for a past day, or
  when attendance says Absent).

The System Manager (and Administrator) and the roles in HR Settings > Roles That Watch
Attendance see it (HR Manager and HR User when it is set up). When HR Settings > Notify
Who Has Not Checked In is on, those users get one notification per shift each day, the
set number of minutes after it starts, of how many have not come in.
"""

from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, get_datetime, getdate, now_datetime

from hrms.utils.holiday_list import get_holiday_list_for_employee

SEES_ALL = "System Manager"
ROLES_FIELD = "custom_roles_that_watch_attendance"
NOTIFY_FIELD = "custom_notify_not_checked_in"
NOTIFY_AFTER_FIELD = "custom_not_checked_in_notify_after"
ROLES_BY_DEFAULT = ("HR Manager", "HR User")
NOTIFY_AFTER_BY_DEFAULT = 15

# The statuses, in the order lists and the report show them.
STATUSES = ("not_in", "absent", "permission", "upcoming", "present", "on_duty", "on_leave", "holiday", "no_shift")
STATUS_LABELS = {
	"not_in": "Not in yet",
	"absent": "Absent",
	"permission": "Late arrival permission",
	"upcoming": "Shift not started",
	"present": "Present",
	"on_duty": "On duty",
	"on_leave": "On Leave",
	"holiday": "Holiday",
	"no_shift": "No shift",
}
PRESENT_ATTENDANCE = ("Present", "Half Day", "Work From Home")


# Settings


def setup():
	"""HR Settings > Attendance Watch: who sees it (HR Manager and HR User when first
	added) and the notification (on, 15 minutes after the shift starts)."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	if frappe.db.exists("Custom Field", {"dt": "HR Settings", "fieldname": ROLES_FIELD}):
		return
	create_custom_fields(
		{
			"HR Settings": [
				{
					"fieldname": "custom_attendance_watch_section",
					"fieldtype": "Section Break",
					"label": "Attendance Watch",
					"insert_after": "allow_geolocation_tracking",
				},
				{
					"fieldname": ROLES_FIELD,
					"fieldtype": "Table MultiSelect",
					"label": "Roles That Watch Attendance",
					"options": "Has Role",
					"insert_after": "custom_attendance_watch_section",
					"description": "Besides the System Manager, these roles see who has not checked in since "
					"their shift started, in the employee app and the Daily Shift Attendance report.",
				},
				{
					"fieldname": NOTIFY_FIELD,
					"fieldtype": "Check",
					"label": "Notify Who Has Not Checked In",
					"default": "1",
					"insert_after": ROLES_FIELD,
				},
				{
					"fieldname": NOTIFY_AFTER_FIELD,
					"fieldtype": "Int",
					"label": "Notify After Shift Start (Minutes)",
					"default": str(NOTIFY_AFTER_BY_DEFAULT),
					"depends_on": f"eval:doc.{NOTIFY_FIELD}",
					"insert_after": NOTIFY_FIELD,
				},
			]
		}
	)
	settings = frappe.get_single("HR Settings")
	for role in ROLES_BY_DEFAULT:
		if frappe.db.exists("Role", role):
			settings.append(ROLES_FIELD, {"role": role})
	settings.set(NOTIFY_FIELD, 1)
	settings.set(NOTIFY_AFTER_FIELD, NOTIFY_AFTER_BY_DEFAULT)
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)


def get_watching_roles():
	settings = frappe.get_cached_doc("HR Settings")
	return [SEES_ALL] + [row.role for row in settings.get(ROLES_FIELD) or []]


def can_watch(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(set(frappe.get_roles(user)) & set(get_watching_roles()))


def check_can_watch():
	if not can_watch():
		frappe.throw(_("You are not allowed to see who has checked in."), frappe.PermissionError)


# The day


def get_day(day=None, now=None, company=None, department=None, shift_type=None):
	"""Every active employee's status on the day, as rows (see the module's docstring)."""
	now = get_datetime(now) if now else now_datetime()
	day = getdate(day) if day else now.date()

	employee_filters = {"status": "Active", "date_of_joining": ("<=", day)}
	if company:
		employee_filters["company"] = company
	if department:
		employee_filters["department"] = department
	employees = frappe.get_all(
		"Employee",
		filters=employee_filters,
		fields=["name", "employee_name", "department", "company", "cell_number", "image", "default_shift", "relieving_date"],
		order_by="employee_name",
	)
	employees = [row for row in employees if not row.relieving_date or getdate(row.relieving_date) >= day]
	if not employees:
		return []
	names = [row.name for row in employees]

	shifts = _shifts_of(names, day)
	types = _shift_types({shifts.get(row.name) or row.default_shift for row in employees} - {None, ""})
	on_leave = _covering("Leave Application", names, day, {"docstatus": 1, "status": "Approved"})
	on_duty = _covering("Attendance Request", names, day, {"docstatus": 1})
	attendance = dict(
		frappe.get_all(
			"Attendance",
			filters={"employee": ("in", names), "attendance_date": day, "docstatus": 1},
			fields=["employee", "status"],
			as_list=True,
		)
	)
	permissions = {
		row.employee: row.to_time
		for row in frappe.get_all(
			"Permission Request",
			filters={
				"employee": ("in", names),
				"permission_date": day,
				"permission_type": "Late Arrival",
				"status": "Approved",
				"docstatus": ("!=", 2),
			},
			fields=["employee", "to_time"],
		)
	}

	rows = []
	windows = {}
	for employee in employees:
		row = frappe._dict(
			employee=employee.name,
			employee_name=employee.employee_name,
			department=employee.department,
			company=employee.company,
			phone=(employee.cell_number or "").strip(),
			image=employee.image,
			shift=shifts.get(employee.name) or employee.default_shift or None,
		)
		rows.append(row)
		shift = types.get(row.shift)
		if not shift:
			row.shift = None
			row.status = "no_shift"
			continue
		row.shift_start = datetime.combine(day, _as_time(shift.start_time))
		end = datetime.combine(day, _as_time(shift.end_time))
		if end <= row.shift_start:
			end += timedelta(days=1)
		row.shift_end = end
		windows[employee.name] = (row.shift_start - timedelta(minutes=cint(shift.begin_check_in_before_shift_start_time)), end)
		row.holiday_list = shift.holiday_list or get_holiday_list_for_employee(employee.name, raise_exception=False, as_on=day)

	checked_in = _checked_in(windows)
	holidays = _holidays({row.holiday_list for row in rows if row.get("holiday_list")}, day)

	for row in rows:
		if row.get("status"):
			continue
		marked = attendance.get(row.employee)
		if row.holiday_list in holidays:
			row.status = "holiday"
		elif row.employee in on_leave or marked == "On Leave":
			row.status = "on_leave"
		elif row.employee in on_duty:
			row.status = "on_duty"
		elif row.employee in checked_in or marked in PRESENT_ATTENDANCE:
			row.status = "present"
			row.first_in = checked_in.get(row.employee)
		elif marked == "Absent":
			row.status = "absent"
		elif now < row.shift_start:
			row.status = "upcoming"
		elif row.employee in permissions and now < datetime.combine(day, _as_time(permissions[row.employee])):
			row.status = "permission"
			row.permission_until = _as_time(permissions[row.employee])
		elif day < now.date() or now >= row.shift_end:
			row.status = "absent"
		else:
			row.status = "not_in"
			row.minutes_late = int((now - row.shift_start).total_seconds() // 60)

	if shift_type:
		rows = [row for row in rows if row.shift == shift_type]
	return rows


def _shifts_of(employees, day):
	"""Each employee's shift from the Shift Assignment active on the day (the earliest
	starting one, when several are)."""
	shifts = {}
	for row in frappe.get_all(
		"Shift Assignment",
		filters={"employee": ("in", employees), "docstatus": 1, "status": "Active", "start_date": ("<=", day)},
		or_filters=[["end_date", "is", "not set"], ["end_date", ">=", day]],
		fields=["employee", "shift_type"],
		order_by="start_date desc",
	):
		shifts.setdefault(row.employee, row.shift_type)
	return shifts


def _shift_types(names):
	if not names:
		return {}
	return {
		row.name: row
		for row in frappe.get_all(
			"Shift Type",
			filters={"name": ("in", list(names))},
			fields=["name", "start_time", "end_time", "begin_check_in_before_shift_start_time", "holiday_list"],
		)
	}


def _covering(doctype, employees, day, filters):
	return set(
		frappe.get_all(
			doctype,
			filters={"employee": ("in", employees), "from_date": ("<=", day), "to_date": (">=", day), **filters},
			pluck="employee",
		)
	)


def _checked_in(windows):
	"""The employees with a check-in in their window, with the first one's time."""
	if not windows:
		return {}
	start = min(window[0] for window in windows.values())
	end = max(window[1] for window in windows.values())
	first = {}
	for employee, moment in frappe.get_all(
		"Employee Checkin",
		filters={"employee": ("in", list(windows)), "time": ("between", (start, end))},
		fields=["employee", "time"],
		order_by="time asc",
		as_list=True,
	):
		window = windows[employee]
		if employee not in first and window[0] <= get_datetime(moment) <= window[1]:
			first[employee] = get_datetime(moment)
	return first


def _holidays(holiday_lists, day):
	if not holiday_lists:
		return set()
	return set(
		frappe.get_all("Holiday", filters={"parent": ("in", list(holiday_lists)), "holiday_date": day}, pluck="parent")
	)


def _as_time(value):
	if isinstance(value, time):
		return value
	if isinstance(value, timedelta):
		return (datetime.min + value).time()
	return get_datetime(f"2000-01-01 {value}").time()


# The employee app


@frappe.whitelist()
def get_overview():
	"""For the home screen's card: how many have not checked in, and how many were absent
	(their shift ended). None when the user may not see it."""
	if not can_watch():
		return None
	rows = get_day()
	return {
		"not_in": sum(row.status == "not_in" for row in rows),
		"absent": sum(row.status == "absent" for row in rows),
		"as_of": now_datetime().strftime("%H:%M"),
	}


@frappe.whitelist()
def get_board():
	"""The Not Checked In screen: who has not come in, who has a late arrival
	permission, who has no shift, and how many are in each other status."""
	check_can_watch()
	rows = get_day()
	now = now_datetime()

	def person(row):
		return {
			"employee": row.employee,
			"employee_name": row.employee_name,
			"department": row.department,
			"phone": row.phone,
			"image": row.image,
			"shift": row.shift,
			"shift_start": row.shift_start.strftime("%H:%M") if row.get("shift_start") else None,
			"minutes_late": row.get("minutes_late"),
			"permission_until": row.permission_until.strftime("%H:%M") if row.get("permission_until") else None,
		}

	lists = {status: [person(row) for row in rows if row.status == status] for status in ("not_in", "absent", "permission", "no_shift")}
	lists["not_in"].sort(key=lambda row: -(row["minutes_late"] or 0))
	return {
		**lists,
		"counts": {status: sum(row.status == status for row in rows) for status in STATUSES},
		"as_of": now.strftime("%H:%M"),
	}


# The notification


def notify_not_checked_in(now=None):
	"""Every few minutes (scheduler): for each shift that started the set minutes ago, tell
	the watching users how many have not checked in, once a day."""
	settings = frappe.get_cached_doc("HR Settings")
	if not settings.get(NOTIFY_FIELD):
		return
	after = timedelta(minutes=cint(settings.get(NOTIFY_AFTER_FIELD)))
	now = get_datetime(now) if now else now_datetime()

	by_shift = {}
	for row in get_day(now=now):
		if row.status == "not_in" and now >= row.shift_start + after:
			by_shift.setdefault(row.shift, []).append(row)
	if not by_shift:
		return

	recipients = _recipients()
	for shift, rows in by_shift.items():
		message = _("{0} have not checked in yet · {1} shift ({2})").format(
			len(rows), shift, rows[0].shift_start.strftime("%H:%M")
		)
		for user in recipients:
			if frappe.db.exists(
				"PWA Notification",
				{
					"to_user": user,
					"reference_document_type": "Shift Type",
					"reference_document_name": shift,
					"creation": (">=", now.date()),
				},
			):
				continue
			frappe.get_doc(
				{
					"doctype": "PWA Notification",
					"from_user": "Administrator",
					"to_user": user,
					"message": message,
					"reference_document_type": "Shift Type",
					"reference_document_name": shift,
				}
			).insert(ignore_permissions=True)


def _recipients():
	roles = get_watching_roles()
	users = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": ("in", roles)}, pluck="parent", distinct=True
	)
	users = set(users) - {"Administrator", "Guest"}
	if not users:
		return []
	return frappe.get_all(
		"User", filters={"name": ("in", list(users)), "enabled": 1, "user_type": "System User"}, pluck="name"
	)
