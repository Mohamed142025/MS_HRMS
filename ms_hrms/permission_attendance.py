"""Attendance follows a Permission Request's check-ins.

An approved Permission Request adds check-ins (late arrival, early leave, out and back
during working hours); editing or cancelling it moves or deletes them. Frappe HR marks
attendance from check-ins only once per shift: a check-in added after the day's
attendance was marked is skipped ("Attendance ... is already marked"), so the
permission would not count. Whenever a request's check-ins change, the attendance of
each shift they belong to is worked out again here from the check-ins it has now:

- no attendance yet: nothing to do; the check-ins wait for Frappe HR's scheduler (any
  of them skipped before are released for it);
- attendance marked from check-ins (linked to it, or marked by the scheduler): it is
  cancelled, the shift's check-ins are unlinked and released, and attendance is marked
  again at once as Frappe HR marks it (Shift Type), or left to the scheduler when the
  shift is not yet synced. A half day of leave is updated in place, as Frappe HR does;
- attendance marked by hand, one a submitted Attendance Penalty Processing has used, or
  one of a shift that no longer marks attendance automatically: it stays as it is, and
  HR is told to review it (Notification Log), as is whoever approved the request;
- attendance on leave: left alone.

Everything runs in the request's own transaction, as Administrator (as the scheduler
does), so the approver need not be allowed to mark attendance.
"""

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import cint, flt, format_date, get_datetime, get_link_to_form

# What Frappe HR reads of check-ins to mark attendance (ShiftType.get_employee_checkins).
CHECKIN_FIELDS = [
	"name",
	"employee",
	"log_type",
	"time",
	"shift",
	"shift_start",
	"shift_end",
	"shift_actual_start",
	"shift_actual_end",
	"device_id",
	"overtime_type",
]
HR_ROLES = ("HR Manager", "HR User")


def get_shift_days(request_name):
	"""The shifts a request's check-ins belong to: (employee, shift, shift start)."""
	if not frappe.get_meta("Employee Checkin").has_field("custom_permission_request"):
		return set()
	return {
		(row.employee, row.shift, get_datetime(row.shift_start))
		for row in frappe.get_all(
			"Employee Checkin",
			filters={"custom_permission_request": request_name},
			fields=["employee", "shift", "shift_start"],
		)
		if row.shift and row.shift_start
	}


def recalculate(request, shift_days):
	"""Work out again the attendance of each of these shifts (see the module's
	docstring). A shift that fails is logged and left to HR; the request is saved."""
	for employee, shift, shift_start in sorted(shift_days):
		frappe.db.savepoint("permission_attendance")
		try:
			_recalculate(request, employee, shift, shift_start)
		except Exception:
			frappe.db.rollback(save_point="permission_attendance")
			frappe.log_error(
				f"Attendance not recalculated for {request.name}",
				f"{employee} · {shift} · {shift_start}\n\n{frappe.get_traceback()}",
			)
			tell_hr(request, employee, shift_start.date(), None, "failed")


def _recalculate(request, employee, shift, shift_start):
	day = shift_start.date()
	checkins = {"employee": employee, "shift": shift, "shift_start": shift_start}
	linked = frappe.get_all("Employee Checkin", filters={**checkins, "attendance": ("is", "set")}, pluck="attendance", distinct=True)
	attendance_name = linked[0] if linked else _attendance_of(employee, day, shift)

	if not attendance_name:
		release(checkins)
		return

	attendance = frappe.get_doc("Attendance", attendance_name)
	if attendance.docstatus != 1:
		release(checkins)
		return
	if attendance.status == "On Leave":
		return
	processing = _penalty_processing_of(attendance.name)
	if processing:
		tell_hr(request, employee, day, attendance, "penalty", processing)
		return
	if not linked and not _marked_by_scheduler(attendance):
		tell_hr(request, employee, day, attendance, "manual")
		return
	if frappe.get_cached_doc("Shift Type", shift).has_incorrect_shift_config():
		# Neither marked again here nor by the scheduler: left for HR.
		tell_hr(request, employee, day, None, "failed")
		return

	with as_administrator():
		# A half day of leave is updated in place by Frappe HR; anything else is marked anew.
		if not (attendance.status == "Half Day" and attendance.get("leave_type")):
			attendance.flags.ignore_permissions = True
			with muted():
				attendance.cancel()
		release(checkins, unlink=True)
		marked = mark(employee, shift, shift_start)

	if marked:
		frappe.msgprint(
			_("Attendance of {0} on {1} was worked out again from the check-ins.").format(
				frappe.bold(attendance.employee_name or employee), format_date(day)
			),
			alert=True,
			indicator="green",
		)


def _attendance_of(employee, day, shift):
	"""The day's submitted attendance for this shift (or with no shift)."""
	rows = frappe.get_all(
		"Attendance",
		filters={"employee": employee, "attendance_date": day, "docstatus": 1},
		fields=["name", "shift"],
	)
	for row in rows:
		if row.shift == shift:
			return row.name
	for row in rows:
		if not row.shift:
			return row.name
	return None


def _marked_by_scheduler(attendance):
	"""Marked automatically: by the scheduler (as Administrator), not from a leave or an
	attendance request."""
	return (
		attendance.owner == "Administrator"
		and not attendance.get("leave_application")
		and not attendance.get("attendance_request")
	)


