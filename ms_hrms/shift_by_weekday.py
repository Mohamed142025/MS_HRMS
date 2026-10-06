"""Shift Assignment Tool: shifts by day of the week.

With "تحديد الشيفت حسب أيام الأسبوع" on, the Assign Shift action takes a table of day
ranges, each with its shift type ("from Saturday to Wednesday: Main"), instead of one shift
type for every day. For each chosen employee, every date from the start to the end date
gets the shift of its weekday; dates in the employee's Holiday List are skipped, and
consecutive dates with the same shift make one Shift Assignment.

An employee is left out, with the reason in the result, when they have no Holiday List
for the period or already have an active Shift Assignment within it. Each employee's
assignments are made together: if one fails, none of theirs is kept.

Off, the tool behaves exactly as Frappe HR ships it.
"""

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import add_days, date_diff, escape_html, formatdate, get_link_to_form, getdate

from hrms.hr.doctype.shift_assignment_tool.shift_assignment_tool import (
	ShiftAssignmentTool,
	create_shift_assignment,
)
from hrms.utils.holiday_list import get_holiday_dates_between, get_holiday_list_for_employee

TOOL = "Shift Assignment Tool"
FLAG = "custom_shift_by_weekday"
RANGES = "custom_weekday_shifts"
MODULE = "Custom Hrms"
# The week as it is read here: Saturday first.
WEEK = ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
MAX_DAYS = 366
# Up to this many employees are assigned while the user waits; more go to the background.
SYNC_LIMIT = 30
DONE_EVENT = "ms_hrms_weekday_shifts_done"

ASSIGN_SHIFT = 'doc.action === "Assign Shift"'
WEEKDAY_MODE = f"{ASSIGN_SHIFT} && doc.{FLAG}"


# Setup ----------------------------------------------------------------------------------


def setup():
	"""The tool's fields for this mode; run after every migrate."""
	create_custom_fields(
		{
			TOOL: [
				{
					"fieldname": FLAG,
					"label": "تحديد الشيفت حسب أيام الأسبوع",
					"fieldtype": "Check",
					"insert_after": "action",
					"depends_on": f"eval:{ASSIGN_SHIFT}",
					"description": "شيفت لكل مجموعة أيام بدل شيفت واحد لكل الأيام. أيام قائمة عطلات الموظف لا يُعيَّن لها شيفت.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_weekday_shifts_section",
					"label": "شيفتات أيام الأسبوع",
					"fieldtype": "Section Break",
					# After the assignment details, so their dates and status stay in their section.
					"insert_after": "end_date",
					"depends_on": f"eval:{WEEKDAY_MODE}",
					"module": MODULE,
				},
				{
					"fieldname": RANGES,
					"label": "شيفتات أيام الأسبوع",
					"fieldtype": "Table",
					"options": "Weekday Shift Range",
					"insert_after": "custom_weekday_shifts_section",
					"depends_on": f"eval:{WEEKDAY_MODE}",
					"description": "الأسبوع من السبت إلى الجمعة. اليوم الذي ليس في أي سطر لا يُعيَّن له شيفت.",
					"module": MODULE,
				},
				{
					"fieldname": "custom_weekday_summary",
					"fieldtype": "HTML",
					"insert_after": RANGES,
					"depends_on": f"eval:{WEEKDAY_MODE}",
					"module": MODULE,
				},
			]
		},
		update=True,
	)

	# The one shift type gives way to the table in this mode, and the end date is required.
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for fieldname, prop, value in (
		("shift_type", "depends_on", f"eval:{ASSIGN_SHIFT} && !doc.{FLAG}"),
		("shift_type", "mandatory_depends_on", f"eval:{ASSIGN_SHIFT} && !doc.{FLAG}"),
		("end_date", "mandatory_depends_on", f"eval:{WEEKDAY_MODE}"),
	):
		current = frappe.db.get_value(
			"Property Setter", {"doc_type": TOOL, "field_name": fieldname, "property": prop}, "value"
		)
		if current != value:
			make_property_setter(TOOL, fieldname, prop, value, "Code")
	frappe.clear_cache(doctype=TOOL)


# The tool -------------------------------------------------------------------------------


