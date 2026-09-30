"""Numbers for the employee app (ms_hrms.pwa): the home screen's day and month, the
attendance calendar, insights, the approver's team today, leaves, salary and expenses.

Everything is about the signed-in employee, except the team summary, which covers only
the employees the user manages or approves, and colleagues' leaves, which follow HR
Settings (Show Leaves Of All Department Members In Calendar). Nothing here writes;
documents are read through frappe.get_list or checked with check_permission.

A day counts as:
- on time / late: the employee checked in (or has Present attendance); late when the
  first check-in is after the shift start plus its grace period, or attendance says so;
  without a shift (and no late mark) the day is simply present;
- leave: an approved leave, or On Leave attendance;
- absent: Absent attendance, or a past working day without any record;
- weekly off / holiday: from the employee's holiday list.
"""

from collections import Counter
from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, get_url, getdate, now_datetime

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from hrms.api import get_current_employee

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
PRESENT = ("on_time", "late", "present")
CACHE_SECONDS = 600


# Home


@frappe.whitelist()
def get_home():
	employee = get_current_employee()
	today = getdate()
	month_days = _days(employee, get_first_day(today), today)
	month = _summary(month_days)
	previous = _cached_summary(employee, get_first_day(add_months(today, -1)))
	shift = _shifts(employee, today, today).get(today)

	return {
		"shift": _shift_times(shift),
		"month": month,
		"previous_month": {k: previous[k] for k in ("avg_arrival", "punctuality", "avg_hours")},
		"week": _week(employee, today),
		"overtime_hours": _overtime_hours(employee, get_first_day(today), today),
		"permission_hours": _permission_hours(employee, get_first_day(today), today),
		"next_holiday": _next_holiday(employee, today),
		"latest_salary_slip": _latest_salary_slip(employee),
		"insights": _insights(employee, today, month_days),
	}


# Attendance


@frappe.whitelist()
def get_attendance(month=None):
	"""A month's calendar for the attendance screen: every day's status, the counts, and
	the latest check-ins."""
	employee = get_current_employee()
	first = get_first_day(getdate(f"{month}-01") if month else getdate())
	last = min(get_last_day(first), getdate())
	days = _days(employee, first, get_last_day(first)) if first <= getdate() else []

	return {
		"month": first.strftime("%Y-%m"),
		"first_weekday": _week_start(employee),
		"days": days,
		"summary": _summary([d for d in days if getdate(d["date"]) <= last]),
		"recent": _recent_days(employee),
	}


# Insights


@frappe.whitelist()
def get_insights(period="month"):
	"""The insights screen: a discipline index, this period against the one before, the
	six-month punctuality trend, arrival times, late days by weekday, and notes."""
	employee = get_current_employee()
	today = getdate()
	months = {"month": 1, "quarter": 3, "year": 12}.get(period, 1)
	start = get_first_day(add_months(today, 1 - months))
	previous_start = add_months(start, -months)

	days = _days(employee, start, today)
	current = _summary(days)
	previous = _summary(_days(employee, previous_start, add_days(start, -1)))
	late_by_weekday = Counter(d["weekday"] for d in days if d["status"] == "late")

	return {
		"period": period,
		"from_date": str(start),
		"shift": _shift_times(_shifts(employee, today, today).get(today)),
		"index": _discipline_index(current),
		"previous_index": _discipline_index(previous),
		"summary": current,
		"previous": previous,
		"overtime_hours": _overtime_hours(employee, start, today),
		"previous_overtime_hours": _overtime_hours(employee, previous_start, add_days(start, -1)),
		"permission_hours": _permission_hours(employee, start, today),
		"trend": _monthly_trend(employee, today),
		"arrivals": [
			{"date": d["date"], "minutes": d["arrival_minutes"], "late": d["status"] == "late"}
			for d in days
			if d["status"] in PRESENT and d["arrival_minutes"] is not None
		],
		"late_by_weekday": [
			{"weekday": weekday, "count": late_by_weekday.get(index, 0)}
			for index, weekday in _working_weekdays(employee)
		],
		"notes": _insights(employee, today, [d for d in days if getdate(d["date"]) >= get_first_day(today)]),
	}


# Team (approvers and managers)