def _penalty_processing_of(attendance_name):
	"""A submitted Attendance Penalty Processing that used this attendance."""
	rows = frappe.db.sql(
		"""select p.name from `tabAttendance Penalty Detail` d
		join `tabAttendance Penalty Processing` p on p.name = d.parent
		where p.docstatus = 1 and d.attendance = %s limit 1""",
		attendance_name,
	)
	return rows[0][0] if rows else None


def release(checkins, unlink=False):
	"""Let Frappe HR mark attendance from the shift's check-ins again: not skipped, and
	(once their attendance is cancelled) not linked."""
	values = {"skip_auto_attendance": 0}
	filters = dict(checkins)
	if unlink:
		values["attendance"] = None
	else:
		filters["attendance"] = ("is", "not set")
	frappe.db.set_value("Employee Checkin", filters, values, update_modified=False)


def mark(employee, shift, shift_start):
	"""Mark the shift's attendance from its check-ins as Frappe HR's scheduler does
	(ShiftType._process for one employee and shift). Left to the scheduler when the shift
	does not mark attendance automatically or its check-ins are not synced yet."""
	from hrms.hr.doctype.employee_checkin.employee_checkin import mark_attendance_and_link_log

	shift_type = frappe.get_doc("Shift Type", shift)
	if shift_type.has_incorrect_shift_config():
		return None
	logs = frappe.get_all(
		"Employee Checkin",
		fields=CHECKIN_FIELDS,
		filters={
			"employee": employee,
			"shift": shift,
			"shift_start": shift_start,
			"skip_auto_attendance": 0,
			"attendance": ("is", "not set"),
			"offshift": 0,
			"time": (">=", shift_type.process_attendance_after),
		},
		order_by="time",
	)
	if not logs or get_datetime(logs[0].shift_actual_end) >= get_datetime(shift_type.last_sync_of_checkin):
		return None

	day = shift_start.date()
	if not shift_type.should_mark_attendance(employee, day):
		return None
	half_day = flt(shift_type.working_hours_threshold_for_half_day)
	absent = flt(shift_type.working_hours_threshold_for_absent)
	if shift_type.is_half_holiday(employee, day):
		half_day, absent = half_day / 2, absent / 2

	status, working_hours, late_entry, early_exit, in_time, out_time = shift_type.get_attendance(logs, absent, half_day)
	return mark_attendance_and_link_log(
		logs,
		status,
		day,
		working_hours,
		late_entry,
		early_exit,
		in_time,
		out_time,
		shift_type.name,
		logs[0].get("overtime_type"),
	)


# HR review


def tell_hr(request, employee, day, attendance, reason, processing=None):
	"""Ask HR to review an attendance the request's check-ins change but that is not
	changed automatically (each in their own language), and tell whoever approved it."""
	employee_name = frappe.db.get_value("Employee", employee, "employee_name") or employee

	def message(lang):
		request_link = get_link_to_form(request.doctype, request.name)
		if not attendance:
			return _(
				"The attendance of {0} on {1} could not be worked out again after Permission Request {2}. Review it.",
				lang=lang,
			).format(frappe.bold(employee_name), format_date(day), request_link)
		if reason == "penalty":
			text = _(
				"Approved Permission Request {0} changes the check-ins of {1} on {2}, whose attendance {3} is in the submitted Attendance Penalty Processing {4}. Review it.",
				lang=lang,
			)
		else:
			text = _(
				"Approved Permission Request {0} changes the check-ins of {1} on {2}, whose attendance {3} was marked by hand. Review it.",
				lang=lang,
			)
		return text.format(
			request_link,
			frappe.bold(employee_name),
			format_date(day),
			get_link_to_form("Attendance", attendance.name),
			get_link_to_form("Attendance Penalty Processing", processing) if processing else "",
		)

	target = attendance.name if attendance else request.name
	for user in _hr_users():
		lang = frappe.db.get_value("User", user, "language") or frappe.db.get_default("lang") or "en"
		subject = message(lang)
		if frappe.db.exists("Notification Log", {"for_user": user, "subject": subject}):
			continue
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"from_user": frappe.session.user,
				"type": "Alert",
				"subject": subject,
				"document_type": "Attendance" if attendance else request.doctype,
				"document_name": target,
			}
		).insert(ignore_permissions=True)

	frappe.msgprint(
		_("The attendance of {0} on {1} was not changed automatically; HR has been asked to review it.").format(
			frappe.bold(employee_name), format_date(day)
		),
		indicator="orange",
		alert=True,
	)


def _hr_users():
	users = frappe.get_all(
		"Has Role", filters={"parenttype": "User", "role": ("in", HR_ROLES)}, pluck="parent", distinct=True
	)
	users = set(users) - {"Administrator", "Guest"}
	if not users:
		return []
	return frappe.get_all("User", filters={"name": ("in", list(users)), "enabled": 1}, pluck="name")


# Context


@contextmanager
def as_administrator():
	"""Run as Administrator, as Frappe HR's scheduler marks attendance. Only the session's
	user (and the permissions worked out for it) is switched: frappe.set_user would also
	replace the request's session id and form."""
	local = frappe.local
	user = local.session.user
	if user == "Administrator":
		yield
		return
	saved = (local.user_perms, local.role_permissions)
	local.session.user, local.user_perms, local.role_permissions = "Administrator", None, {}
	try:
		yield
	finally:
		local.session.user = user
		local.user_perms, local.role_permissions = saved


@contextmanager
def muted():
	"""Without Frappe HR's "Unlinked logs" message on cancelling attendance."""
	before = frappe.flags.mute_messages
	frappe.flags.mute_messages = True
	try:
		yield
	finally:
		frappe.flags.mute_messages = before
