from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from ms_hrms.custom_hrms.services.attendance_penalty import calculate_for_employee, get_applicable_policy


class AttendancePenaltyProcessing(Document):
	def before_cancel(self):
		self.ignore_linked_doctypes = ["Attendance Penalty Detail"]

	def validate(self):
		self.validate_dates()
		self.validate_scope()
		self.calculate_totals()
		if self.docstatus == 0 and self.status == "Submitted":
			self.status = "Calculated"

	def validate_dates(self):
		if not self.posting_date:
			self.posting_date = today()
		if not self.from_date or not self.to_date:
			frappe.throw(_("From Date and To Date are required."))
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From Date cannot be after To Date."))

	def resolve_payroll_period(self):
		if self.payroll_period:
			period = frappe.get_cached_doc("Payroll Period", self.payroll_period)
		else:
			period_name = frappe.db.get_value(
				"Payroll Period",
				{"start_date": ["<=", self.from_date], "end_date": [">=", self.to_date]},
				"name",
			)
			if not period_name:
				frappe.throw(_("Select a Payroll Period covering the processing dates."))
			self.payroll_period = period_name
			period = frappe.get_cached_doc("Payroll Period", self.payroll_period)
		self.from_date = period.start_date
		self.to_date = period.end_date

	def validate_scope(self):
		if self.apply_on == "Department" and not self.department:
			frappe.throw(_("Department is required."))
		if self.apply_on == "Employee" and not self.employee:
			frappe.throw(_("Employee is required."))

	def calculate_totals(self):
		self.total_entry_deduction = sum(flt(row.deduction_amount) for row in self.details if row.penalty_type == "Late Entry")
		self.total_exit_deduction = sum(flt(row.deduction_amount) for row in self.details if row.penalty_type == "Early Exit")
		self.grand_total = flt(self.total_entry_deduction) + flt(self.total_exit_deduction)

	@frappe.whitelist()
	def get_attendance(self):
		self.check_permission("write")
		self.validate_dates()
		self.resolve_payroll_period()
		employees = get_processing_employees(self)
		if not employees:
			frappe.throw(_("No employees matched the selected scope."))
		self.set("details", [])
		for employee in employees:
			policy = get_applicable_policy(employee, self.policy)
			if not policy:
				continue
			for detail in calculate_for_employee(employee, self.from_date, self.to_date, policy, self.payroll_period):
				detail["penalty_processing"] = self.name
				row = self.append("details", {})
				for fieldname, value in detail.items():
					row.set(fieldname, value)
				missing = [
					fieldname
					for fieldname in ("employee", "attendance_date", "payroll_period", "policy")
					if not row.get(fieldname)
				]
				if missing:
					frappe.throw(_("Generated detail row is missing: {0}").format(", ".join(missing)))
		self.calculate_totals()
		self.status = "Calculated"
		return self.as_dict()

	def before_submit(self):
		if self.status != "Calculated":
			frappe.throw(_("Get Attendance and review the calculations before submitting."))
		if not self.details:
			frappe.throw(_("There are no attendance penalty details to submit."))
		for row in self.details:
			missing = [
				fieldname
				for fieldname in ("employee", "attendance_date", "payroll_period", "policy")
				if not row.get(fieldname)
			]
			if missing:
				frappe.throw(_("Detail row {0} is missing: {1}").format(row.idx, ", ".join(missing)))
		if any(row.review_required and row.deduction_type == "Review Required" for row in self.details):
			frappe.throw(_("Resolve all Review Required details before submitting."))
		validate_duplicate_attendance(self.details)

	def on_submit(self):
		self.create_additional_salaries()
		self.db_set("status", "Submitted")

	def on_cancel(self):
		for name in json.loads(self.additional_salary_references or "[]"):
			if frappe.db.exists("Additional Salary", name):
				salary = frappe.get_doc("Additional Salary", name)
				if salary.docstatus == 1:
					salary.cancel()
		self.db_set("status", "Cancelled")

	def create_additional_salaries(self):
		from ms_hrms.custom_hrms.services.attendance_penalty import ensure_salary_component

		created = []
		for (employee, component), rows in group_details_by_employee(self.details).items():
			amount = flt(sum(flt(row.deduction_amount) for row in rows))
			if amount <= 0:
				continue
			if frappe.db.exists("Additional Salary", {"ref_doctype": self.doctype, "ref_docname": self.name, "employee": employee, "docstatus": ["!=", 2]}):
				frappe.throw(_("An Additional Salary already exists for {0} and this processing.").format(employee))
			company = frappe.db.get_value("Employee", employee, "company")
			values = {"doctype": "Additional Salary", "employee": employee, "salary_component": ensure_salary_component(component), "amount": amount, "payroll_date": self.posting_date, "company": company}
			meta = frappe.get_meta("Additional Salary")
			if meta.has_field("ref_doctype"):
				values.update({"ref_doctype": self.doctype, "ref_docname": self.name})
			salary = frappe.get_doc(values)
			salary.insert(ignore_permissions=True)
			salary.submit()
			created.append(salary.name)
		self.additional_salary = created[0] if created else None
		self.additional_salary_references = json.dumps(created)
		self.db_set({"additional_salary": self.additional_salary, "additional_salary_references": self.additional_salary_references})


def get_processing_employees(processing):
	filters = {"status": "Active"}
	if processing.apply_on == "Employee":
		return [processing.employee] if processing.employee else []
	if processing.apply_on == "Department":
		filters["department"] = processing.department
	return frappe.get_all("Employee", filters=filters, pluck="name")


def validate_duplicate_attendance(details):
	attendance_names = {row.attendance for row in details if row.attendance}
	if not attendance_names:
		return
	duplicates = frappe.db.sql(
		"""
		select d.attendance from `tabAttendance Penalty Detail` d
		join `tabAttendance Penalty Processing` p on p.name = d.parent
		where p.docstatus = 1 and d.attendance in %(attendance_names)s
		""",
		{"attendance_names": tuple(attendance_names)},
		pluck="attendance",
	)
	if duplicates:
		frappe.throw(_("These Attendance records were already processed: {0}").format(", ".join(duplicates)))


def group_details_by_employee(details):
	grouped = {}
	for row in details:
		policy = frappe.get_cached_doc("Attendance Penalty Policy", row.policy)
		component = policy.deduction_salary_component
		grouped.setdefault((row.employee, component), []).append(row)
	return grouped
