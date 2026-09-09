from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, get_datetime, get_first_day, get_last_day, get_time


PENALTY_TYPES = {"Late Entry", "Early Exit"}


def get_applicable_policy(employee, policy_name=None, as_of=None):
	if policy_name:
		policy = frappe.get_doc("Attendance Penalty Policy", policy_name)
		if not policy.enabled:
			frappe.throw(_("Policy {0} is disabled.").format(policy_name))
		return policy

	employee_department = frappe.db.get_value("Employee", employee, "department")
	filters = {"enabled": 1}
	for apply_on, scope in (("Employee", employee), ("Department", employee_department), ("All Employees", None)):
		candidate_filters = {**filters, "apply_on": apply_on}
		if apply_on == "Employee":
			candidate_filters["employee"] = scope
		elif apply_on == "Department":
			candidate_filters["department"] = scope
		name = frappe.db.get_value("Attendance Penalty Policy", candidate_filters, "name")
		if name:
			return frappe.get_doc("Attendance Penalty Policy", name)
	return None


def get_period_start(attendance_date, reset_period):
	attendance_date = getdate(attendance_date)
	if reset_period == "Quarterly":
		month = ((attendance_date.month - 1) // 3) * 3 + 1
		return date(attendance_date.year, month, 1)
	if reset_period == "Yearly":
		return date(attendance_date.year, 1, 1)
	if reset_period == "Never":
		return date(1900, 1, 1)
	return get_first_day(attendance_date)


def get_period_end(attendance_date, reset_period):
	attendance_date = getdate(attendance_date)
	if reset_period == "Quarterly":
		month = ((attendance_date.month - 1) // 3) * 3 + 3
		return date(attendance_date.year, month, calendar.monthrange(attendance_date.year, month)[1])
	if reset_period == "Yearly":
		return date(attendance_date.year, 12, 31)
	if reset_period == "Never":
		return date(9999, 12, 31)
	return get_last_day(attendance_date)


def get_existing_occurrences(employee, policy, payroll_period, attendance_date):
	period_start = get_period_start(attendance_date, policy.reset_period)
	period_end = get_period_end(attendance_date, policy.reset_period)
	period_filter = "d.payroll_period = %(payroll_period)s" if payroll_period else "d.attendance_date between %(period_start)s and %(period_end)s"
	rows = frappe.db.sql(
		f"""
		select d.name
		from `tabAttendance Penalty Detail` d
		join `tabAttendance Penalty Processing` p on p.name = d.parent
		where p.docstatus = 1
			and d.employee = %(employee)s
			and {period_filter}
			and d.policy = %(policy)s
			and d.occurrence_number > 0
		""",
		{"employee": employee, "policy": policy.name, "payroll_period": payroll_period, "period_start": period_start, "period_end": period_end},
		as_dict=True,
	)
	return len(rows)


def get_existing_grace_occurrences(employee, policy, payroll_period, attendance_date):
	period_start = get_period_start(attendance_date, policy.reset_period)
	period_end = get_period_end(attendance_date, policy.reset_period)
	period_filter = "d.payroll_period = %(payroll_period)s" if payroll_period else "d.attendance_date between %(period_start)s and %(period_end)s"
	return frappe.db.sql(
		f"""
		select count(d.name)
		from `tabAttendance Penalty Detail` d
		join `tabAttendance Penalty Processing` p on p.name = d.parent
		where p.docstatus = 1
			and d.employee = %(employee)s
			and {period_filter}
			and d.policy = %(policy)s
			and d.occurrence_number = 0
			and d.deduction_type = 'No Deduction'
		""",
		{"employee": employee, "policy": policy.name, "payroll_period": payroll_period, "period_start": period_start, "period_end": period_end},
	)[0][0]


def match_rule(policy, penalty_type, occurrence_number, counted_minutes):
	rules = policy.entry_rules if penalty_type == "Late Entry" else policy.exit_rules
	matches = [
		rule
		for rule in rules
		if rule.enabled
		and cint(rule.occurrence_number) == cint(occurrence_number)
		and (not cint(rule.max_late_minutes) or counted_minutes <= cint(rule.max_late_minutes))
	]
	return sorted(matches, key=lambda rule: cint(rule.max_late_minutes) or 10**9)[0] if matches else None


def get_shift_window(attendance):
	shift_name = attendance.get("shift") or attendance.get("shift_type")
	if not shift_name:
		shift_name = frappe.db.get_value("Employee", attendance.employee, "default_shift")
	if not shift_name or not frappe.db.exists("Shift Type", shift_name):
		return shift_name, None, None
	shift = frappe.get_cached_doc("Shift Type", shift_name)
	start_time = shift.start_time
	end_time = shift.end_time
	if not start_time or not end_time:
		return shift_name, None, None
	attendance_date = getdate(attendance.attendance_date)
	start = datetime.combine(attendance_date, _as_time(start_time))
	end = datetime.combine(attendance_date, _as_time(end_time))
	if end <= start:
		end += timedelta(days=1)
	return shift_name, start, end


def _as_time(value):
	if isinstance(value, time):
		return value
	if isinstance(value, datetime):
		return value.time()
	return get_time(value)


def get_attendance_rows(employee, from_date, to_date):
	filters = {"employee": employee, "attendance_date": ["between", [from_date, to_date]]}
	attendance_fields = ["name", "employee", "attendance_date", "shift", "in_time", "out_time"]
	available = {field.fieldname for field in frappe.get_meta("Attendance").fields}
	fields = [field for field in attendance_fields if field in available]
	rows = frappe.get_all("Attendance", filters=filters, fields=fields, order_by="attendance_date asc")
	for row in rows:
		if not row.get("in_time") or not row.get("out_time"):
			checkins = frappe.get_all(
				"Employee Checkin",
				filters={"employee": employee, "time": ["between", [f"{row.attendance_date} 00:00:00", f"{row.attendance_date} 23:59:59"]]},
				fields=["time", "log_type"],
				order_by="time asc",
			)
			ins = [get_datetime(item.time) for item in checkins if item.log_type == "IN"]
			outs = [get_datetime(item.time) for item in checkins if item.log_type == "OUT"]
			row.in_time = row.get("in_time") or (ins[0] if ins else None)
			row.out_time = row.get("out_time") or (outs[-1] if outs else None)
	return rows


def calculate_penalty(policy, attendance, penalty_type, actual_minutes, shift_start, shift_end, occurrence_number=None, grace_available=True):
	grace = cint(policy.entry_grace_period if penalty_type == "Late Entry" else policy.exit_grace_period)
	actual_minutes = max(0, cint(actual_minutes))
	if actual_minutes <= grace and grace_available:
		return {
			"actual_minutes": actual_minutes,
			"grace_period": grace,
			"counted_minutes": 0,
			"occurrence_number": 0,
			"deduction_type": "No Deduction",
			"deduction_value": 0,
			"deduction_amount": 0,
			"review_required": 0,
			"remarks": _("Within grace period; occurrence was not counted."),
		}
	counted_minutes = max(0, actual_minutes - grace)
	occurrence_number = occurrence_number or 1
	rule = match_rule(policy, penalty_type, occurrence_number, counted_minutes)
	if not rule:
		return {
			"actual_minutes": actual_minutes,
			"grace_period": grace,
			"counted_minutes": counted_minutes,
			"occurrence_number": occurrence_number,
			"deduction_type": "Review Required",
			"deduction_value": 0,
			"deduction_amount": 0,
			"review_required": 1,
			"remarks": _("No matching penalty rule; HR review is required."),
		}
	return {
		"actual_minutes": actual_minutes,
		"grace_period": grace,
		"counted_minutes": counted_minutes,
		"occurrence_number": occurrence_number,
		"deduction_type": rule.deduction_type,
		"deduction_value": flt(rule.deduction_value),
		"deduction_amount": 0,
		"review_required": 0,
		"remarks": None,
	}


def get_salary_basis(employee, policy, from_date, to_date, salary_component=None):
	slip_fields = {field.fieldname for field in frappe.get_meta("Salary Slip").fields}
	fields = [field for field in ("name", "company", "gross_pay", "start_date", "end_date") if field in slip_fields]
	slip = frappe.get_all(
		"Salary Slip",
		filters={
			"employee": employee,
			"docstatus": 1,
			"start_date": ["<=", to_date],
			"end_date": [">=", from_date],
		},
		fields=fields,
		order_by="start_date desc",
		limit=1,
	)
	if not slip:
		assignment = frappe.db.get_value(
			"Salary Structure Assignment",
			{"employee": employee, "docstatus": 1, "from_date": ["<=", to_date]},
			["base", "salary_structure"],
			as_dict=True,
		)
		if assignment and policy.deduction_based_on == "Basic Salary":
			return flt(assignment.base), None
		return 0, None
	slip = slip[0]
	if policy.deduction_based_on == "Gross Salary":
		return flt(slip.gross_pay), slip
	if policy.deduction_based_on == "Salary Component":
		amount = frappe.db.get_value(
			"Salary Detail",
			{"parent": slip.name, "parenttype": "Salary Slip", "salary_component": salary_component, "parentfield": "earnings"},
			"amount",
		)
		return flt(amount), slip
	basic_amount = frappe.db.get_value(
		"Salary Detail",
		{"parent": slip.name, "parenttype": "Salary Slip", "salary_component": "Basic Salary", "parentfield": "earnings"},
		"amount",
	)
	if basic_amount is not None:
		return flt(basic_amount), slip
	assignment = frappe.db.get_value(
		"Salary Structure Assignment",
		{"employee": employee, "docstatus": 1, "from_date": ["<=", to_date]},
		"base",
		order_by="from_date desc",
	)
	return flt(assignment), slip


def calculate_deduction_amount(deduction_type, deduction_value, salary_basis, policy):
	daily_rate = Decimal(str(flt(salary_basis))) / Decimal(str(flt(policy.salary_divisor)))
	hourly_rate = daily_rate / Decimal(str(flt(policy.working_hours_per_day)))
	value = Decimal(str(flt(deduction_value)))
	amounts = {
		"No Deduction": Decimal("0"),
		"Minutes": hourly_rate * value / Decimal("60"),
		"Hour": hourly_rate * value,
		"Quarter Day": daily_rate / Decimal("4") * (value or Decimal("1")),
		"Half Day": daily_rate / Decimal("2") * (value or Decimal("1")),
		"Full Day": daily_rate * (value or Decimal("1")),
	}
	return flt(amounts.get(deduction_type, Decimal("0")), 2)


def ensure_salary_component(component_name=None):
	component_name = component_name or "Late Attendance Deduction"
	if frappe.db.exists("Salary Component", component_name):
		return component_name
	component = frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": component_name,
			"type": "Deduction",
		}
	)
	component.insert(ignore_permissions=True)
	return component.name