@frappe.whitelist()
def get_team_today():
	"""Where the user's team is today: in on time, late, on leave, or not checked in yet."""
	me = get_current_employee()
	team = _team(me)
	if not team:
		return {"size": 0}

	today = getdate()
	now = now_datetime()
	people = frappe.get_all(
		"Employee", filters={"name": ("in", team)}, fields=["name", "employee_name", "image"]
	)
	on_leave = set(
		frappe.get_all(
			"Leave Application",
			filters={
				"employee": ("in", team),
				"docstatus": 1,
				"status": "Approved",
				"from_date": ("<=", today),
				"to_date": (">=", today),
			},
			pluck="employee",
		)
	)
	first_in = dict(
		frappe.db.sql(
			"""select employee, min(time) from `tabEmployee Checkin`
			where employee in %(team)s and time >= %(day)s and time < %(next)s
			group by employee""",
			{"team": tuple(team), "day": today, "next": add_days(today, 1)},
		)
	)

	groups = {"on_time": [], "late": [], "on_leave": [], "not_in": [], "off": []}
	for person in people:
		if person.name in on_leave:
			groups["on_leave"].append(person)
		elif _is_holiday(person.name, today):
			groups["off"].append(person)
		elif person.name in first_in:
			shift = _shifts(person.name, today, today).get(today)
			late = shift and _arrival_minutes(first_in[person.name], shift) > shift.late_entry_grace_period
			groups["late" if late else "on_time"].append(person)
		else:
			groups["not_in"].append(person)

	return {
		"size": len(people),
		"counts": {key: len(value) for key, value in groups.items()},
		"late": groups["late"][:6],
		"on_leave": groups["on_leave"][:6],
		"as_of": now.strftime("%H:%M"),
	}


# Leaves


@frappe.whitelist()
def get_leave_overview():
	"""Each leave type's balance (allocated, used, pending, expired, remaining), upcoming
	leaves (the employee's own, and the department's when HR Settings shows them), and
	when each current allocation ends."""
	from hrms.hr.doctype.leave_application.leave_application import get_leave_details

	employee = get_current_employee()
	today = getdate()
	fields = ["name", "employee", "employee_name", "leave_type", "from_date", "to_date", "total_leave_days", "status"]

	mine = frappe.get_list(
		"Leave Application",
		filters={"employee": employee, "docstatus": ("!=", 2), "to_date": (">=", today), "status": ("in", ("Open", "Approved"))},
		fields=fields,
		order_by="from_date",
		limit=10,
	)

	department = None
	if cint(frappe.db.get_single_value("HR Settings", "show_leaves_of_all_department_members_in_calendar")):
		department_name = frappe.db.get_value("Employee", employee, "department")
		if department_name:
			members = frappe.get_all(
				"Employee", filters={"department": department_name, "status": "Active", "name": ("!=", employee)}, pluck="name"
			)
			department = (
				frappe.get_all(
					"Leave Application",
					filters={
						"employee": ("in", members),
						"docstatus": ("!=", 2),
						"status": ("in", ("Open", "Approved")),
						"to_date": (">=", today),
						"from_date": ("<=", add_days(today, 60)),
					},
					fields=["employee", "employee_name", "from_date", "to_date", "status"],
					order_by="from_date",
					limit=10,
				)
				if members
				else []
			)

	allocations = {}
	for row in frappe.get_all(
		"Leave Allocation",
		filters={"employee": employee, "docstatus": 1, "from_date": ("<=", today), "to_date": (">=", today)},
		fields=["leave_type", "to_date"],
	):
		allocations[row.leave_type] = {
			"to_date": str(row.to_date),
			"carry_forward": cint(frappe.get_cached_value("Leave Type", row.leave_type, "is_carry_forward")),
		}

	balances = get_leave_details(employee, today)["leave_allocation"]
	return {
		"balances": balances,
		"mine": mine,
		"department": department,
		"allocations": allocations,
		"holidays": _upcoming_holidays(employee, today),
	}


# Salary and expenses


