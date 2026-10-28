"""Who came in on a day, by shift: not checked in yet (today), absent, on a late arrival
permission, present, on leave or duty, on holiday, or without a shift
(ms_hrms.attendance_watch). Seen by the roles that watch attendance."""

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from ms_hrms.attendance_watch import STATUS_LABELS, STATUSES, check_can_watch, get_day

MISSING = ("not_in", "absent")


def execute(filters=None):
	check_can_watch()
	filters = frappe._dict(filters or {})
	day = getdate(filters.date or nowdate())
	if day > getdate(nowdate()):
		frappe.throw(_("Choose today or a past day."))

	rows = get_day(day, company=filters.company, department=filters.department, shift_type=filters.shift_type)
	counts = {status: sum(row.status == status for row in rows) for status in STATUSES}
	if filters.status == "missing":
		rows = [row for row in rows if row.status in MISSING]
	elif filters.status:
		rows = [row for row in rows if row.status == filters.status]
	rows.sort(key=lambda row: (STATUSES.index(row.status), -(row.get("minutes_late") or 0), row.employee_name or ""))

	data = [
		{
			"employee": row.employee,
			"employee_name": row.employee_name,
			"department": row.department,
			"shift": row.shift,
			"shift_start": row.shift_start.strftime("%H:%M:%S") if row.get("shift_start") else None,
			"first_in": row.get("first_in"),
			"status": row.status,
			"status_label": _(STATUS_LABELS[row.status]),
			"minutes_late": row.get("minutes_late"),
			"phone": row.phone,
		}
		for row in rows
	]
	return get_columns(), data, None, None, get_summary(counts)


def get_columns():
	return [
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 140},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 200},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 180},
		{"label": _("Shift"), "fieldname": "shift", "fieldtype": "Link", "options": "Shift Type", "width": 110},
		{"label": _("Starts At"), "fieldname": "shift_start", "fieldtype": "Time", "width": 100},
		{"label": _("First Check-in"), "fieldname": "first_in", "fieldtype": "Datetime", "width": 160},
		{"label": _("Status"), "fieldname": "status_label", "fieldtype": "Data", "width": 170},
		{"label": _("Minutes Late"), "fieldname": "minutes_late", "fieldtype": "Int", "width": 110},
		{"label": _("Mobile"), "fieldname": "phone", "fieldtype": "Data", "width": 140},
	]


def get_summary(counts):
	indicators = {"not_in": "Red", "absent": "Red", "permission": "Orange", "upcoming": "Blue", "present": "Green"}
	return [
		{"value": counts[status], "label": _(STATUS_LABELS[status]), "indicator": indicators.get(status, "Grey"), "datatype": "Int"}
		for status in STATUSES
		if counts[status] or status in indicators
	]
