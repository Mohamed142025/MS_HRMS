"""The employee app's notifications (PWA Notification), each also pushed to the user's
devices (web_push).

- Requests: a new Permission, Overtime or Attendance Request or Employee Advance tells its
  approvers (Frappe HR already tells them of new leaves, expense claims and shift
  requests); every request's decision and cancellation tells its employee, and a
  cancellation by the employee tells the approver it was waiting on.
- Frappe HR's own notifications, written in English, are written again in the language
  of the user they go to, with what the request is for.
- Occasions, once a day at HR Settings' time: holidays and the employee's approved leave
  the next day, birthdays and work anniversaries (to the employee and the colleagues of
  their department).
- Salary slips, when submitted.
- Check-in reminder: an employee who has not checked in the set minutes after their
  shift started (attendance_watch), once a day.
- HR Announcements, when submitted.

HR Settings > App Notifications turns each of them on and off.
"""

import functools
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, fmt_money, get_datetime, getdate, now_datetime

from hrms.utils.holiday_list import get_holiday_list_for_employee

# HR Settings > App Notifications (setup()).
SETTINGS = {
	"requests": "custom_notify_requests",
	"holidays": "custom_notify_holidays",
	"leave_start": "custom_notify_leave_start",
	"birthdays": "custom_notify_birthdays",
	"work_anniversaries": "custom_notify_work_anniversaries",
	"salary_slips": "custom_notify_salary_slips",
	"check_in": "custom_remind_check_in",
}
OCCASIONS_AT_FIELD = "custom_occasions_notify_at"
CHECK_IN_AFTER_FIELD = "custom_check_in_reminder_after"
OCCASIONS_SENT = "ms_hrms_occasions_sent_on"

# Requests whose approvers Frappe HR itself notifies of new ones (hrms PWANotificationsMixin).
NOTIFIED_BY_HRMS = ("Leave Application", "Expense Claim", "Shift Request")
STATUS_FIELDS = {"Leave Application": "status", "Expense Claim": "approval_status", "Shift Request": "status"}


# Settings


def setup():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	if frappe.db.exists("Custom Field", {"dt": "HR Settings", "fieldname": SETTINGS["requests"]}):
		return
	checks = [
		("requests", "Notify About Requests", "New requests to their approvers; decisions and cancellations to their employees."),
		("holidays", "Remind of Holidays", "The day before a holiday, to the employees whose holiday list has it."),
		("leave_start", "Remind of Leaves Starting", "The day before an employee's approved leave starts."),
		("birthdays", "Birthday Greetings", "To the employee and the colleagues of their department."),
		("work_anniversaries", "Work Anniversary Greetings", "To the employee and the colleagues of their department."),
		("salary_slips", "Notify of Salary Slips", "When an employee's salary slip is submitted."),
		("check_in", "Remind Employees to Check In", "When their shift started and they have not checked in."),
	]
	fields = [
		{
			"fieldname": "custom_app_notifications_section",
			"fieldtype": "Section Break",
			"label": "App Notifications",
			"insert_after": "custom_roles_that_see_all_requests",
			"description": "What the employee app notifies of; each is also pushed to the phones that turned notifications on.",
		}
	]
	after = "custom_app_notifications_section"
	for key, label, description in checks:
		fields.append(
			{
				"fieldname": SETTINGS[key],
				"fieldtype": "Check",
				"label": label,
				"default": "1",
				"description": description,
				"insert_after": after,
			}
		)
		after = SETTINGS[key]
		if key == "work_anniversaries":
			fields.append({"fieldname": "custom_app_notifications_column", "fieldtype": "Column Break", "insert_after": after})
			fields.append(
				{
					"fieldname": OCCASIONS_AT_FIELD,
					"fieldtype": "Time",
					"label": "Send Reminders and Greetings At",
					"default": "09:00:00",
					"insert_after": "custom_app_notifications_column",
				}
			)
			after = OCCASIONS_AT_FIELD
	fields.append(
		{
			"fieldname": CHECK_IN_AFTER_FIELD,
			"fieldtype": "Int",
			"label": "Check-in Reminder After Shift Start (Minutes)",
			"default": "15",
			"depends_on": f"eval:doc.{SETTINGS['check_in']}",
			"insert_after": after,
		}
	)
	create_custom_fields({"HR Settings": fields})

	settings = frappe.get_single("HR Settings")
	for fieldname in SETTINGS.values():
		settings.set(fieldname, 1)
	settings.set(OCCASIONS_AT_FIELD, "09:00:00")
	settings.set(CHECK_IN_AFTER_FIELD, 15)
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)


def is_on(key):
	return bool(frappe.get_cached_doc("HR Settings").get(SETTINGS[key]))


# Sending