@frappe.whitelist()
def get_salary():
	"""The latest salary slips (net pay trend), the newest slip's earnings and deductions,
	and the net pay so far this year."""
	employee = get_current_employee()
	slips = frappe.get_list(
		"Salary Slip",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "start_date", "end_date", "posting_date", "net_pay", "gross_pay", "total_deduction", "currency"],
		order_by="end_date desc",
		limit=12,
	)
	if not slips:
		return {"slips": []}

	latest = frappe.get_doc("Salary Slip", slips[0].name)
	latest.check_permission("read")
	year = getdate().year

	return {
		"slips": slips,
		"latest": {
			"name": latest.name,
			"start_date": str(latest.start_date),
			"end_date": str(latest.end_date),
			"posting_date": str(latest.posting_date),
			"payment_days": latest.payment_days,
			"currency": latest.currency,
			"gross_pay": latest.gross_pay,
			"total_deduction": latest.total_deduction,
			"net_pay": latest.net_pay,
			"total_in_words": latest.total_in_words,
			"earnings": [_component(row) for row in latest.earnings if flt(row.amount)],
			"deductions": [_component(row) for row in latest.deductions if flt(row.amount)],
		},
		"year_net_pay": sum(flt(s.net_pay) for s in slips if getdate(s.end_date).year == year),
	}


@frappe.whitelist()
def get_expenses():
	"""This year's expense claims: totals by stage, amounts by expense type, recent claims."""
	employee = get_current_employee()
	year_start = date(getdate().year, 1, 1)
	claims = frappe.get_list(
		"Expense Claim",
		filters={"employee": employee, "docstatus": ("!=", 2), "posting_date": (">=", year_start)},
		fields=["name", "posting_date", "total_claimed_amount", "total_sanctioned_amount", "approval_status", "status", "docstatus"],
		order_by="posting_date desc",
	)
	company = frappe.db.get_value("Employee", employee, "company")
	currency = frappe.get_cached_value("Company", company, "default_currency")

	stages = {"paid": 0, "approved": 0, "pending": 0, "rejected": 0}
	for claim in claims:
		if claim.approval_status == "Rejected":
			stages["rejected"] += flt(claim.total_claimed_amount)
		elif claim.status == "Paid":
			stages["paid"] += flt(claim.total_sanctioned_amount)
		elif claim.approval_status == "Approved":
			stages["approved"] += flt(claim.total_sanctioned_amount)
		else:
			stages["pending"] += flt(claim.total_claimed_amount)

	by_type = Counter()
	types_by_claim = {}
	counted = [c.name for c in claims if c.approval_status != "Rejected"]
	if claims:
		for row in frappe.get_all(
			"Expense Claim Detail",
			filters={"parenttype": "Expense Claim", "parent": ("in", [c.name for c in claims])},
			fields=["parent", "expense_type", "amount"],
		):
			types_by_claim.setdefault(row.parent, [])
			if row.expense_type not in types_by_claim[row.parent]:
				types_by_claim[row.parent].append(row.expense_type)
			if row.parent in counted:
				by_type[row.expense_type] += flt(row.amount)

	for claim in claims:
		claim.expense_types = types_by_claim.get(claim.name, [])

	return {
		"currency": currency,
		"total": sum(stages[key] for key in ("paid", "approved", "pending")),
		"stages": stages,
		"by_type": [{"expense_type": key, "amount": value} for key, value in by_type.most_common()],
		"recent": claims[:5],
	}


# Install


@frappe.whitelist(allow_guest=True)
def get_install_qr():
	"""A QR code (SVG) of the app's address, shown beside the app on wide screens."""
	url = get_url("/hrms")

	def make():
		import io

		import pyqrcode

		buffer = io.BytesIO()
		pyqrcode.create(url).svg(buffer, scale=4, module_color="#0E3B2E", background="#FFFFFF", xmldecl=False, svgns=True)
		return buffer.getvalue().decode()

	return {"url": url, "svg": frappe.cache.get_value(f"ms_hrms:install_qr:{url}", make)}


# Days


