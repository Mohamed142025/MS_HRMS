"""Who approves Permission and Overtime Requests, and who may see them.

As with Frappe HR's Leave, Expense and Shift approvers, the approver set on the employee
(Employee > Approvers) comes first; when none is set, the approvers listed on the
employee's department approve.

An employee sees their own requests and the requests they approve. Only the System
Manager (and Administrator) sees all of them; HR Manager and HR User are limited like
everyone else. The rules apply everywhere: lists, forms, reports and the employee app.
"""

import frappe

# For each request: the approver field on Employee, and the approvers table on Department.
REQUESTS = {
	"Permission Request": frappe._dict(
		employee_field="custom_permission_approver", department_field="custom_permission_approver"
	),
	"Overtime Request": frappe._dict(
		employee_field="custom_overtime_approver", department_field="custom_overtime_approver"
	),
}
SEES_ALL = "System Manager"


def get_approvers(doctype, employee):
	"""The users who approve this employee's requests of this type."""
	request = REQUESTS[doctype]
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


def sees_all(user):
	return user == "Administrator" or SEES_ALL in frappe.get_roles(user)


def get_condition(doctype, user=None):
	"""The requests a user may see: their own, and those whose employee they approve,
	either by the employee's own approver field or, when it is empty, by the department's
	approvers table."""
	user = user or frappe.session.user
	if sees_all(user):
		return ""

	request = REQUESTS[doctype]
	table = f"`tab{doctype}`"
	user_value = frappe.db.escape(user)
	field = request.employee_field
	return f"""({table}.employee in (
		select name from `tabEmployee` where user_id = {user_value}
		union
		select name from `tabEmployee` where `{field}` = {user_value}
		union
		select employee.name from `tabEmployee` employee
		join `tabDepartment Approver` approver
			on approver.parent = employee.department
			and approver.parenttype = 'Department'
			and approver.parentfield = '{request.department_field}'
		where ifnull(employee.`{field}`, '') = '' and approver.approver = {user_value}
	))"""


def permission_request_condition(user=None):
	return get_condition("Permission Request", user)


def overtime_request_condition(user=None):
	return get_condition("Overtime Request", user)


def has_permission(doc, ptype=None, user=None, debug=False):
	"""Controller check behind get_condition, for single requests. It can only take away
	what the roles give; True leaves the roles to decide."""
	user = user or frappe.session.user
	if sees_all(user) or doc.is_new() or not doc.get("employee"):
		return True
	own = frappe.db.get_value("Employee", doc.employee, "user_id") == user
	return own or is_approver(doc.doctype, doc.employee, user)