def notify(to_user, message, doctype=None, name=None, from_user=None):
	"""One notification in the app (and pushed to the user's devices)."""
	if not to_user or to_user in ("Guest",):
		return
	doc = frappe.new_doc("PWA Notification")
	doc.flags.ms_hrms = True
	doc.update(
		{
			"from_user": from_user or frappe.session.user,
			"to_user": to_user,
			"message": message,
			"reference_document_type": doctype,
			"reference_document_name": name,
		}
	)
	doc.insert(ignore_permissions=True)


def lang_of(user):
	return frappe.db.get_value("User", user, "language", cache=True) or frappe.db.get_default("lang") or "en"


def t(message, lang, *values):
	"""The message in this language, with its values in bold."""
	return _(message, lang=lang).format(*[f"<b>{frappe.utils.escape_html(str(v))}</b>" for v in values])


def user_of(employee):
	return frappe.db.get_value("Employee", employee, "user_id", cache=True) if employee else None


def name_of(user):
	return frappe.utils.get_fullname(user) if user else ""


def day_label(value, lang, with_month=True):
	from babel.dates import format_date

	try:
		return format_date(getdate(value), "d MMMM" if with_month else "d", locale=lang.replace("-", "_"))
	except Exception:
		return str(getdate(value))


# What a request is for, in a few words


def describe(doc, lang):
	def period(start, end):
		if not start:
			return ""
		if not end or getdate(start) == getdate(end):
			return day_label(start, lang)
		return f"{day_label(start, lang)} – {day_label(end, lang)}"

	def clock(value):
		from ms_hrms.attendance_watch import _as_time

		return _as_time(value).strftime("%H:%M") if value else ""

	if doc.doctype == "Leave Application":
		parts = [_(doc.leave_type, lang=lang), period(doc.from_date, doc.to_date)]
	elif doc.doctype == "Permission Request":
		parts = [_(doc.permission_type, lang=lang), day_label(doc.permission_date, lang), f"{clock(doc.from_time)} – {clock(doc.to_time)}"]
	elif doc.doctype == "Overtime Request":
		parts = [day_label(doc.overtime_date, lang), _("{0} hours", lang=lang).format(f"{flt(doc.requested_hours, 2):g}")]
	elif doc.doctype == "Shift Request":
		parts = [doc.shift_type, period(doc.from_date, doc.to_date)]
	elif doc.doctype == "Attendance Request":
		parts = [_(doc.reason, lang=lang) if doc.reason else "", period(doc.from_date, doc.to_date)]
	elif doc.doctype == "Expense Claim":
		parts = [fmt_money(doc.total_claimed_amount, currency=doc.currency), day_label(doc.posting_date, lang)]
	elif doc.doctype == "Employee Advance":
		parts = [fmt_money(doc.advance_amount, currency=doc.currency), day_label(doc.posting_date, lang)]
	else:
		parts = [doc.name]
	return " · ".join(part for part in parts if part)


def request_label(doctype, lang):
	return _(doctype, lang=lang)


# Requests


def safe(handler):
	"""A notification that fails is logged; it never stops the request being saved."""

	@functools.wraps(handler)
	def wrapper(*args, **kwargs):
		try:
			return handler(*args, **kwargs)
		except Exception:
			frappe.log_error(f"App notification failed: {handler.__name__}")

	return wrapper


def approvers_of(doc):
	"""Who decides the request: its approver field, the employee's or department's
	approvers (request_approvers), or the employee's manager."""
	from ms_hrms.request_approvers import REQUESTS, get_approvers

	field = {"Leave Application": "leave_approver", "Expense Claim": "expense_approver", "Shift Request": "approver"}.get(doc.doctype)
	if field and doc.get(field):
		return [doc.get(field)]
	users = []
	if REQUESTS.get(doc.doctype, {}).get("employee_field"):
		users = get_approvers(doc.doctype, doc.employee)
	if not users:
		manager = frappe.db.get_value("Employee", doc.employee, "reports_to")
		users = [user_of(manager)] if manager else []
	return [user for user in users if user]


def tell_approvers_of_new(doc):
	employee_user = user_of(doc.employee)
	for user in approvers_of(doc):
		if user == employee_user:
			continue
		lang = lang_of(user)
		notify(
			user,
			t("{0} sent a {1} for your approval: {2}", lang, doc.employee_name, request_label(doc.doctype, lang), describe(doc, lang)),
			doc.doctype,
			doc.name,
			from_user=employee_user,
		)


def tell_employee_of_decision(doc, decision, remarks=None):
	"""Approved, Rejected or Cancelled, by the session user, unless that is the employee."""
	employee_user = user_of(doc.employee)
	actor = frappe.session.user
	if not employee_user or actor == employee_user:
		return
	lang = lang_of(employee_user)
	messages = {
		"Approved": "Your {0} ({1}) was approved by {2}",
		"Rejected": "Your {0} ({1}) was rejected by {2}",
		"Cancelled": "Your {0} ({1}) was cancelled by {2}",
	}
	message = t(messages[decision], lang, request_label(doc.doctype, lang), describe(doc, lang), name_of(actor))
	if remarks:
		message += "<br>" + _("Remarks: {0}", lang=lang).format(frappe.utils.escape_html(remarks))
	notify(employee_user, message, doc.doctype, doc.name)


