"""Who approves employee requests, and who may see them.

As with Frappe HR's Leave, Expense and Shift approvers, the approver set on the employee
(Employee > Approvers) comes first; when none is set, the approvers listed on the
employee's department approve.

An employee sees their own requests, the ones they created, and the requests of the
employees they manage (Reports To) or approve. The System Manager (and Administrator)
sees all of them, and so do the roles listed in HR Settings > Roles That See All
Requests (HR Manager and HR User when it is set up). The rules apply everywhere: lists, forms, reports and the employee app. They cover
ms_hrms' Permission and Overtime Requests and Frappe HR's own requests, whose Employee
role otherwise reads every employee's.
"""

import frappe

# For each request: the approver field on Employee, the approvers table on Department,
# and the approver field on the request itself. Requests with none of them (Attendance
# Request, Employee Advance) are seen by the employee's manager (Reports To).
REQUESTS = {
	"Permission Request": frappe._dict(
		employee_field="custom_permission_approver", department_field="custom_permission_approver"
	),
	"Overtime Request": frappe._dict(
		employee_field="custom_overtime_approver", department_field="custom_overtime_approver"
	),
	"Leave Application": frappe._dict(
		employee_field="leave_approver", department_field="leave_approvers", request_field="leave_approver"
	),
	"Expense Claim": frappe._dict(
		employee_field="expense_approver", department_field="expense_approvers", request_field="expense_approver"
	),
	"Shift Request": frappe._dict(
		employee_field="shift_request_approver", department_field="shift_request_approver", request_field="approver"
	),
	"Attendance Request": frappe._dict(),
	"Employee Advance": frappe._dict(),
}
SEES_ALL = "System Manager"
# HR Settings' list of the other roles that see every request (setup()).
SEES_ALL_FIELD = "custom_roles_that_see_all_requests"
SEES_ALL_BY_DEFAULT = ("HR Manager", "HR User")
# Requests decided through decide(): the Employee role may not write them, so their
# approvers approve and reject through it.
DECIDED_HERE = ("Permission Request", "Overtime Request")
DECISIONS = ("Approved", "Rejected")


def get_approvers(doctype, employee):
	"""The users who approve this employee's requests of this type."""
	request = REQUESTS[doctype]
	if not request.employee_field:
		return []
	employee_row = frappe.db.get_value(
		"Employee", employee, ["department", request.employee_field], as_dict=True
	)
	if not employee_row:
		return []
	if employee_row.get(request.employee_field):
		return [employee_row.get(request.employee_field)]
	if not employee_row.department:
		return []
	return frappe.get_all(
		"Department Approver",
		filters={
			"parenttype": "Department",
			"parent": employee_row.department,
			"parentfield": request.department_field,
		},
		pluck="approver",
		order_by="idx",
	)


def is_approver(doctype, employee, user=None):
	user = user or frappe.session.user
	return bool(employee) and user in get_approvers(doctype, employee)


def is_manager(employee, user=None):
	"""Whether the user is the employee's manager (Reports To)."""
	user = user or frappe.session.user
	manager = frappe.db.get_value("Employee", employee, "reports_to")
	return bool(manager) and frappe.db.get_value("Employee", manager, "user_id") == user


def sees_all(user):
	if user == "Administrator":
		return True
	roles = set(frappe.get_roles(user))
	return SEES_ALL in roles or bool(roles & set(get_roles_that_see_all()))


def get_roles_that_see_all():
	settings = frappe.get_cached_doc("HR Settings")
	return [row.role for row in settings.get(SEES_ALL_FIELD) or []]