def _days(employee, from_date, to_date):
	"""One entry per date: its status, first check-in, last check-out and hours worked."""
	from_date, to_date = getdate(from_date), getdate(to_date)
	today = getdate()
	joining, relieving = frappe.get_cached_value("Employee", employee, ["date_of_joining", "relieving_date"])
	shifts = _shifts(employee, from_date, to_date)
	holidays = _holidays(employee, from_date, to_date)
	checkins = _checkins(employee, from_date, to_date)
	attendance = {
		row.attendance_date: row
		for row in frappe.get_all(
			"Attendance",
			filters={"employee": employee, "docstatus": 1, "attendance_date": ("between", (from_date, to_date))},
			fields=["attendance_date", "status", "late_entry", "early_exit", "working_hours", "shift"],
		)
	}
	leaves = _leave_dates(employee, from_date, to_date)

	days = []
	for day in _dates(from_date, to_date):
		shift = shifts.get(day)
		log = checkins.get(day)
		record = attendance.get(day)
		entry = {
			"date": str(day),
			"weekday": day.weekday(),
			"status": None,
			"first_in": None,
			"last_out": None,
			"hours": 0,
			"arrival_minutes": None,
			"early_exit": False,
			"holiday": None,
		}
		if log:
			entry["first_in"] = log.first_in.strftime("%H:%M")
			entry["last_out"] = log.last_out.strftime("%H:%M") if log.last_out else None
			end = log.last_out or (now_datetime() if day == today else None)
			if end:
				entry["hours"] = round((end - log.first_in).total_seconds() / 3600, 2)
			if shift:
				entry["arrival_minutes"] = _arrival_minutes(log.first_in, shift)
				if log.last_out:
					entry["early_exit"] = _minutes_of(log.last_out) < _minutes(shift.end_time) - cint(
						shift.early_exit_grace_period
					)
		if record and flt(record.working_hours):
			entry["hours"] = flt(record.working_hours, 2)

		if (joining and day < joining) or (relieving and day > relieving):
			entry["status"] = "future"
		elif day in holidays:
			entry["status"] = "weekly_off" if holidays[day].weekly_off else "holiday"
			entry["holiday"] = holidays[day].description
		elif day > today:
			entry["status"] = "future"
		elif day in leaves or (record and record.status == "On Leave"):
			entry["status"] = "leave"
		elif record and record.status == "Absent":
			entry["status"] = "absent"
		elif log or (record and record.status in ("Present", "Work From Home", "Half Day")):
			late = (record and record.late_entry) or (
				shift and entry["arrival_minutes"] is not None and entry["arrival_minutes"] > cint(shift.late_entry_grace_period)
			)
			# Arrival is judged against the shift; attendance marked for a shift has judged it.
			judged = (shift and entry["arrival_minutes"] is not None) or (record and record.shift)
			entry["status"] = "late" if late else ("on_time" if judged else "present")
			entry["early_exit"] = entry["early_exit"] or bool(record and record.early_exit)
		elif day == today:
			entry["status"] = "today"
		else:
			entry["status"] = "absent"

		if day == today and entry["status"] in PRESENT:
			entry["in_progress"] = not entry["last_out"]
		days.append(entry)
	return days


def _summary(days):
	"""Counts and averages over past days (today counts once the employee checked in)."""
	counts = Counter(d["status"] for d in days)
	present = [d for d in days if d["status"] in PRESENT]
	finished = [d for d in present if d["hours"] and not d.get("in_progress")]
	arrivals = [_minutes(datetime.strptime(d["first_in"], "%H:%M").time()) for d in present if d["first_in"]]
	present_count = len(present)
	judged = counts["on_time"] + counts["late"]
	expected = present_count + counts["absent"]
	hours = sum(d["hours"] for d in finished)

	return {
		"on_time": counts["on_time"],
		"late": counts["late"],
		"leave": counts["leave"],
		"absent": counts["absent"],
		"present": present_count,
		"expected": expected,
		"early_exits": sum(1 for d in present if d["early_exit"]),
		"hours": round(hours, 1),
		"avg_hours": round(hours / len(finished), 1) if finished else 0,
		"avg_arrival": _clock(sum(arrivals) / len(arrivals)) if arrivals else None,
		"judged": judged,
		"punctuality": round(counts["on_time"] / judged * 100) if judged else None,
		"attendance_rate": round(present_count / expected * 100) if expected else None,
	}


def _discipline_index(summary):
	"""0 to 100: punctuality (50%), attendance (40%) and leaving on time (10%). Without a
	shift to judge arrivals by, attendance alone."""
	if not summary["present"]:
		return None
	parts = [(0.4, summary["present"] / summary["expected"] if summary["expected"] else 1)]
	if summary["judged"]:
		parts.append((0.5, summary["on_time"] / summary["judged"]))
		parts.append((0.1, 1 - summary["early_exits"] / summary["present"]))
	return round(100 * sum(weight * value for weight, value in parts) / sum(weight for weight, _value in parts))


