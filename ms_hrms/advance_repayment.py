"""Repayment plans for employee advances.

Once the manager approves (submits) an advance, HR sets the number of months it is repaid
over and the first month, and the schedule lists one installment a month. When a month
comes, its installment goes to that month's salary as an Additional Salary of the
deduction set in Payroll Settings. An installment that the month's salary slip went
without, or whose Additional Salary was cancelled, is marked Missed; HR moves the
remaining installments on from a month, or postpones one to after the last.

An installment is:
- Scheduled: not sent to payroll yet. An advance not paid yet waits, whatever the month.
- Due: its Additional Salary waits for the month's salary slip.
- Deducted: in a submitted salary slip.
- Missed: not deducted in its month, until it is moved or postponed.
"""

import math

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import add_months, cint, flt, fmt_money, get_first_day, getdate, today

from ms_hrms.app_notifications import safe
from ms_hrms.request_approvers import sees_all

CHILD = "Employee Advance Repayment"
SCHEDULE = "custom_repayment_schedule"
COMPONENT_FIELD = "custom_advance_repayment_component"
PENDING = ("Scheduled", "Missed")
SENT = ("Due", "Deducted")


# Setup


def setup():
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	fields = [
		{
			"fieldname": "custom_repayment_section",
			"fieldtype": "Section Break",
			"label": "Repayment Plan",
			"depends_on": "eval:doc.docstatus==1",
			"insert_after": "paid_amount",
		},
		{
			"fieldname": "custom_repayment_months",
			"fieldtype": "Int",
			"label": "Number of Months",
			"non_negative": 1,
			"read_only": 0,
			"allow_on_submit": 1,
			"description": "Set the number of months and the first month, then Update: the schedule is made from them.",
			"insert_after": "custom_repayment_section",
		},
		{
			"fieldname": "custom_repayment_start",
			"fieldtype": "Date",
			"label": "First Repayment Month",
			"read_only": 0,
			"allow_on_submit": 1,
			"description": "Any day of the month: the installment is deducted in that month's salary.",
			"insert_after": "custom_repayment_months",
		},
		{
			"fieldname": "custom_repayment_installment",
			"fieldtype": "Currency",
			"label": "Monthly Installment",
			"options": "currency",
			"read_only": 1,
			"allow_on_submit": 1,
			"insert_after": "custom_repayment_start",
		},
		{"fieldname": "custom_repayment_column", "fieldtype": "Column Break", "insert_after": "custom_repayment_installment"},
		{
			"fieldname": "custom_repaid_amount",
			"fieldtype": "Currency",
			"label": "Repaid From Salary",
			"options": "currency",
			"read_only": 1,
			"allow_on_submit": 1,
			"insert_after": "custom_repayment_column",
		},
		{
			"fieldname": "custom_repayment_balance",
			"fieldtype": "Currency",
			"label": "Remaining to Repay",
			"options": "currency",
			"read_only": 1,
			"allow_on_submit": 1,
			"insert_after": "custom_repaid_amount",
		},
		{
			"fieldname": "custom_missed_installments",
			"fieldtype": "Int",
			"label": "Missed Installments",
			"read_only": 1,
			"allow_on_submit": 1,
			"depends_on": "eval:doc.custom_missed_installments",
			"insert_after": "custom_repayment_balance",
		},
		{
			"fieldname": "custom_repayment_schedule_section",
			"fieldtype": "Section Break",
			"depends_on": "eval:doc.docstatus==1",
			"insert_after": "custom_missed_installments",
		},
		{
			"fieldname": SCHEDULE,
			"fieldtype": "Table",
			"label": "Repayment Schedule",
			"options": CHILD,
			"allow_on_submit": 1,
			"insert_after": "custom_repayment_schedule_section",
		},
	]
	settings = [
		{
			"fieldname": COMPONENT_FIELD,
			"fieldtype": "Link",
			"label": "Advance Repayment Component",
			"options": "Salary Component",
			"description": "The deduction that employee advance installments are deducted from salaries as.",
			"insert_after": "create_overtime_slip",
		}
	]
	create_custom_fields({"Employee Advance": fields, "Payroll Settings": settings}, update=True)

	# A single deduction named for advances is the one to use.
	if not frappe.db.get_single_value("Payroll Settings", COMPONENT_FIELD):
		components = [
			name
			for name in frappe.get_all("Salary Component", filters={"type": "Deduction", "disabled": 0}, pluck="name")
			if "سلف" in name or "advance" in name.lower()
		]
		if len(components) == 1:
			frappe.db.set_single_value("Payroll Settings", COMPONENT_FIELD, components[0])


