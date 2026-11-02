"""The employee's own evaluations in the app (My Evaluations).

Only the signed-in employee's own, and only once HR approved them, whatever the user's
roles: a manager or HR user sees their own evaluations here, never their team's. The
manager's notes on each item stay on the desk; the employee sees the parts' scores and
notes, the items' scores, and the incentive.

The employee acknowledges an evaluation, with a comment if they wish; the comment and the
time are kept on the evaluation where only HR reads them, and HR is notified of a comment
on the desk.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from hrms.api import get_current_employee

DOCTYPE = "Employee Evaluation"
HR_ROLES = ("HR Manager", "HR User")


def own_evaluation(name):
	employee = get_current_employee()
	doc = frappe.get_doc(DOCTYPE, name) if frappe.db.exists(DOCTYPE, name) else None
	if not employee or not doc or doc.employee != employee or doc.docstatus != 1:
		frappe.throw(_("This evaluation is not yours to see."), frappe.PermissionError)
	return doc


@frappe.whitelist()
def get_my_evaluations():
	employee = get_current_employee()
	if not employee:
		return []
	evaluations = frappe.get_all(
		DOCTYPE,
		filters={"employee": employee, "docstatus": 1},
		fields=["name", "payroll_period", "from_date", "to_date", "final_score", "incentive_percent", "incentive_amount", "company", "acknowledged_on"],
		order_by="from_date desc",
	)
	for row in evaluations:
		row.currency = frappe.get_cached_value("Company", row.company, "default_currency")
	return evaluations


@frappe.whitelist()
def get_my_evaluation(name):
	doc = own_evaluation(name)
	previous = frappe.get_all(
		DOCTYPE,
		filters={"employee": doc.employee, "docstatus": 1, "from_date": ("<", doc.from_date)},
		fields=["final_score"],
		order_by="from_date desc",
		limit=1,
	)
	return {
		"name": doc.name,
		"payroll_period": doc.payroll_period,
		"from_date": doc.from_date,
		"to_date": doc.to_date,
		"evaluator_name": doc.evaluator_name,
		"final_score": doc.final_score,
		"previous_score": previous[0].final_score if previous else None,
		"incentive_percent": doc.incentive_percent,
		"incentive_amount": doc.incentive_amount,
		"currency": frappe.get_cached_value("Company", doc.company, "default_currency"),
		"parts": [
			{
				"name": part.part_name,
				"weight": part.weight,
				"score": part.score,
				"notes": part.notes,
				# Items without the manager's notes.
				"items": [
					{"kra": item.kra, "weight": item.weight, "score": item.score}
					for item in doc.items
					if item.part == part.part_name
				],
			}
			for part in doc.parts
		],
		"acknowledged_on": doc.acknowledged_on,
		"employee_comment": doc.employee_comment,
	}


@frappe.whitelist(methods=["POST"])
def acknowledge(name, comment=None):
	"""The employee read the evaluation; HR hears of their comment."""
	doc = own_evaluation(name)
	if doc.acknowledged_on:
		frappe.throw(_("You already acknowledged this evaluation."))
	comment = (comment or "").strip()[:2000]
	doc.db_set({"acknowledged_on": now_datetime(), "employee_comment": comment or None})
	if comment:
		tell_hr_of_comment(doc, comment)
	return doc.acknowledged_on


def tell_hr_of_comment(doc, comment):
	"""On the desk, where HR reads evaluations (the app shows each employee only their own)."""
	from ms_hrms.app_notifications import lang_of, safe

	@safe
	def send():
		users = frappe.get_all(
			"Has Role",
			filters={"role": ("in", HR_ROLES), "parenttype": "User", "parent": ("not in", ("Administrator", "Guest"))},
			pluck="parent",
			distinct=True,
		)
		employee_user = frappe.db.get_value("Employee", doc.employee, "user_id")
		for user in set(users):
			if user == employee_user or not frappe.db.get_value("User", user, "enabled"):
				continue
			frappe.get_doc(
				{
					"doctype": "Notification Log",
					"for_user": user,
					"type": "Alert",
					"document_type": DOCTYPE,
					"document_name": doc.name,
					"from_user": employee_user,
					"subject": _("{0} commented on their evaluation for {1}", lang=lang_of(user)).format(
						doc.employee_name, doc.payroll_period
					),
					"email_content": frappe.utils.escape_html(comment),
				}
			).insert(ignore_permissions=True)

	send()


def on_submit(doc, method=None):
	"""Approved by HR: the employee is told their evaluation is ready."""
	from ms_hrms.app_notifications import is_on, lang_of, notify, safe, t, user_of

	@safe
	def send():
		user = user_of(doc.employee)
		if not user or not is_on("requests"):
			return
		lang = lang_of(user)
		notify(user, t("Your evaluation for {0} is ready: {1}", lang, doc.payroll_period, f"{doc.final_score:g}%"), DOCTYPE, doc.name)

	send()