def calculate_for_employee(employee, from_date, to_date, policy, payroll_period=None):
	rows = []
	occurrence_number = get_existing_occurrences(employee, policy, payroll_period, from_date)
	grace_occurrences = get_existing_grace_occurrences(employee, policy, payroll_period, from_date)
	allowed_grace_occurrences = cint(policy.allowed_grace_occurrences)
	salary_basis, _slip = get_salary_basis(employee, policy, from_date, to_date, policy.salary_component)
	for attendance in get_attendance_rows(employee, from_date, to_date):
		shift_type, shift_start, shift_end = get_shift_window(attendance)
		if not shift_start or not shift_end:
			continue
		checkin = get_datetime(attendance.get("in_time")) if attendance.get("in_time") else None
		checkout = get_datetime(attendance.get("out_time")) if attendance.get("out_time") else None
		if checkin and checkin > shift_start:
			actual_minutes = (checkin - shift_start).total_seconds() / 60
			within_grace = actual_minutes <= cint(policy.entry_grace_period)
			grace_available = not within_grace or not allowed_grace_occurrences or grace_occurrences < allowed_grace_occurrences
			if within_grace:
				grace_occurrences += 1
			if not within_grace or not grace_available:
				occurrence_number += 1
			result = calculate_penalty(policy, attendance, "Late Entry", actual_minutes, shift_start, shift_end, occurrence_number, grace_available)
			result["deduction_amount"] = calculate_deduction_amount(result["deduction_type"], result["deduction_value"], salary_basis, policy)
			rows.append(_detail(employee, attendance, payroll_period, shift_type, shift_start, shift_end, checkin, checkout, "Late Entry", policy, result))
		if checkout and checkout < shift_end:
			actual_minutes = (shift_end - checkout).total_seconds() / 60
			within_grace = actual_minutes <= cint(policy.exit_grace_period)
			grace_available = not within_grace or not allowed_grace_occurrences or grace_occurrences < allowed_grace_occurrences
			if within_grace:
				grace_occurrences += 1
			if not within_grace or not grace_available:
				occurrence_number += 1
			result = calculate_penalty(policy, attendance, "Early Exit", actual_minutes, shift_start, shift_end, occurrence_number, grace_available)
			result["deduction_amount"] = calculate_deduction_amount(result["deduction_type"], result["deduction_value"], salary_basis, policy)
			rows.append(_detail(employee, attendance, payroll_period, shift_type, shift_start, shift_end, checkin, checkout, "Early Exit", policy, result))
	return rows


def _detail(employee, attendance, payroll_period, shift_type, shift_start, shift_end, checkin, checkout, penalty_type, policy, result):
	return {
		"employee": employee,
		"attendance": attendance.name,
		"attendance_date": attendance.attendance_date,
		"payroll_period": payroll_period,
		"shift_type": shift_type,
		"shift_start": shift_start,
		"shift_end": shift_end,
		"checkin_time": checkin,
		"checkout_time": checkout,
		"penalty_type": penalty_type,
		"policy": policy.name,
		**result,
	}