# Helpers


def owed(doc):
	"""What the schedule repays: the paid amount not claimed back, or the amount asked for
	while unpaid."""
	if flt(doc.paid_amount):
		return flt(flt(doc.paid_amount) - flt(doc.claimed_amount), doc.precision("advance_amount"))
	return flt(doc.advance_amount, doc.precision("advance_amount"))


def month_label(value, lang=None):
	from babel.dates import format_date

	lang = lang or frappe.local.lang or "en"
	try:
		return format_date(getdate(value), "MMMM yyyy", locale=lang.replace("-", "_"))
	except Exception:
		return str(getdate(value))


def set_totals(doc):
	rows = doc.get(SCHEDULE) or []
	precision = doc.precision("advance_amount")
	repaid = flt(sum(flt(row.amount) for row in rows if row.status == "Deducted"), precision)
	amounts = [flt(row.amount) for row in rows]
	doc.custom_repaid_amount = repaid
	doc.custom_repayment_balance = flt(owed(doc) - repaid, precision) if rows else 0
	doc.custom_missed_installments = sum(1 for row in rows if row.status == "Missed")
	# The installment most months share (the last one takes what rounding left).
	doc.custom_repayment_installment = max(amounts, key=amounts.count) if amounts else 0
	if not rows:
		doc.custom_repayment_months = 0
		doc.custom_repayment_start = None


def update_totals(names):
	for name in set(names):
		doc = frappe.get_doc("Employee Advance", name)
		set_totals(doc)
		frappe.db.set_value(
			"Employee Advance",
			name,
			{
				"custom_repaid_amount": doc.custom_repaid_amount,
				"custom_repayment_balance": doc.custom_repayment_balance,
				"custom_missed_installments": doc.custom_missed_installments,
				"custom_repayment_installment": doc.custom_repayment_installment,
			},
			update_modified=False,
		)


def get_planned_advance(name):
	doc = frappe.get_doc("Employee Advance", name)
	doc.check_permission("read")
	if not sees_all(frappe.session.user):
		frappe.throw(_("Only HR may set the repayment plan of an advance."), frappe.PermissionError)
	if doc.docstatus != 1:
		frappe.throw(_("The repayment plan is set after the advance is approved."))
	return doc


def check_month(value):
	month = get_first_day(value)
	if month < get_first_day(today()):
		frappe.throw(_("Choose this month or a later one."))
	return month


def save_plan(doc, comment):
	doc.flags.ms_hrms_repayment = True
	doc.save(ignore_permissions=True)
	doc.add_comment("Info", comment)
	send_due(doc.name)


# Planning (HR)


@frappe.whitelist(methods=["POST"])
def make_schedule(name, months, start):
	"""One installment a month from the start month, equal in whole amounts; the last takes
	what is left."""
	doc = get_planned_advance(name)
	build_schedule(doc, months, start)
	save_plan(doc, plan_comment(doc))
	tell_employee(doc, "plan")


def build_schedule(doc, months, start):
	months = cint(months)
	if months < 1:
		frappe.throw(_("Set the number of months."))
	if not start:
		frappe.throw(_("Set the first repayment month."))
	if any(row.status in SENT for row in doc.get(SCHEDULE)):
		frappe.throw(_("Installments of this advance were already sent to payroll. Move or postpone the remaining ones instead."))
	if not frappe.db.get_single_value("Payroll Settings", COMPONENT_FIELD):
		frappe.throw(_("Set the Advance Repayment Component in Payroll Settings first."))

	start = check_month(start)
	precision = doc.precision("advance_amount")
	total = owed(doc)
	installment = math.floor(total / months) if total >= months else flt(total / months, precision)
	doc.set(SCHEDULE, [])
	for index in range(months):
		amount = installment if index < months - 1 else flt(total - installment * (months - 1), precision)
		doc.append(SCHEDULE, {"payroll_date": add_months(start, index), "amount": amount, "status": "Scheduled"})
	doc.custom_repayment_months = months
	doc.custom_repayment_start = start


