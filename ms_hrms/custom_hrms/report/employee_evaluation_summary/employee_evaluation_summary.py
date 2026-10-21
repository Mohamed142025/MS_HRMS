"""Each employee's evaluation for a period: a column for each part (its score out of its
weight), the final score and the incentive. Only the evaluations the user may see are shown."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	conditions = {"docstatus": ("<", 2)}
	for field in ("payroll_period", "department", "status"):
		if filters.get(field):
			conditions[field] = filters.get(field)

	data = frappe.get_list(
		"Employee Evaluation",
		filters=conditions,
		fields=["name", "employee", "employee_name", "department", "evaluator_name", "final_score", "incentive_percent", "incentive_amount", "status"],
		order_by="department, employee",
	)

	# The parts, in the order they first appear, each in its own column.
	parts = []
	weights = {}
	by_evaluation = {}
	if data:
		for row in frappe.get_all(
			"Employee Evaluation Part",
			filters={"parenttype": "Employee Evaluation", "parent": ("in", [d.name for d in data])},
			fields=["parent", "part_name", "score", "weight"],
			order_by="parent, idx",
		):
			if row.part_name not in parts:
				parts.append(row.part_name)
			weights.setdefault(row.part_name, set()).add(f"{flt(row.weight, 2):g}")
			by_evaluation.setdefault(row.parent, {})[part_field(parts.index(row.part_name))] = row.score
	for row in data:
		row.update(by_evaluation.get(row.name, {}))

	return get_columns(parts, weights), data


def part_field(index):
	return f"part_{index}"


def part_label(part, weights):
	"""The part with its weight, the most it scores; templates may weigh a part differently."""
	weight = weights.get(part, set())
	return _("{0} (من {1})").format(part, next(iter(weight))) if len(weight) == 1 else part


def get_columns(parts, weights):
	return [
		{"label": _("التقييم"), "fieldname": "name", "fieldtype": "Link", "options": "Employee Evaluation", "width": 190},
		{"label": _("الموظف"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("اسم الموظف"), "fieldname": "employee_name", "fieldtype": "Data", "width": 180},
		{"label": _("القسم"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 160},
		{"label": _("المقيِّم"), "fieldname": "evaluator_name", "fieldtype": "Data", "width": 150},
		*(
			{"label": part_label(part, weights), "fieldname": part_field(index), "fieldtype": "Float", "width": 140}
			for index, part in enumerate(parts)
		),
		{"label": _("النتيجة النهائية"), "fieldname": "final_score", "fieldtype": "Percent", "width": 120},
		{"label": _("نسبة صرف الحافز"), "fieldname": "incentive_percent", "fieldtype": "Percent", "width": 120},
		{"label": _("الحافز المستحق"), "fieldname": "incentive_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("الحالة"), "fieldname": "status", "fieldtype": "Data", "width": 160},
	]