def _cached_summary(employee, month_start):
	"""A past month's summary; it changes only when old records do."""
	key = f"ms_hrms:attendance_summary:{employee}:{month_start}"
	summary = frappe.cache.get_value(key, expires=True)
	if summary is None:
		summary = _summary(_days(employee, month_start, get_last_day(month_start)))
		frappe.cache.set_value(key, summary, expires_in_sec=CACHE_SECONDS)
	return summary


def _monthly_trend(employee, today):
	"""Punctuality for each of the last six months, the current one included."""
	trend = []
	for offset in range(5, -1, -1):
		start = get_first_day(add_months(today, -offset))
		summary = _summary(_days(employee, start, today)) if offset == 0 else _cached_summary(employee, start)
		trend.append({"month": start.strftime("%Y-%m"), "punctuality": summary["punctuality"], "present": summary["present"]})
	return trend


def _week(employee, today):
	"""This week's working days (from the day after the weekly off) with the hours worked,
	and the hours the shifts add up to."""
	start = today - timedelta(days=(today.weekday() - _week_start(employee)) % 7)
	days = _days(employee, start, add_days(start, 6))
	shifts = _shifts(employee, start, add_days(start, 6))
	week = [d for d in days if d["status"] not in ("weekly_off",)]
	target = sum(_shift_hours(shifts.get(getdate(d["date"]))) for d in week if d["status"] not in ("holiday", "leave"))
	return {
		"days": [
			{
				"date": d["date"],
				"weekday": d["weekday"],
				"hours": d["hours"] if d["status"] in PRESENT else 0,
				"status": d["status"],
				"is_today": d["date"] == str(today),
			}
			for d in week
		],
		"total": round(sum(d["hours"] for d in week if d["status"] in PRESENT), 1),
		"target": round(target, 1),
	}


def _recent_days(employee):
	today = getdate()
	return [d for d in reversed(_days(employee, add_days(today, -30), today)) if d["first_in"]][:5]


# Notes


def _insights(employee, today, month_days):
	"""Short notes worth acting on, from this month's days."""
	notes = []
	month = _summary(month_days)

	for leave_type, remaining, to_date in _expiring_leaves(employee, today):
		notes.append(
			{
				"kind": "leave",
				"text": _("{0} days of your {1} expire on {2}.").format(
					_format_number(remaining), _(leave_type), frappe.format(to_date, {"fieldtype": "Date"})
				),
				"action": {"label": _("Plan a leave"), "route": "LeaveApplicationFormView"},
			}
		)

	if month["late"] >= 2:
		weekdays = Counter(d["weekday"] for d in month_days if d["status"] == "late")
		weekday, count = weekdays.most_common(1)[0]
		if count == month["late"]:
			text = _("You were late {0} times this month, all of them on {1}.").format(month["late"], _(WEEKDAYS[weekday]))
		else:
			text = _("You were late {0} times this month, most often on {1}.").format(month["late"], _(WEEKDAYS[weekday]))
		notes.append({"kind": "attendance", "text": text, "action": {"label": _("View details"), "route": "Insights"}})
	elif month["judged"] >= 5 and month["punctuality"] >= 90:
		notes.append(
			{
				"kind": "positive",
				"text": _("You arrived on time on {0} of {1} days this month.").format(month["on_time"], month["judged"]),
			}
		)

	missing = [d for d in month_days if d["status"] in PRESENT and not d["last_out"] and d["date"] != str(today)]
	if missing:
		notes.append(
			{
				"kind": "warning",
				"text": _("You did not check out on {0}.").format(frappe.format(missing[-1]["date"], {"fieldtype": "Date"})),
				"action": {"label": _("Request attendance"), "route": "AttendanceRequestFormView"},
			}
		)

	overtime = _overtime_hours(employee, get_first_day(today), today)
	earlier = [
		_overtime_hours(employee, get_first_day(add_months(today, -i)), get_last_day(add_months(today, -i))) for i in (1, 2, 3)
	]
	average = sum(earlier) / 3
	if overtime and overtime > average:
		notes.append(
			{
				"kind": "info",
				"text": _("Your overtime this month is {0} hours, above your average of the last 3 months ({1}).").format(
					_format_number(overtime), _format_number(round(average, 1))
				),
			}
		)

	return notes