def plan_comment(doc):
	return _("Repayment plan set: {0} months from {1}.").format(doc.custom_repayment_months, month_label(doc.custom_repayment_start))


@frappe.whitelist(methods=["POST"])
def move_remaining(name, start):
	"""The installments not deducted yet (the missed ones first) one a month from the start
	month."""
	doc = get_planned_advance(name)
	start = check_month(start)
	pending = sorted((row for row in doc.get(SCHEDULE) if row.status in PENDING), key=lambda row: getdate(row.payroll_date))
	if not pending:
		frappe.throw(_("No installments are left to move."))

	for index, row in enumerate(pending):
		reschedule(row, add_months(start, index))
	save_plan(doc, _("Remaining installments moved to start from {0}.").format(month_label(start)))
	tell_employee(doc, "moved")


@frappe.whitelist(methods=["POST"])
def postpone(name, row):
	"""One installment to the month after the last; one waiting for its salary slip has its
	Additional Salary cancelled."""
	doc = get_planned_advance(name)
	installment = next((r for r in doc.get(SCHEDULE) if r.name == row), None)
	if not installment or installment.status == "Deducted":
		frappe.throw(_("Choose an installment that was not deducted."))

	if installment.status == "Due" and installment.additional_salary:
		additional_salary = frappe.get_doc("Additional Salary", installment.additional_salary)
		if additional_salary.docstatus == 1:
			frappe.flags.ms_hrms_postponing = additional_salary.name
			try:
				additional_salary.flags.ignore_permissions = True
				additional_salary.cancel()
			finally:
				frappe.flags.ms_hrms_postponing = None

	last = max(getdate(r.payroll_date) for r in doc.get(SCHEDULE))
	moved_from = month_label(installment.payroll_date)
	reschedule(installment, add_months(get_first_day(last), 1), _("Postponed from {0}").format(moved_from))
	save_plan(doc, _("Installment of {0} postponed to {1}.").format(moved_from, month_label(installment.payroll_date)))
	tell_employee(doc, "moved")


def reschedule(row, month, note=None):
	month = getdate(month)
	# A missed installment's note already says why it moved.
	if not note and row.status == "Scheduled" and getdate(row.payroll_date) != month:
		note = _("Moved from {0}").format(month_label(row.payroll_date))
	if note:
		row.note = "\n".join(filter(None, [row.note, note]))
	row.payroll_date = month
	row.status = "Scheduled"
	row.additional_salary = None
	row.salary_slip = None


# Employee Advance events


def onload(doc, method=None):
	from ms_hrms.request_approvers import can_approve

	doc.set_onload("ms_hrms_can_plan_repayment", sees_all(frappe.session.user))
	doc.set_onload("ms_hrms_can_approve", can_approve(doc))


def validate_schedule(doc, method=None):
	"""Edits of the schedule after approval (before_update_after_submit): by HR only; the
	installments sent to payroll stay as they are, and all of them add up to the advance."""
	before = doc.get_doc_before_save()

	# Months or first month changed on the form: the schedule is made again from them.
	if (
		not doc.flags.ms_hrms_repayment
		and before
		and (
			cint(doc.custom_repayment_months) != cint(before.custom_repayment_months)
			or str(doc.custom_repayment_start or "") != str(before.custom_repayment_start or "")
		)
	):
		if not sees_all(frappe.session.user):
			frappe.throw(_("Only HR may change the repayment schedule."), frappe.PermissionError)
		build_schedule(doc, doc.custom_repayment_months, doc.custom_repayment_start)
		doc.flags.ms_hrms_repayment = doc.flags.ms_hrms_new_plan = True

	old = {row.name: row for row in (before.get(SCHEDULE) if before else [])}
	rows = doc.get(SCHEDULE)

	def key(row):
		return (str(getdate(row.payroll_date)) if row.payroll_date else None, flt(row.amount))

	changed = [row for row in rows if row.name not in old or key(row) != key(old[row.name])]
	removed = [row for name, row in old.items() if name not in {r.name for r in rows}]
	if not changed and not removed:
		set_totals(doc)
		return

	by_hand = not doc.flags.ms_hrms_repayment
	if by_hand:
		if not sees_all(frappe.session.user):
			frappe.throw(_("Only HR may change the repayment schedule."), frappe.PermissionError)
		for row in removed + changed:
			if row.name in old and old[row.name].status in SENT:
				frappe.throw(
					_("The installment of {0} was already sent to payroll and cannot be changed.").format(
						month_label(old[row.name].payroll_date)
					)
				)
	for row in changed:
		if not row.payroll_date:
			frappe.throw(_("Row {0}: set the month of the installment.").format(row.idx))
		row.payroll_date = get_first_day(row.payroll_date)
		was = old.get(row.name)
		if not was:
			row.status = "Scheduled"
			row.additional_salary = row.salary_slip = None
		if by_hand and (not was or getdate(row.payroll_date) != getdate(was.payroll_date)):
			check_month(row.payroll_date)
			if was:
				note = _("Moved from {0}").format(month_label(was.payroll_date)) if was.status == "Scheduled" else None
				row.status = was.status
				reschedule(row, row.payroll_date, note)
		if flt(row.amount) <= 0:
			frappe.throw(_("Row {0}: the installment should be more than zero.").format(row.idx))

	if rows:
		precision = doc.precision("advance_amount")
		total = flt(sum(flt(row.amount) for row in rows), precision)
		if abs(total - owed(doc)) >= 10 ** -precision:
			frappe.throw(
				_("The installments add up to {0}, but the advance to repay is {1}.").format(
					fmt_money(total, currency=doc.currency), fmt_money(owed(doc), currency=doc.currency)
				),
				title=_("Repayment Schedule"),
			)
		rows.sort(key=lambda row: getdate(row.payroll_date))
		for index, row in enumerate(rows, 1):
			row.idx = index
	set_totals(doc)


