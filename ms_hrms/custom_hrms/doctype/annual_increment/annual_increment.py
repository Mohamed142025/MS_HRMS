# Copyright (c) 2026, Mohamed Sayed and contributors
# For license information, please see license.txt

"""The annual increment of a group of employees: one employee, a department (with its
sub-departments) or a grade.

Each employee's increment starts from their latest submitted Salary Structure Assignment
on the effective date and its Salary Structure. The chosen components of that structure
rise by a percentage or an amount, and so may the assignment's Base and Incentive Amount; every amount is rounded to the nearest pound.

On submit, each employee gets a Salary Structure of their own, a copy of the old one with
every component it had (those at 0 included) and the new amounts, and a new assignment of
it from the effective date with the new Base and Incentive Amount. The employee's
assignments from the effective date on are cancelled first, as the confirmation says.
Cancelling the increment cancels what it made; the assignments it cancelled stay
cancelled.
"""

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, fmt_money, getdate, rounded

INCENTIVE_FIELD = "custom_incentive_amount"
# Records that keep naming a cancelled assignment, as history.
KEEP_LINKS_FROM = ("Employee Evaluation", "Annual Increment")


class AnnualIncrement(Document):
	def validate(self):
		if not self.employees:
			self.get_employees()
		if not self.employees:
			frappe.throw(_("No active employees match this selection."))
		if not (any(flt(row.value) for row in self.components) or flt(self.base_percentage) or flt(self.incentive_percentage)):
			frappe.throw(_("Set the increase: salary components, the Base or the Incentive percentage."))
		self.validate_components()
		self.validate_base_and_incentive()
		self.validate_employees()
		warnings = []
		for row in self.employees:
			warnings += self.compute(row)
		if warnings:
			frappe.msgprint("<br>".join(dict.fromkeys(warnings)), title=_("Please Note"), indicator="orange")

	def validate_components(self):
		seen = set()
		for row in self.components:
			if row.salary_component in seen:
				frappe.throw(_("Row {0}: {1} is listed twice.").format(row.idx, frappe.bold(row.salary_component)))
			seen.add(row.salary_component)
			if row.increment_type == "Percentage" and flt(row.value) <= -100:
				frappe.throw(_("Row {0}: the percentage must be above -100.").format(row.idx))

	def validate_base_and_incentive(self):
		for label, kind, value in (
			(_("Base Increase"), self.base_increment_type, self.base_percentage),
			(_("Incentive Increase"), self.incentive_increment_type, self.incentive_percentage),
		):
			if kind != "Amount" and flt(value) <= -100:
				frappe.throw(_("{0}: the percentage must be above -100.").format(label))

	def validate_employees(self):
		seen = set()
		for row in self.employees:
			if row.employee in seen:
				frappe.throw(_("Employee {0} is listed twice.").format(frappe.bold(row.employee)))
			seen.add(row.employee)

	@frappe.whitelist()
	def get_employees(self):
		"""The active employees of the company in this selection."""
		filters = {"company": self.company, "status": "Active"}
		if self.apply_to == "Employee":
			if not self.employee:
				frappe.throw(_("Select the employee."))
			filters["name"] = self.employee
		elif self.apply_to == "Department":
			if not self.department:
				frappe.throw(_("Select the department."))
			lft, rgt = frappe.db.get_value("Department", self.department, ["lft", "rgt"])
			filters["department"] = (
				"in",
				frappe.get_all("Department", filters={"lft": (">=", lft), "rgt": ("<=", rgt)}, pluck="name"),
			)
		elif self.apply_to == "Grade":
			if not self.grade:
				frappe.throw(_("Select the grade."))
			filters["grade"] = self.grade
		self.set("employees", [])
		for employee in frappe.get_all("Employee", filters=filters, fields=["name", "employee_name"], order_by="name"):
			self.append("employees", {"employee": employee.name, "employee_name": employee.employee_name})

	@frappe.whitelist()
	def get_salary_components(self):
		"""Lists the fixed earnings of the employees' latest salary structures, each at 0
		until an increase is entered; rows already entered keep their values. With one
		employee, each shows its current amount."""
		if self.apply_to == "Employee" and self.employee:
			employees = [self.employee]
		else:
			if not self.employees:
				self.get_employees()
			employees = [row.employee for row in self.employees]
		on = self.effective_date or frappe.utils.today()
		components = {}
		for employee in employees:
			assignment = get_current_assignment(employee, on)
			if not assignment:
				continue
			for detail in frappe.get_all(
				"Salary Detail",
				filters={
					"parenttype": "Salary Structure",
					"parent": assignment.salary_structure,
					"parentfield": "earnings",
					"amount_based_on_formula": 0,
				},
				fields=["salary_component", "amount"],
				order_by="idx",
			):
				components.setdefault(detail.salary_component, []).append(flt(detail.amount))
		entered = {row.salary_component: row for row in self.components}
		single = len(employees) == 1
		for name, amounts in components.items():
			row = entered.get(name) or self.append(
				"components", {"salary_component": name, "increment_type": "Percentage", "value": 0}
			)
			row.current_amount = amounts[0] if single else None

	# The increase ---------------------------------------------------------------------

	def compute(self, row):
		"""Fills the row with the employee's old and new pay; returns warnings."""
		assignment = get_current_assignment(row.employee, self.effective_date)
		if not assignment:
			frappe.throw(
				_("Employee {0} ({1}) has no submitted Salary Structure Assignment on {2}.").format(
					frappe.bold(row.employee), row.employee_name, frappe.format(self.effective_date, "Date")
				)
			)
		structure = frappe.get_doc("Salary Structure", assignment.salary_structure)
		old_total, new_total, changes, warnings = 0, 0, [], []
		increments = {row.salary_component: row for row in self.components}
		found = set()
		for component in structure.earnings + structure.deductions:
			if component.salary_component not in increments:
				if component.parentfield == "earnings" and not component.amount_based_on_formula:
					old_total += flt(component.amount)
					new_total += flt(component.amount)
				continue
			found.add(component.salary_component)
			if component.amount_based_on_formula:
				warnings.append(
					_("{0} is calculated by a formula in {1}; it is kept as it is.").format(
						frappe.bold(component.salary_component), structure.name
					)
				)
				continue
			new_amount = raise_amount(component.amount, increments[component.salary_component])
			if component.parentfield == "earnings":
				old_total += flt(component.amount)
				new_total += new_amount
			if new_amount != flt(component.amount):
				changes.append(f"{component.salary_component}: \u2066{money(component.amount)} → {money(new_amount)}\u2069")
		for component in increments:
			if component not in found:
				warnings.append(
					_("{0} is not in {1}'s salary structure.").format(frappe.bold(component), row.employee_name)
				)

		row.current_assignment = assignment.name
		row.current_structure = structure.name
		row.old_base = flt(assignment.base)
		row.new_base = raise_amount(assignment.base, frappe._dict(increment_type=self.base_increment_type, value=self.base_percentage))
		row.old_incentive = flt(assignment.get(INCENTIVE_FIELD))
		row.new_incentive = raise_amount(
			row.old_incentive, frappe._dict(increment_type=self.incentive_increment_type, value=self.incentive_percentage)
		)
		for label, old, new in ((_("Base"), row.old_base, row.new_base), (_("Incentive"), row.old_incentive, row.new_incentive)):
			if old != new:
				changes.append(f"{label}: \u2066{money(old)} → {money(new)}\u2069")
		row.old_total = old_total
		row.new_total = new_total
		row.increase = new_total - old_total
		row.changes = "\n".join(changes) or _("No change")
		row.assignments_to_cancel = "\n".join(
			f"{name} ({frappe.format(from_date, 'Date')})"
			for name, from_date in get_assignments_to_cancel(row.employee, self.effective_date)
		)
		return warnings

	# Submit and cancel ----------------------------------------------------------------

	def on_submit(self):
		for row in self.employees:
			for name, _from_date in get_assignments_to_cancel(row.employee, self.effective_date):
				assignment = frappe.get_doc("Salary Structure Assignment", name)
				assignment.flags.ignore_permissions = True
				# Evaluations keep naming the assignment they were made under.
				assignment.ignore_linked_doctypes = KEEP_LINKS_FROM
				assignment.cancel()
			structure = self.make_structure(row)
			assignment = self.make_assignment(row, structure)
			row.db_set({"new_structure": structure.name, "new_assignment": assignment.name})

	def make_structure(self, row):
		old = frappe.get_doc("Salary Structure", row.current_structure)
		increments = {item.salary_component: item for item in self.components}
		new = frappe.copy_doc(old)
		new.is_active = "Yes"
		for component in new.earnings + new.deductions:
			if component.salary_component in increments and not component.amount_based_on_formula:
				component.amount = raise_amount(component.amount, increments[component.salary_component])
		new.flags.ignore_permissions = True
		new.insert(set_name=self.structure_name(old.name))
		new.submit()
		return new

	def structure_name(self, old_name):
		stem = re.sub(r" - \d{4}(-\d+)?$", "", old_name)
		name = f"{stem} - {getdate(self.effective_date).year}"
		suffix = 1
		while frappe.db.exists("Salary Structure", name):
			suffix += 1
			name = f"{stem} - {getdate(self.effective_date).year}-{suffix}"
		return name

	def make_assignment(self, row, structure):
		old = frappe.get_doc("Salary Structure Assignment", row.current_assignment)
		new = frappe.copy_doc(old)
		new.amended_from = None
		new.salary_structure = structure.name
		new.from_date = self.effective_date
		new.base = row.new_base
		if new.meta.has_field(INCENTIVE_FIELD):
			new.set(INCENTIVE_FIELD, row.new_incentive)
		new.flags.ignore_permissions = True
		new.insert()
		new.submit()
		return new

	def on_cancel(self):
		for row in self.employees:
			if row.new_assignment and frappe.db.get_value("Salary Structure Assignment", row.new_assignment, "docstatus") == 1:
				assignment = frappe.get_doc("Salary Structure Assignment", row.new_assignment)
				assignment.flags.ignore_permissions = True
				assignment.cancel()
			if row.new_structure and frappe.db.get_value("Salary Structure", row.new_structure, "docstatus") == 1:
				structure = frappe.get_doc("Salary Structure", row.new_structure)
				structure.flags.ignore_permissions = True
				structure.cancel()


def raise_amount(amount, increment):
	if increment.increment_type == "Amount":
		return rounded(flt(amount) + flt(increment.value), 0)
	return rounded(flt(amount) * (1 + flt(increment.value) / 100), 0)


def money(value):
	return fmt_money(value, precision=0)


def get_current_assignment(employee, effective_date):
	"""The employee's latest submitted assignment on the effective date."""
	rows = frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": employee, "docstatus": 1, "from_date": ("<=", effective_date)},
		fields=["name"],
		order_by="from_date desc, creation desc",
		limit=1,
	)
	return frappe.get_doc("Salary Structure Assignment", rows[0].name) if rows else None


def get_assignments_to_cancel(employee, effective_date):
	"""The employee's submitted assignments from the effective date on."""
	return frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": employee, "docstatus": 1, "from_date": (">=", effective_date)},
		fields=["name", "from_date"],
		order_by="from_date",
		as_list=True,
	)
