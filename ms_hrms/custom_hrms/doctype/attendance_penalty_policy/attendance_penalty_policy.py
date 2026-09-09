import frappe
from frappe import _
from frappe.model.document import Document


class AttendancePenaltyPolicy(Document):
	def validate(self):
		self.validate_scope()
		self.validate_values()
		self.validate_rules(self.entry_rules, _("Entry Rules"))
		self.validate_rules(self.exit_rules, _("Exit Rules"))
		self.validate_duplicate_scope()

	def validate_scope(self):
		if self.apply_on == "Department" and not self.department:
			frappe.throw(_("Department is required when Apply On is Department."))
		if self.apply_on == "Employee" and not self.employee:
			frappe.throw(_("Employee is required when Apply On is Employee."))
		if self.apply_on == "All Employees":
			self.department = None
			self.employee = None

	def validate_values(self):
		if self.entry_grace_period < 0 or self.exit_grace_period < 0 or self.allowed_grace_occurrences < 0:
			frappe.throw(_("Grace periods and allowed grace occurrences cannot be negative."))
		if self.salary_divisor <= 0 or self.working_hours_per_day <= 0:
			frappe.throw(_("Salary divisor and working hours must be greater than zero."))
		if self.deduction_based_on == "Salary Component" and not self.salary_component:
			frappe.throw(_("Salary Component is required for this deduction basis."))

	def validate_rules(self, rules, label):
		seen = set()
		for rule in rules:
			if not rule.enabled:
				continue
			if rule.occurrence_number <= 0:
				frappe.throw(_("{0}: occurrence number must be greater than zero.").format(label))
			if rule.occurrence_number in seen:
				frappe.throw(_("{0}: occurrence number {1} is duplicated.").format(label, rule.occurrence_number))
			if rule.max_late_minutes < 0 or rule.deduction_value < 0:
				frappe.throw(_("{0}: minutes and deduction value cannot be negative.").format(label))
			seen.add(rule.occurrence_number)

	def validate_duplicate_scope(self):
		if not self.enabled:
			return
		filters = {"enabled": 1, "apply_on": self.apply_on, "name": ["!=", self.name]}
		if self.apply_on == "Department":
			filters["department"] = self.department
		elif self.apply_on == "Employee":
			filters["employee"] = self.employee
		if frappe.db.exists("Attendance Penalty Policy", filters):
			frappe.throw(_("Another enabled policy already exists for this scope."))