def on_schedule_update(doc, method=None):
	"""Saved on the form: a new plan is told to the employee, and an installment for this
	month is sent now, not tomorrow."""
	if doc.flags.ms_hrms_new_plan:
		doc.add_comment("Info", plan_comment(doc))
		tell_employee(doc, "plan")
	if (not doc.flags.ms_hrms_repayment or doc.flags.ms_hrms_new_plan) and any(
		row.status == "Scheduled" for row in doc.get(SCHEDULE)
	):
		send_due(doc.name)
	doc.flags.ms_hrms_repayment = doc.flags.ms_hrms_new_plan = False


# Sending installments to payroll (daily, and when a plan changes)


def send_due(advance=None):
	component = frappe.db.get_single_value("Payroll Settings", COMPONENT_FIELD)
	if not component:
		return
	Row = DocType(CHILD)
	Advance = DocType("Employee Advance")
	query = (
		frappe.qb.from_(Row)
		.join(Advance)
		.on(Row.parent == Advance.name)
		.select(Row.name, Row.parent, Row.payroll_date, Row.amount)
		.where(Row.parenttype == "Employee Advance")
		.where(Row.parentfield == SCHEDULE)
		.where(Row.status == "Scheduled")
		.where(Row.payroll_date <= getdate(today()))
		.where(Advance.docstatus == 1)
		.where(Advance.paid_amount > 0)
		.orderby(Row.payroll_date)
	)
	if advance:
		query = query.where(Advance.name == advance)

	touched = []
	for row in query.run(as_dict=True):
		doc = frappe.get_doc("Employee Advance", row.parent)
		touched.append(doc.name)
		# Never more than was paid: an installment the payment does not cover waits.
		if flt(row.amount) > unsent_paid(doc):
			continue
		if salary_slip_submitted(doc.employee, row.payroll_date):
			mark_missed(row.name, _("The salary slip of {0} was submitted before the installment was sent.").format(month_label(row.payroll_date)))
			continue

		frappe.db.savepoint("ms_hrms_advance_installment")
		try:
			additional_salary = frappe.new_doc("Additional Salary")
			additional_salary.update(
				{
					"employee": doc.employee,
					"company": doc.company,
					"currency": doc.currency,
					"salary_component": component,
					"amount": row.amount,
					"payroll_date": row.payroll_date,
					"overwrite_salary_structure_amount": 0,
					"ref_doctype": "Employee Advance",
					"ref_docname": doc.name,
				}
			)
			additional_salary.flags.ignore_permissions = True
			additional_salary.insert()
			additional_salary.submit()
		except Exception as error:
			frappe.db.rollback(save_point="ms_hrms_advance_installment")
			frappe.clear_messages()
			frappe.log_error(title=f"Advance installment not sent to payroll: {doc.name}", reference_doctype="Employee Advance", reference_name=doc.name)
			frappe.db.set_value(
				CHILD, row.name, "note", _("Not sent to payroll: {0}").format(frappe.utils.strip_html(str(error))), update_modified=False
			)
			continue
		frappe.db.set_value(CHILD, row.name, {"status": "Due", "additional_salary": additional_salary.name}, update_modified=False)
	update_totals(touched)