def _expiring_leaves(employee, today):
	"""Leave that will be lost: the balance of allocations ending within 90 days whose leave
	type is not carried forward."""
	from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on

	for row in frappe.get_all(
		"Leave Allocation",
		filters={
			"employee": employee,
			"docstatus": 1,
			"from_date": ("<=", today),
			"to_date": ("between", (today, add_days(today, 90))),
		},
		fields=["leave_type", "to_date"],
	):
		if cint(frappe.get_cached_value("Leave Type", row.leave_type, "is_carry_forward")):
			continue
		remaining = flt(get_leave_balance_on(employee, row.leave_type, today, to_date=row.to_date), 2)
		if remaining > 0:
			yield row.leave_type, remaining, row.to_date


# Team


def _team(me):
	"""Active employees the user manages (reports to them) or approves."""
	user = frappe.session.user
	team = set(frappe.get_all("Employee", filters={"status": "Active", "reports_to": me}, pluck="name"))
	meta = frappe.get_meta("Employee")
	for field in (
		"leave_approver",
		"expense_approver",
		"shift_request_approver",
		"custom_permission_approver",
		"custom_overtime_approver",
	):
		if meta.has_field(field):
			team |= set(frappe.get_all("Employee", filters={"status": "Active", field: user}, pluck="name"))

	departments = frappe.get_all(
		"Department Approver", filters={"parenttype": "Department", "approver": user}, pluck="parent", distinct=True
	)
	if departments:
		team |= set(frappe.get_all("Employee", filters={"status": "Active", "department": ("in", departments)}, pluck="name"))

	team.discard(me)
	return sorted(team)


# Sources


def _shifts(employee, from_date, to_date):
	"""The shift type on each date: an active assignment, else the employee's default shift."""
	assignments = frappe.get_all(
		"Shift Assignment",
		filters={"employee": employee, "docstatus": 1, "status": "Active", "start_date": ("<=", to_date)},
		or_filters=[["end_date", "is", "not set"], ["end_date", ">=", from_date]],
		fields=["shift_type", "start_date", "end_date"],
		order_by="start_date desc",
	)
	default = frappe.get_cached_value("Employee", employee, "default_shift")
	result = {}
	for day in _dates(getdate(from_date), getdate(to_date)):
		name = next(
			(a.shift_type for a in assignments if a.start_date <= day and (not a.end_date or a.end_date >= day)), default
		)
		result[day] = _shift_type(name) if name else None
	return result


def _shift_type(name):
	return frappe.get_cached_value(
		"Shift Type",
		name,
		["name", "start_time", "end_time", "late_entry_grace_period", "early_exit_grace_period"],
		as_dict=True,
	)


def _holidays(employee, from_date, to_date):
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return {}
	return {
		row.holiday_date: row
		for row in frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list, "holiday_date": ("between", (from_date, to_date))},
			fields=["holiday_date", "description", "weekly_off"],
		)
	}


def _is_holiday(employee, day):
	return day in _holidays(employee, day, day)


def _checkins(employee, from_date, to_date):
	"""The first check-in and the last check-out of each date. Logs without a type (some
	devices) count as check-ins; a day with only check-outs has no check-in."""
	rows = frappe.db.sql(
		"""select date(time) as day,
			min(case when log_type = 'IN' then time end) as first_in,
			max(case when log_type = 'OUT' then time end) as last_out,
			min(case when ifnull(log_type, '') = '' then time end) as first_untyped
		from `tabEmployee Checkin`
		where employee = %s and time >= %s and time < %s
		group by date(time)""",
		(employee, from_date, add_days(to_date, 1)),
		as_dict=True,
	)
	result = {}
	for row in rows:
		row.first_in = row.first_in or row.first_untyped
		if not row.first_in:
			continue
		if row.last_out and row.last_out <= row.first_in:
			row.last_out = None
		result[row.day] = row
	return result


def _leave_dates(employee, from_date, to_date):
	dates = set()
	for leave in frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ("<=", to_date),
			"to_date": (">=", from_date),
		},
		fields=["from_date", "to_date"],
	):
		dates.update(_dates(max(leave.from_date, from_date), min(leave.to_date, to_date)))
	return dates


def _overtime_hours(employee, from_date, to_date):
	request = frappe.qb.DocType("Overtime Request")
	hours = (
		frappe.qb.from_(request)
		.select(Sum(request.requested_hours))
		.where(
			(request.employee == employee)
			& (request.status == "Approved")
			& (request.docstatus != 2)
			& (request.overtime_date[from_date:to_date])
		)
	).run()[0][0]
	return flt(hours, 1)