def tell_approvers_of_cancel(doc):
	"""The employee withdrew a request that was still waiting."""
	employee_user = user_of(doc.employee)
	if frappe.session.user != employee_user:
		return
	for user in approvers_of(doc):
		if user == employee_user:
			continue
		lang = lang_of(user)
		notify(
			user,
			t("{0} cancelled their {1}: {2}", lang, doc.employee_name, request_label(doc.doctype, lang), describe(doc, lang)),
			doc.doctype,
			doc.name,
			from_user=employee_user,
		)


@safe
def on_status_request_update(doc, method=None):
	"""Permission and Overtime Requests (on update): new ones waiting for approval, and
	decisions."""
	if not is_on("requests"):
		return
	before = doc.get_doc_before_save()
	previous = before.status if before else None
	if doc.status == previous:
		return
	if doc.status == "Pending Approval":
		tell_approvers_of_new(doc)
	elif doc.status in ("Approved", "Rejected"):
		tell_employee_of_decision(doc, doc.status, doc.get("approval_remarks"))
	elif doc.status == "Cancelled":
		on_request_cancel(doc, was_waiting=previous == "Pending Approval")


@safe
def on_request_insert(doc, method=None):
	"""Attendance Requests and Employee Advances (after insert): to the approver."""
	if is_on("requests"):
		tell_approvers_of_new(doc)


@safe
def on_request_submit(doc, method=None):
	"""Attendance Requests and Employee Advances (on submit): approving them is
	submitting them."""
	if is_on("requests"):
		tell_employee_of_decision(doc, "Approved")


@safe
def on_request_cancel(doc, method=None, was_waiting=None):
	"""Any request (on cancel). Whether it was still waiting for its decision is read
	from before the cancellation."""
	if not is_on("requests"):
		return
	if was_waiting is None:
		before = doc.get_doc_before_save()
		field = STATUS_FIELDS.get(doc.doctype) or ("status" if doc.meta.has_field("status") else None)
		was_waiting = bool(before and field and before.get(field) in ("Open", "Draft", "Pending Approval"))
	if frappe.session.user == user_of(doc.employee):
		if was_waiting:
			tell_approvers_of_cancel(doc)
	else:
		tell_employee_of_decision(doc, "Cancelled")


@safe
def rewrite_hrms_notification(doc, method=None):
	"""PWA Notification (before insert): Frappe HR's notifications of new and decided
	leaves, expense claims and shift requests, written again in the user's language."""
	if doc.flags.ms_hrms or doc.reference_document_type not in NOTIFIED_BY_HRMS or not doc.reference_document_name:
		return
	request = frappe.get_doc(doc.reference_document_type, doc.reference_document_name)
	lang = lang_of(doc.to_user)
	label = request_label(request.doctype, lang)
	if doc.to_user == user_of(request.employee):
		status = request.get(STATUS_FIELDS[request.doctype])
		message = {"Approved": "Your {0} ({1}) was approved by {2}", "Rejected": "Your {0} ({1}) was rejected by {2}"}.get(status)
		if message:
			doc.message = t(message, lang, label, describe(request, lang), name_of(doc.from_user))
	else:
		doc.message = t("{0} sent a {1} for your approval: {2}", lang, request.employee_name, label, describe(request, lang))


# Salary slips


@safe
def on_salary_slip_submit(doc, method=None):
	if not is_on("salary_slips"):
		return
	user = user_of(doc.employee)
	if not user:
		return
	lang = lang_of(user)
	from babel.dates import format_date

	try:
		month = format_date(getdate(doc.end_date), "MMMM yyyy", locale=lang.replace("-", "_"))
	except Exception:
		month = str(doc.end_date)
	notify(user, t("Your salary slip for {0} is ready: {1}", lang, month, fmt_money(doc.net_pay, currency=doc.currency)), "Salary Slip", doc.name)


# Announcements


def send_announcement(doc):
	"""The announcement to every active employee with a user (of the department, when
	it is for one). Returns how many it went to."""
	filters = {"status": "Active", "user_id": ("is", "set")}
	if doc.company:
		filters["company"] = doc.company
	if doc.audience == "Department":
		filters["department"] = doc.department
	users = set(frappe.get_all("Employee", filters=filters, pluck="user_id"))
	body = f"<b>{frappe.utils.escape_html(doc.title)}</b><br>{frappe.utils.escape_html(doc.message)}"
	for user in users:
		notify(user, body, "HR Announcement", doc.name)
	return len(users)