def unsent_paid(doc):
	"""What was paid of the advance (and not claimed) that no installment was sent for."""
	precision = doc.precision("advance_amount")
	sent = sum(flt(row.amount) for row in doc.get(SCHEDULE) if row.status in SENT)
	return flt(flt(doc.paid_amount) - flt(doc.claimed_amount) - sent, precision)


def hold_unpaid(name):
	"""After a payment of the advance is cancelled: the installments sent beyond what is
	still paid are taken back from payroll (the latest first) and wait for payment again.
	An installment already in a submitted salary slip stays."""
	doc = frappe.get_doc("Employee Advance", name)
	if doc.docstatus != 1:
		return
	over = -unsent_paid(doc)
	due = sorted((row for row in doc.get(SCHEDULE) if row.status == "Due"), key=lambda row: getdate(row.payroll_date), reverse=True)
	for row in due:
		if over <= 0:
			break
		if row.additional_salary and frappe.db.get_value("Additional Salary", row.additional_salary, "docstatus") == 1:
			additional_salary = frappe.get_doc("Additional Salary", row.additional_salary)
			frappe.flags.ms_hrms_postponing = additional_salary.name
			try:
				additional_salary.flags.ignore_permissions = True
				additional_salary.cancel()
			except Exception:
				frappe.log_error(title=f"Advance installment not taken back from payroll: {doc.name}", reference_doctype="Employee Advance", reference_name=doc.name)
				continue
			finally:
				frappe.flags.ms_hrms_postponing = None
		old = frappe.db.get_value(CHILD, row.name, "note")
		frappe.db.set_value(
			CHILD,
			row.name,
			{
				"status": "Scheduled",
				"additional_salary": None,
				"note": "\n".join(filter(None, [old, _("Taken back from payroll: the advance payment was cancelled.")])),
			},
			update_modified=False,
		)
		over -= flt(row.amount)
	update_totals([doc.name])


def advances_paid_by(doc):
	if doc.doctype == "Payment Entry":
		rows = [(row.reference_doctype, row.reference_name) for row in doc.get("references") or []]
	else:
		rows = [(row.reference_type, row.reference_name) for row in doc.get("accounts") or []]
	return {name for doctype, name in rows if doctype == "Employee Advance" and name}


def on_payment_submit(doc, method=None):
	"""An advance paid: its installments of this month and before go to payroll now."""
	for name in advances_paid_by(doc):
		send_due(name)


def on_payment_cancel(doc, method=None):
	for name in advances_paid_by(doc):
		hold_unpaid(name)


def salary_slip_submitted(employee, day):
	return frappe.db.exists(
		"Salary Slip", {"employee": employee, "docstatus": 1, "start_date": ["<=", day], "end_date": [">=", day]}
	)


def mark_missed(row, note):
	old = frappe.db.get_value(CHILD, row, "note")
	frappe.db.set_value(CHILD, row, {"status": "Missed", "note": "\n".join(filter(None, [old, note]))}, update_modified=False)


# Additional Salary and Salary Slip events


def ignore_schedule_links(doc, method=None):
	"""Before cancel: a schedule's link to the document does not hold it."""
	doc.ignore_linked_doctypes = list(doc.get("ignore_linked_doctypes") or []) + [CHILD]


def rows_of(fieldname, value, status=None):
	filters = {"parenttype": "Employee Advance", "parentfield": SCHEDULE, fieldname: value}
	if status:
		filters["status"] = status
	return frappe.get_all(CHILD, filters=filters, fields=["name", "parent", "payroll_date"])


def on_additional_salary_cancel(doc, method=None):
	if doc.ref_doctype != "Employee Advance" or frappe.flags.ms_hrms_postponing == doc.name:
		return
	rows = rows_of("additional_salary", doc.name, "Due")
	for row in rows:
		mark_missed(row.name, _("Not deducted in {0}: {1} was cancelled.").format(month_label(row.payroll_date), doc.name))
	update_totals(row.parent for row in rows)
	for name in {row.parent for row in rows}:
		tell_hr_of_missed(name)


