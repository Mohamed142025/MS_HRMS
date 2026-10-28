"""The employee's request history in the employee app (ms_hrms.pwa).

My Requests lists every request of the signed-in employee, the cancelled ones included,
which Frappe HR's own lists leave out. A request's sheet shows how it was decided: who
approved, rejected or cancelled it, when, and the approver's remarks.

Decisions are read from the request's version history, so the requests whose changes
Frappe HR does not track (Leave Application, Expense Claim) are tracked from setup().
Requests decided before that fall back to what the request itself records: the
approval audit fields of Overtime and Permission Requests, or the approver named on it.
"""

import json

import frappe
from frappe.utils import get_fullname

from hrms.api import get_current_employee, get_workflow_state_field

# What My Requests shows of the requests Frappe HR lists (as hrms.api returns them).
MY_REQUESTS = {
	"Leave Application": frappe._dict(
		fields=[
			"name",
			"posting_date",
			"employee",
			"employee_name",
			"leave_type",
			"status",
			"from_date",
			"to_date",
			"half_day",
			"half_day_date",
			"description",
			"total_leave_days",
			"leave_balance",
			"leave_approver",
			"docstatus",
			"creation",
		],
		order_by="posting_date desc",
	),
	"Expense Claim": frappe._dict(
		fields=[
			"`tabExpense Claim`.name",
			"`tabExpense Claim`.posting_date",
			"`tabExpense Claim`.employee",
			"`tabExpense Claim`.employee_name",
			"`tabExpense Claim`.currency",
			"`tabExpense Claim`.approval_status",
			"`tabExpense Claim`.status",
			"`tabExpense Claim`.expense_approver",
			"`tabExpense Claim`.total_claimed_amount",
			"`tabExpense Claim`.company",
			"`tabExpense Claim`.docstatus",
			"`tabExpense Claim`.creation",
			"`tabExpense Claim Detail`.expense_type",
			{"COUNT": "`tabExpense Claim Detail`.expense_type", "as": "total_expenses"},
		],
		order_by="`tabExpense Claim`.posting_date desc",
		group_by="`tabExpense Claim`.name",
	),
	"Shift Request": frappe._dict(
		fields=[
			"name",
			"employee",
			"employee_name",
			"shift_type",
			"from_date",
			"to_date",
			"status",
			"approver",
			"docstatus",
			"creation",
		],
		order_by="creation desc",
	),
	"Attendance Request": frappe._dict(
		fields=[
			"name",
			"reason",
			"employee",
			"employee_name",
			"from_date",
			"to_date",
			"include_holidays",
			"shift",
			"docstatus",
			"creation",
		],
		order_by="creation desc",
	),
}

# For each request: the field that holds the approver's decision (none when approving
# is submitting), and the field that names its approver.
REQUESTS = {
	"Leave Application": frappe._dict(decision_field="status", approver_field="leave_approver"),
	"Expense Claim": frappe._dict(decision_field="approval_status", approver_field="expense_approver"),
	"Shift Request": frappe._dict(decision_field="status", approver_field="approver"),
	"Permission Request": frappe._dict(decision_field="status"),
	"Overtime Request": frappe._dict(decision_field="status", approver_field="approved_by"),
	"Attendance Request": frappe._dict(),
	"Employee Advance": frappe._dict(),
}
DECISIONS = ("Approved", "Rejected")
# Requests whose changes Frappe HR does not track; setup() tracks them.
TRACKED_HERE = ("Leave Application", "Expense Claim")


def setup():
	"""Track the changes of the requests whose decisions would otherwise go unrecorded."""
	from frappe.custom.doctype.property_setter.property_setter import make_property_setter

	for doctype in TRACKED_HERE:
		if not frappe.get_meta(doctype).track_changes:
			make_property_setter(doctype, None, "track_changes", 1, "Check", for_doctype=True)


@frappe.whitelist()
def get_my_requests(doctype):
	"""Every request of this type of the signed-in employee, the cancelled ones included."""
	if doctype not in MY_REQUESTS:
		frappe.throw(frappe._("This request type is not listed here."))
	employee = get_current_employee()
	if not employee:
		return []

	request = MY_REQUESTS[doctype]
	fields = list(request.fields)
	workflow_state_field = get_workflow_state_field(doctype)
	if workflow_state_field:
		fields.append(workflow_state_field)

	requests = frappe.get_list(
		doctype,
		fields=fields,
		filters={"employee": employee},
		order_by=request.order_by,
		group_by=request.get("group_by"),
		limit=0,
	)
	if workflow_state_field:
		for row in requests:
			row["workflow_state_field"] = workflow_state_field
	return requests


@frappe.whitelist()
def get_request_decision(doctype, name):
	"""How a request was decided, for its sheet in the app:

	{"status": "Approved" | "Rejected" | "Submitted", "by": full name, "on": datetime,
	 "remarks": text, "cancelled_by": full name, "cancelled_on": datetime}

	Any part may be missing; None while the request awaits its decision."""
	if doctype not in REQUESTS:
		frappe.throw(frappe._("This request type is not listed here."))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	request = REQUESTS[doctype]
	decision = frappe._dict()
	for version in frappe.get_all(
		"Version",
		filters={"ref_doctype": doctype, "docname": name},
		fields=["owner", "creation", "data"],
		order_by="creation asc",
	):
		for fieldname, _old, new in json.loads(version.data or "{}").get("changed") or []:
			if fieldname == request.decision_field and new in DECISIONS:
				decision.update(status=new, by=version.owner, on=version.creation)
			elif fieldname == "docstatus" and new == 1 and not request.decision_field:
				decision.update(status="Submitted", by=version.owner, on=version.creation)
			elif fieldname == "docstatus" and new == 2:
				decision.update(cancelled_by=version.owner, cancelled_on=version.creation)

	# Decided before its changes were tracked: what the request itself records.
	if not decision.status:
		if request.decision_field and doc.get(request.decision_field) in DECISIONS:
			decision.status = doc.get(request.decision_field)
		elif not request.decision_field and doc.docstatus:
			decision.status = "Submitted"
		if decision.status:
			decision.by = doc.get("approved_by") or doc.get(request.approver_field or "")
			decision.on = doc.get("approval_date")
	if doc.docstatus == 2 and not decision.cancelled_by:
		decision.update(cancelled_by=doc.modified_by, cancelled_on=doc.modified)

	if not decision:
		return None
	decision.remarks = doc.get("approval_remarks")
	for user_field in ("by", "cancelled_by"):
		if decision.get(user_field):
			decision[user_field] = get_fullname(decision[user_field])
	return decision