def setup():
	"""HR Settings > Roles That See All Requests, listing HR Manager and HR User when it
	is first added."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	if frappe.db.exists("Custom Field", {"dt": "HR Settings", "fieldname": SEES_ALL_FIELD}):
		return
	create_custom_fields(
		{
			"HR Settings": [
				{
					"fieldname": "custom_employee_requests_section",
					"fieldtype": "Section Break",
					"label": "Employee Requests",
					"insert_after": "retirement_age",
				},
				{
					"fieldname": SEES_ALL_FIELD,
					"fieldtype": "Table MultiSelect",
					"label": "Roles That See All Requests",
					"options": "Has Role",
					"insert_after": "custom_employee_requests_section",
					"description": "Besides the System Manager, these roles see every employee's "
					"requests (leaves, permissions, overtime, attendance, shifts, expenses and "
					"advances). Everyone else sees their own, and those of the employees they "
					"manage or approve.",
				},
			]
		}
	)
	settings = frappe.get_single("HR Settings")
	for role in SEES_ALL_BY_DEFAULT:
		if frappe.db.exists("Role", role):
			settings.append(SEES_ALL_FIELD, {"role": role})
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)


# The app's For Approval lists: for each request, the field that holds the decision, its
# value while the request waits, and the field that names its approver (Frappe HR's
# hrms.api.get_filters). Permission and Overtime Requests go by their employees'
# approvers instead; Attendance Requests by who may see them.
WAITING = {
	"Leave Application": frappe._dict(status_field="status", waiting="Open", approver_field="leave_approver"),
	"Expense Claim": frappe._dict(status_field="approval_status", waiting="Draft", approver_field="expense_approver"),
	"Shift Request": frappe._dict(status_field="status", waiting="Draft", approver_field="approver"),
	"Attendance Request": frappe._dict(),
	"Permission Request": frappe._dict(status_field="status", waiting="Pending Approval"),
	"Overtime Request": frappe._dict(status_field="status", waiting="Pending Approval"),
}


@frappe.whitelist()
def get_requests_to_approve(doctype, fields=None):
	"""The requests of this type awaiting the user's approval, theirs included when they
	are its approver (a department's approver approves their own requests unless their
	Employee names another approver). Requests under a workflow are those in a state the
	user's roles move on, as in Frappe HR."""
	from hrms.api import get_allowed_states_for_workflow, get_workflow, get_workflow_state_field

	from ms_hrms.request_history import MY_REQUESTS

	if doctype not in WAITING:
		frappe.throw(frappe._("This request type is not listed here."))
	user = frappe.session.user
	me = frappe.db.get_value("Employee", {"user_id": user}, "name")
	waiting = WAITING[doctype]
	filters = {"docstatus": 0}
	others_only = False

	workflow = get_workflow(doctype)
	if workflow:
		filters[workflow.workflow_state_field] = ("in", get_allowed_states_for_workflow(workflow, user))
		others_only = True
	else:
		if waiting.status_field:
			filters[waiting.status_field] = waiting.waiting
		if doctype in DECIDED_HERE:
			employees = _employees_approved_by(doctype, user)
			if employees is not None:
				if not employees:
					return []
				filters["employee"] = ("in", sorted(employees))
			else:
				others_only = True
		elif waiting.approver_field:
			filters[waiting.approver_field] = user
			if doctype == "Leave Application" and frappe.db.get_single_value("HR Settings", "prevent_self_leave_approval"):
				others_only = True
		else:
			# No approver on the request: of those the user may see, the others'.
			others_only = True
	if others_only and me:
		filters["employee"] = ("!=", me) if "employee" not in filters else filters["employee"]

	listed = MY_REQUESTS.get(doctype)
	fields = frappe.parse_json(fields) if fields else list(listed.fields if listed else ["name"])
	state_field = get_workflow_state_field(doctype)
	if state_field and state_field not in fields:
		fields.append(state_field)
	requests = frappe.get_list(
		doctype,
		fields=fields,
		filters=filters,
		order_by=listed.order_by if listed else "creation desc",
		group_by=listed.get("group_by") if listed else None,
		limit=0,
	)
	if state_field:
		for row in requests:
			row["workflow_state_field"] = state_field
	return requests