class WeekdayShiftAssignmentTool(ShiftAssignmentTool):
	def by_weekday(self):
		return self.action == "Assign Shift" and bool(self.get(FLAG))

	def get_query_for_employees_with_shifts(self):
		# Employees who already have shifts in the period stay in the list: assigning them
		# is refused with their shifts named, rather than having them silently vanish.
		if not self.by_weekday():
			return super().get_query_for_employees_with_shifts()
		ShiftAssignment = frappe.qb.DocType("Shift Assignment")
		return frappe.qb.from_(ShiftAssignment).select(ShiftAssignment.employee).where(ShiftAssignment.name.isnull())

	@frappe.whitelist()
	def assign_shifts_by_weekday(self, employees: list):
		if not self.by_weekday():
			frappe.throw(_("فعّل «تحديد الشيفت حسب أيام الأسبوع» أولاً."))
		employees = list(dict.fromkeys(frappe.parse_json(employees) if isinstance(employees, str) else employees or []))
		if not employees:
			frappe.throw(_("اختر موظفاً واحداً على الأقل."))
		for fieldname, label in (("company", _("Company")), ("start_date", _("Start Date")), ("end_date", _("End Date"))):
			if not self.get(fieldname):
				frappe.throw(_("حدد {0}.").format(label))
		if getdate(self.end_date) < getdate(self.start_date):
			frappe.throw(_("تاريخ النهاية قبل تاريخ البداية."))
		if date_diff(self.end_date, self.start_date) + 1 > MAX_DAYS:
			frappe.throw(_("المدة أطول من سنة؛ قسّمها على أكثر من مرة."))
		day_shifts = get_day_shifts(self.get(RANGES))

		if len(employees) <= SYNC_LIMIT:
			return self._assign_by_weekday(employees, day_shifts)

		frappe.enqueue(
			self._assign_by_weekday,
			timeout=3000,
			employees=employees,
			day_shifts=day_shifts,
			notify_user=frappe.session.user,
		)
		frappe.msgprint(
			_("بدأ تعيين الشيفتات لـ {0} موظف في الخلفية، وتظهر النتيجة عند الانتهاء.").format(len(employees)),
			alert=True,
			indicator="blue",
		)
		return {"queued": True}

	def _assign_by_weekday(self, employees, day_shifts, notify_user=None):
		success, failure = [], []
		for count, employee in enumerate(employees, 1):
			employee_name = frappe.db.get_value("Employee", employee, "employee_name") or employee
			savepoint = "weekday_shift_assignment"
			try:
				frappe.db.savepoint(savepoint)
				reason = self._refusal(employee)
				if reason:
					failure.append({"employee": employee, "employee_name": employee_name, "reason": reason})
					continue
				runs = plan_assignments(
					day_shifts, self.start_date, self.end_date, self._holidays(employee)
				)
				if not runs:
					failure.append(
						{
							"employee": employee,
							"employee_name": employee_name,
							"reason": _("كل أيام الفترة إجازات أو بدون شيفت، فلا يوجد ما يُعيَّن."),
						}
					)
					continue
				created = [
					create_shift_assignment(
						employee,
						self.company,
						shift_type,
						start,
						end,
						self.status,
						self.shift_location,
					).name
					for shift_type, start, end in runs
				]
			except Exception as e:
				frappe.db.rollback(save_point=savepoint)
				frappe.log_error(title=f"Weekday shift assignment failed for {employee}", reference_doctype=TOOL)
				failure.append(
					{
						"employee": employee,
						"employee_name": employee_name,
						"reason": frappe.utils.strip_html(str(e)) or _("خطأ غير متوقع"),
					}
				)
			else:
				success.append({"employee": employee, "employee_name": employee_name, "assignments": created})
			finally:
				frappe.publish_progress(count * 100 / len(employees), title=_("تعيين الشيفتات..."))

		frappe.clear_messages()
		result = {"success": success, "failure": failure}
		if notify_user:
			frappe.publish_realtime(DONE_EVENT, result, user=notify_user, after_commit=True)
		return result

	def _refusal(self, employee):
		"""Why the employee cannot be assigned, if they cannot."""
		for as_on in (self.start_date, self.end_date):
			assigned = get_holiday_list_for_employee(employee, raise_exception=False, as_on=as_on, as_dict=True)
			if not assigned:
				return _("ليس له قائمة عطلات في {0}. عيّن له قائمة عطلات (Holiday List Assignment) أو حدد قائمة افتراضية للشركة.").format(
					formatdate(as_on)
				)
			# Holidays past the list's own dates are not in it, so those days would get shifts.
			dates = frappe.db.get_value("Holiday List", assigned.holiday_list, ["from_date", "to_date"])
			if not dates:
				return _("قائمة العطلات {0} المعيّنة له غير موجودة. أنشئها أو عيّن له قائمة أخرى.").format(
					frappe.bold(assigned.holiday_list)
				)
			from_date, to_date = dates
			if not (getdate(from_date) <= getdate(as_on) <= getdate(to_date)):
				return _("قائمة العطلات {0} من {1} إلى {2} لا تغطي {3}. مدّ القائمة أو غيّر الفترة.").format(
					get_link_to_form("Holiday List", assigned.holiday_list),
					formatdate(from_date),
					formatdate(to_date),
					formatdate(as_on),
				)

		existing = frappe.get_all(
			"Shift Assignment",
			filters={
				"employee": employee,
				"docstatus": 1,
				"status": "Active",
				"start_date": ["<=", self.end_date],
			},
			or_filters=[["end_date", ">=", self.start_date], ["end_date", "is", "not set"]],
			fields=["name", "shift_type", "start_date", "end_date"],
			order_by="start_date asc",
		)
		existing = [
			row for row in existing if not row.end_date or getdate(row.end_date) >= getdate(self.start_date)
		]
		if existing:
			shown = "، ".join(
				_("{0} ({1} من {2} إلى {3})").format(
					get_link_to_form("Shift Assignment", row.name),
					escape_html(row.shift_type),
					formatdate(row.start_date),
					formatdate(row.end_date) if row.end_date else _("مفتوح"),
				)
				for row in existing[:5]
			)
			more = _(" و{0} غيرها").format(len(existing) - 5) if len(existing) > 5 else ""
			return _("لديه شيفتات قائمة في نفس الفترة: {0}{1}. ألغِها أو غيّر الفترة.").format(shown, more)

	def _holidays(self, employee):
		"""The employee's holidays in the period, from the list in force on each date."""
		holidays = set()
		start = getdate(self.start_date)
		end = getdate(self.end_date)
		date = start
		while date <= end:
			assigned = get_holiday_list_for_employee(employee, raise_exception=False, as_on=date, as_dict=True)
			# The list stays in force until the next assignment takes over (or the period ends).
			next_change = _next_holiday_list_change(employee, date, end)
			if assigned:
				holidays.update(
					getdate(d) for d in get_holiday_dates_between(assigned.holiday_list, date, next_change)
				)
			date = add_days(next_change, 1)
		return holidays