def on_additional_salary_trash(doc, method=None):
	for row in rows_of("additional_salary", doc.name):
		frappe.db.set_value(CHILD, row.name, "additional_salary", None, update_modified=False)


def on_salary_slip_submit(doc, method=None):
	"""The month's installments in the slip are deducted; those sent but left out of it
	are missed."""
	in_slip = {row.additional_salary for row in doc.get("deductions") or [] if row.additional_salary}
	Row = DocType(CHILD)
	Advance = DocType("Employee Advance")
	due = (
		frappe.qb.from_(Row)
		.join(Advance)
		.on(Row.parent == Advance.name)
		.select(Row.name, Row.parent, Row.payroll_date, Row.amount, Row.additional_salary)
		.where(Row.parenttype == "Employee Advance")
		.where(Row.status == "Due")
		.where(Advance.employee == doc.employee)
		.where(Row.payroll_date[getdate(doc.start_date) : getdate(doc.end_date)])
	).run(as_dict=True)
	if not due:
		return

	deducted = []
	for row in due:
		if row.additional_salary in in_slip:
			frappe.db.set_value(CHILD, row.name, {"status": "Deducted", "salary_slip": doc.name}, update_modified=False)
			deducted.append(row)
		else:
			mark_missed(row.name, _("Not deducted in {0}: left out of {1}.").format(month_label(row.payroll_date), doc.name))
	update_totals(row.parent for row in due)
	for row in deducted:
		tell_employee(frappe.get_doc("Employee Advance", row.parent), "deducted", row)
	for name in {row.parent for row in due if row not in deducted}:
		tell_hr_of_missed(name)


def on_salary_slip_cancel(doc, method=None):
	"""Its installments wait for the next slip of the month again."""
	Row = DocType(CHILD)
	Advance = DocType("Employee Advance")
	AdditionalSalary = DocType("Additional Salary")
	rows = (
		frappe.qb.from_(Row)
		.join(Advance)
		.on(Row.parent == Advance.name)
		.join(AdditionalSalary)
		.on(Row.additional_salary == AdditionalSalary.name)
		.select(Row.name, Row.parent, Row.status)
		.where(Row.parenttype == "Employee Advance")
		.where(Advance.employee == doc.employee)
		.where(AdditionalSalary.docstatus == 1)
		.where(
			(Row.salary_slip == doc.name)
			| ((Row.status == "Missed") & Row.payroll_date[getdate(doc.start_date) : getdate(doc.end_date)])
		)
	).run(as_dict=True)
	for row in rows:
		frappe.db.set_value(CHILD, row.name, {"status": "Due", "salary_slip": None}, update_modified=False)
	update_totals(row.parent for row in rows)


# Notifications


@safe
def tell_employee(doc, event, row=None):
	from ms_hrms.app_notifications import is_on, lang_of, notify, t, user_of

	user = user_of(doc.employee)
	if not user or not is_on("requests"):
		return
	lang = lang_of(user)
	money = lambda value: fmt_money(value, currency=doc.currency)  # noqa: E731
	if event == "plan":
		message = t(
			"Your advance will be repaid from your salary: {0} a month for {1} months, from {2}",
			lang,
			money(doc.custom_repayment_installment),
			doc.custom_repayment_months,
			month_label(doc.custom_repayment_start, lang),
		)
	elif event == "deducted":
		doc.reload()
		message = t(
			"{0} of your advance was deducted from your salary for {1}. Remaining: {2}",
			lang,
			money(row.amount),
			month_label(row.payroll_date, lang),
			money(doc.custom_repayment_balance),
		)
	else:
		upcoming = [r for r in doc.get(SCHEDULE) if r.status == "Scheduled"]
		if not upcoming:
			return
		message = t("Your advance installments were rescheduled. The next one is in {0}", lang, month_label(upcoming[0].payroll_date, lang))
	notify(user, message, "Employee Advance", doc.name)


@safe
def tell_hr_of_missed(name):
	"""A missed installment, on the advance's timeline for HR."""
	frappe.get_doc("Employee Advance", name).add_comment(
		"Info", _("An installment was not deducted. Move the remaining installments or postpone it.")
	)