def _permission_hours(employee, from_date, to_date):
	request = frappe.qb.DocType("Permission Request")
	seconds = (
		frappe.qb.from_(request)
		.select(Sum(request.duration))
		.where(
			(request.employee == employee)
			& (request.status == "Approved")
			& (request.docstatus != 2)
			& (request.permission_date[from_date:to_date])
		)
	).run()[0][0]
	return flt(flt(seconds) / 3600, 1)


def _upcoming_holidays(employee, today, limit=5):
	"""The next public holidays (weekly offs left out)."""
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return []
	return [
		{"date": str(row.holiday_date), "description": frappe.utils.strip_html(row.description or "").strip()}
		for row in frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list, "weekly_off": 0, "holiday_date": (">=", today)},
			fields=["holiday_date", "description"],
			order_by="holiday_date",
			limit=limit,
		)
	]


def _next_holiday(employee, today):
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if not holiday_list:
		return None
	holiday = frappe.get_all(
		"Holiday",
		filters={"parent": holiday_list, "weekly_off": 0, "holiday_date": (">=", today)},
		fields=["holiday_date", "description"],
		order_by="holiday_date",
		limit=1,
	)
	if not holiday:
		return None
	return {
		"date": str(holiday[0].holiday_date),
		"description": frappe.utils.strip_html(holiday[0].description or "").strip(),
		"days_left": (holiday[0].holiday_date - today).days,
	}


def _latest_salary_slip(employee):
	slip = frappe.get_list(
		"Salary Slip",
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "start_date", "end_date", "posting_date", "net_pay", "currency"],
		order_by="end_date desc",
		limit=1,
	)
	return slip[0] if slip else None


def _component(row):
	return {"component": row.salary_component, "abbr": row.abbr, "amount": row.amount}


# Weeks


def _week_start(employee):
	"""The weekday a week starts on: the day after the weekly off, else System Settings'
	first day of the week."""
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	if holiday_list:
		offs = frappe.get_all(
			"Holiday", filters={"parent": holiday_list, "weekly_off": 1}, pluck="holiday_date", limit=60, order_by="holiday_date desc"
		)
		if offs:
			weekday = Counter(d.weekday() for d in offs).most_common(1)[0][0]
			return (weekday + 1) % 7
	first = frappe.db.get_single_value("System Settings", "first_day_of_the_week") or "Sunday"
	return WEEKDAYS.index(first)


def _working_weekdays(employee):
	"""The weekdays that are not weekly offs, in week order."""
	start = _week_start(employee)
	holiday_list = get_holiday_list_for_employee(employee, raise_exception=False)
	offs = set()
	if holiday_list:
		offs = {
			d.weekday()
			for d in frappe.get_all(
				"Holiday", filters={"parent": holiday_list, "weekly_off": 1}, pluck="holiday_date", limit=60, order_by="holiday_date desc"
			)
		}
	order = [(start + i) % 7 for i in range(7)]
	return [(index, WEEKDAYS[index]) for index in order if index not in offs]


# Time


def _dates(from_date, to_date):
	day = from_date
	while day <= to_date:
		yield day
		day = add_days(day, 1)


def _minutes(value):
	"""Minutes after midnight of a time or a timedelta (Time fields)."""
	if value is None:
		return 0
	if isinstance(value, timedelta):
		return value.total_seconds() / 60
	return value.hour * 60 + value.minute + value.second / 60


def _minutes_of(moment):
	return _minutes(moment.time())


def _arrival_minutes(first_in, shift):
	"""Minutes after the shift start (negative when early)."""
	return round(_minutes_of(first_in) - _minutes(shift.start_time))


def _shift_hours(shift):
	if not shift:
		return 0
	length = _minutes(shift.end_time) - _minutes(shift.start_time)
	return (length if length > 0 else length + 1440) / 60


def _shift_times(shift):
	if not shift:
		return None
	return {"name": shift.name, "start": _clock(_minutes(shift.start_time)), "end": _clock(_minutes(shift.end_time))}


def _clock(minutes):
	minutes = round(minutes) % 1440
	return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _format_number(value):
	return f"{flt(value):g}"