# Occasions


def send_occasions(now=None):
	"""Every few minutes (scheduler): once a day, at HR Settings' time, the reminders and
	greetings that are on."""
	now = get_datetime(now) if now else now_datetime()
	settings = frappe.get_cached_doc("HR Settings")
	at = settings.get(OCCASIONS_AT_FIELD) or "09:00:00"
	if now < get_datetime(f"{now.date()} {at}"):
		return
	if frappe.db.get_default(OCCASIONS_SENT) == str(now.date()):
		return
	frappe.db.set_default(OCCASIONS_SENT, str(now.date()))

	today = now.date()
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", "user_id": ("is", "set")},
		fields=["name", "employee_name", "first_name", "user_id", "department", "date_of_birth", "date_of_joining"],
	)
	if is_on("holidays"):
		_holidays_tomorrow(employees, today)
	if is_on("leave_start"):
		_leaves_tomorrow(today)
	if is_on("birthdays"):
		_greet(employees, today, "date_of_birth")
	if is_on("work_anniversaries"):
		_greet(employees, today, "date_of_joining")


def _holidays_tomorrow(employees, today):
	tomorrow = add_days(today, 1)
	holidays = {
		row.parent: row.description
		for row in frappe.get_all(
			"Holiday", filters={"holiday_date": tomorrow, "weekly_off": 0}, fields=["parent", "description"]
		)
	}
	if not holidays:
		return
	for employee in employees:
		holiday_list = get_holiday_list_for_employee(employee.name, raise_exception=False, as_on=tomorrow)
		if holiday_list in holidays:
			lang = lang_of(employee.user_id)
			what = frappe.utils.strip_html(holidays[holiday_list] or "").strip() or _("Holiday", lang=lang)
			notify(employee.user_id, t("Tomorrow is a holiday: {0}", lang, what), "Holiday List", holiday_list, from_user="Administrator")


def _leaves_tomorrow(today):
	tomorrow = add_days(today, 1)
	for leave in frappe.get_all(
		"Leave Application",
		filters={"from_date": tomorrow, "status": "Approved", "docstatus": 1},
		fields=["name", "employee", "leave_type", "to_date"],
	):
		user = user_of(leave.employee)
		if user:
			lang = lang_of(user)
			notify(
				user,
				t("Your {0} starts tomorrow and ends on {1}", lang, _(leave.leave_type, lang=lang), day_label(leave.to_date, lang)),
				"Leave Application",
				leave.name,
				from_user="Administrator",
			)


def _greet(employees, today, date_field):
	"""Birthdays (date_of_birth) or work anniversaries (date_of_joining) today: the
	employee, and the colleagues of their department."""
	birthday = date_field == "date_of_birth"
	for person in employees:
		day = person.get(date_field)
		if not day:
			continue
		day = getdate(day)
		years = today.year - day.year
		if (day.month, day.day) != (today.month, today.day) or (not birthday and years < 1):
			continue

		lang = lang_of(person.user_id)
		first = person.first_name or person.employee_name
		if birthday:
			message = t("Happy birthday, {0}! Wishing you a wonderful year.", lang, first)
		else:
			message = t("Happy work anniversary, {0}! {1} years with us today.", lang, first, years)
		notify(person.user_id, message, "Employee", person.name, from_user="Administrator")

		if not person.department:
			continue
		for colleague in employees:
			if colleague.department != person.department or colleague.name == person.name:
				continue
			lang = lang_of(colleague.user_id)
			if birthday:
				message = t("Today is {0}'s birthday. Wish them a happy birthday!", lang, person.employee_name)
			else:
				message = t("{0} completes {1} years with us today.", lang, person.employee_name, years)
			notify(colleague.user_id, message, "Employee", person.name, from_user="Administrator")


# Check-in reminder


def remind_check_in(now=None):
	"""Every few minutes (scheduler): the employees who have not checked in the set
	minutes after their shift started, once a day (attendance_watch)."""
	if not is_on("check_in"):
		return
	from ms_hrms.attendance_watch import get_day

	now = get_datetime(now) if now else now_datetime()
	after = timedelta(minutes=cint(frappe.get_cached_doc("HR Settings").get(CHECK_IN_AFTER_FIELD)))
	for row in get_day(now=now):
		if row.status != "not_in" or now < row.shift_start + after:
			continue
		user = user_of(row.employee)
		if not user or frappe.db.exists(
			"PWA Notification",
			{"to_user": user, "reference_document_type": "Employee Checkin", "creation": (">=", now.date())},
		):
			continue
		lang = lang_of(user)
		notify(
			user,
			t("Your {0} shift started at {1} and you have not checked in yet.", lang, row.shift, row.shift_start.strftime("%H:%M")),
			"Employee Checkin",
			None,
			from_user="Administrator",
		)