def _next_holiday_list_change(employee, date, end):
	"""The last date before the employee's (or their company's) holiday list changes."""
	company = frappe.db.get_value("Employee", employee, "company")
	changes = frappe.get_all(
		"Holiday List Assignment",
		filters={"assigned_to": ["in", [employee, company]], "docstatus": 1, "from_date": ["between", [add_days(date, 1), end]]},
		pluck="from_date",
		order_by="from_date asc",
		limit=1,
	)
	return add_days(changes[0], -1) if changes else end


# Planning -------------------------------------------------------------------------------


def get_day_shifts(ranges):
	"""{weekday: shift type} from the table's day ranges, refusing overlaps and reversed
	ranges with the row numbers."""
	if not ranges:
		frappe.throw(_("أضف سطراً واحداً على الأقل في «شيفتات أيام الأسبوع»."))
	day_shifts, day_rows = {}, {}
	for idx, row in enumerate(ranges, 1):
		row = frappe._dict(row.as_dict() if hasattr(row, "as_dict") else row)
		if not (row.from_day and row.to_day and row.shift_type):
			frappe.throw(_("السطر {0}: اختر من يوم وإلى يوم ونوع الوردية.").format(idx))
		if row.from_day not in WEEK or row.to_day not in WEEK:
			frappe.throw(_("السطر {0}: يوم غير معروف.").format(idx))
		start, end = WEEK.index(row.from_day), WEEK.index(row.to_day)
		if start > end:
			frappe.throw(
				_("السطر {0}: «من {1}» بعد «إلى {2}». الأسبوع يبدأ السبت؛ قسّم المدة على سطرين.").format(
					idx, _(row.from_day), _(row.to_day)
				)
			)
		if not frappe.db.exists("Shift Type", row.shift_type):
			frappe.throw(_("السطر {0}: نوع الوردية {1} غير موجود.").format(idx, row.shift_type))
		for day in WEEK[start : end + 1]:
			if day in day_shifts:
				frappe.throw(_("يوم {0} مكرر في السطرين {1} و{2}.").format(_(day), day_rows[day], idx))
			day_shifts[day] = row.shift_type
			day_rows[day] = idx
	return day_shifts


def plan_assignments(day_shifts, start_date, end_date, holidays):
	"""[(shift type, start, end)]: each date gets its weekday's shift; holidays and days
	without a shift break the run, and consecutive dates with the same shift are one."""
	runs = []
	date, end = getdate(start_date), getdate(end_date)
	while date <= end:
		shift_type = None if date in holidays else day_shifts.get(WEEK[(date.weekday() + 2) % 7])
		if shift_type and runs and runs[-1][0] == shift_type and runs[-1][2] == add_days(date, -1):
			runs[-1][2] = date
		elif shift_type:
			runs.append([shift_type, date, date])
		date = add_days(date, 1)
	return [tuple(run) for run in runs]