def _employees_approved_by(doctype, user):
	"""The employees whose requests of this type the user approves (None: every
	employee, for the Administrator)."""
	if user == "Administrator":
		return None
	request = REQUESTS[doctype]
	employees = set(frappe.get_all("Employee", filters={request.employee_field: user}, pluck="name"))
	departments = frappe.get_all(
		"Department Approver",
		filters={"parenttype": "Department", "parentfield": request.department_field, "approver": user},
		pluck="parent",
	)
	if departments:
		employees |= set(
			frappe.get_all(
				"Employee",
				filters={"department": ("in", departments), request.employee_field: ("is", "not set")},
				pluck="name",
			)
		)
	return employees


def get_condition(doctype, user=None):
	"""The requests a user may see: their own, the ones they created, those whose
	employee reports to them, and those they approve, either named on the request or by
	the employee's own approver field or, when it is empty, by the department's
	approvers table."""
	user = user or frappe.session.user
	if sees_all(user):
		return ""

	request = REQUESTS[doctype]
	table = f"`tab{doctype}`"
	user_value = frappe.db.escape(user)
	employees = [
		f"select name from `tabEmployee` where user_id = {user_value}",
		f"""select employee.name from `tabEmployee` employee
		join `tabEmployee` manager on manager.name = employee.reports_to
		where manager.user_id = {user_value}""",
	]
	if request.employee_field:
		field = request.employee_field
		employees += [
			f"select name from `tabEmployee` where `{field}` = {user_value}",
			f"""select employee.name from `tabEmployee` employee
			join `tabDepartment Approver` approver
				on approver.parent = employee.department
				and approver.parenttype = 'Department'
				and approver.parentfield = '{request.department_field}'
			where ifnull(employee.`{field}`, '') = '' and approver.approver = {user_value}""",
		]
	conditions = [
		f"{table}.employee in ({' union '.join(employees)})",
		f"{table}.owner = {user_value}",
	]
	if request.request_field:
		conditions.append(f"{table}.`{request.request_field}` = {user_value}")
	return f"({' or '.join(conditions)})"


def permission_request_condition(user=None):
	return get_condition("Permission Request", user)


def overtime_request_condition(user=None):
	return get_condition("Overtime Request", user)


def leave_application_condition(user=None):
	return get_condition("Leave Application", user)


def expense_claim_condition(user=None):
	return get_condition("Expense Claim", user)


def shift_request_condition(user=None):
	return get_condition("Shift Request", user)


def attendance_request_condition(user=None):
	return get_condition("Attendance Request", user)


def employee_advance_condition(user=None):
	return get_condition("Employee Advance", user)


@frappe.whitelist(methods=["POST"])
def decide(doctype, name, status):
	"""Approve or reject a Permission or Overtime Request awaiting approval, as its
	approver. The request's own validation still checks the change."""
	if doctype not in DECIDED_HERE or status not in DECISIONS:
		frappe.throw(frappe._("This request cannot be decided here."))

	doc = frappe.get_doc(doctype, name)
	if frappe.session.user != "Administrator" and not is_approver(doctype, doc.employee):
		frappe.throw(frappe._("You are not the approver of this request."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.status != "Pending Approval":
		frappe.throw(frappe._("This request is not awaiting approval."))

	doc.status = status
	doc.flags.ignore_permissions = True
	doc.save()
	return doc.status


def has_permission(doc, ptype=None, user=None, debug=False):
	"""Controller check behind get_condition, for single requests. It can only take away
	what the roles give; True leaves the roles to decide."""
	user = user or frappe.session.user
	if sees_all(user) or doc.is_new() or not doc.get("employee") or doc.owner == user:
		return True
	request = REQUESTS[doc.doctype]
	if request.request_field and doc.get(request.request_field) == user:
		return True
	own = frappe.db.get_value("Employee", doc.employee, "user_id") == user
	return own or is_manager(doc.employee, user) or is_approver(doc.doctype, doc.employee, user)
