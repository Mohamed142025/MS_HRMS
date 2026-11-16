# Copyright (c) 2026, Mohamed Sayed and contributors
# For license information, please see license.txt

"""Each employee's salary before and after their submitted annual increments: the
salary (the structure's fixed earnings), the Base and the Incentive Amount, each with its
increase as an amount and a percentage. With "Show Components", every component whose
amount changed gets its old and new amounts and the increase too."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	rows = get_rows(filters)
	components = get_component_changes(rows) if filters.show_components else {}
	component_names = sorted({name for changes in components.values() for name in changes})

	data = []
	for row in rows:
		line = {
			"annual_increment": row.annual_increment,
			"effective_date": row.effective_date,
			"employee": row.employee,
			"employee_name": row.employee_name,
			"department": row.department,
			"grade": row.grade,
		}
		for key, old, new in (
			("salary", row.old_total, row.new_total),
			("base", row.old_base, row.new_base),
			("incentive", row.old_incentive, row.new_incentive),
		):
			line.update(compare(key, old, new))
		for index, name in enumerate(component_names):
			old, new = components.get(row.name, {}).get(name, (None, None))
			if old is not None:
				line.update(compare(f"c{index}", old, new))
		data.append(line)

	return get_columns(component_names), data, None, None, get_summary(data)


def compare(key, old, new):
	old, new = flt(old), flt(new)
	return {
		f"{key}_old": old,
		f"{key}_new": new,
		f"{key}_diff": new - old,
		f"{key}_pct": (new - old) / old * 100 if old else None,
	}


def get_rows(filters):
	increment = frappe.qb.DocType("Annual Increment")
	row = frappe.qb.DocType("Annual Increment Employee")
	employee = frappe.qb.DocType("Employee")
	query = (
		frappe.qb.from_(row)
		.join(increment)
		.on(increment.name == row.parent)
		.left_join(employee)
		.on(employee.name == row.employee)
		.select(
			row.name,
			row.parent.as_("annual_increment"),
			increment.effective_date,
			row.employee,
			row.employee_name,
			employee.department,
			employee.grade,
			row.old_total,
			row.new_total,
			row.old_base,
			row.new_base,
			row.old_incentive,
			row.new_incentive,
			row.current_structure,
			row.new_structure,
		)
		.where((increment.docstatus == 1) & (row.parenttype == "Annual Increment"))
		.orderby(increment.effective_date, order=frappe.qb.desc)
		.orderby(row.employee_name)
	)
	if filters.company:
		query = query.where(increment.company == filters.company)
	if filters.from_date:
		query = query.where(increment.effective_date >= filters.from_date)
	if filters.to_date:
		query = query.where(increment.effective_date <= filters.to_date)
	if filters.annual_increment:
		query = query.where(increment.name == filters.annual_increment)
	if filters.employee:
		query = query.where(row.employee == filters.employee)
	if filters.department:
		lft, rgt = frappe.db.get_value("Department", filters.department, ["lft", "rgt"])
		departments = frappe.get_all("Department", filters={"lft": (">=", lft), "rgt": ("<=", rgt)}, pluck="name")
		query = query.where(employee.department.isin(departments))
	if filters.grade:
		query = query.where(employee.grade == filters.grade)
	return query.run(as_dict=True)


def get_component_changes(rows):
	"""{row: {component: (old, new)}} for the fixed components whose amount changed."""
	structures = {name for row in rows for name in (row.current_structure, row.new_structure) if name}
	amounts = {}
	for detail in frappe.get_all(
		"Salary Detail",
		filters={"parenttype": "Salary Structure", "parent": ("in", list(structures)), "amount_based_on_formula": 0},
		fields=["parent", "salary_component", "amount"],
	) if structures else []:
		amounts.setdefault(detail.parent, {})[detail.salary_component] = flt(detail.amount)

	changes = {}
	for row in rows:
		old, new = amounts.get(row.current_structure, {}), amounts.get(row.new_structure, {})
		for name in old.keys() | new.keys():
			if old.get(name, 0) != new.get(name, 0):
				changes.setdefault(row.name, {})[name] = (old.get(name, 0), new.get(name, 0))
	return changes


def get_columns(component_names):
	columns = [
		{"fieldname": "annual_increment", "label": _("Annual Increment"), "fieldtype": "Link", "options": "Annual Increment", "width": 150},
		{"fieldname": "effective_date", "label": _("Effective Date"), "fieldtype": "Date", "width": 105},
		{"fieldname": "employee", "label": _("Employee"), "fieldtype": "Link", "options": "Employee", "width": 125},
		{"fieldname": "employee_name", "label": _("Employee Name"), "fieldtype": "Data", "width": 170},
		{"fieldname": "department", "label": _("Department"), "fieldtype": "Link", "options": "Department", "width": 150},
		{"fieldname": "grade", "label": _("Grade"), "fieldtype": "Link", "options": "Employee Grade", "width": 90},
	]
	groups = [("salary", _("Salary")), ("base", _("Base")), ("incentive", _("Incentive"))]
	groups += [(f"c{index}", name) for index, name in enumerate(component_names)]
	for key, label in groups:
		columns += [
			{"fieldname": f"{key}_old", "label": _("{0} Old").format(label), "fieldtype": "Currency", "width": 120},
			{"fieldname": f"{key}_new", "label": _("{0} New").format(label), "fieldtype": "Currency", "width": 120},
			{"fieldname": f"{key}_diff", "label": _("{0} Increase").format(label), "fieldtype": "Currency", "width": 120},
			{"fieldname": f"{key}_pct", "label": _("{0} Increase %").format(label), "fieldtype": "Percent", "width": 105},
		]
	return columns


def get_summary(data):
	if not data:
		return []
	old = sum(flt(row["salary_old"]) for row in data)
	new = sum(flt(row["salary_new"]) for row in data)
	return [
		{"label": _("Employees"), "value": len(data), "datatype": "Int"},
		{"label": _("Old Salaries"), "value": old, "datatype": "Currency"},
		{"label": _("New Salaries"), "value": new, "datatype": "Currency"},
		{"label": _("Total Increase"), "value": new - old, "datatype": "Currency", "indicator": "Green"},
		{"label": _("Increase %"), "value": (new - old) / old * 100 if old else 0, "datatype": "Percent", "indicator": "Green"},
	]
