"""Monthly employee evaluation, the basis of the incentive.

One evaluation per employee and Payroll Period, with the parts and items of the employee's
Employee Evaluation Template. Each part is scored either by the employee's manager (Reports
To) or by HR, and each item out of its weight.

The manager scores their parts and sends the evaluation to HR; HR scores its parts and
submits it (or returns it to the manager). A part's score is out of its weight, the final
score is the parts' scores added up, and the incentive is the employee's incentive amount
(on their Salary Structure Assignment) times the share the template's incentive slabs give
that score. The slabs are copied with the items, so a later change to the template leaves
the evaluation as it was. Submitting makes an Additional Salary with it on the incentive
component of Payroll Settings; cancelling cancels it.

HR sees every evaluation. Anyone else sees the evaluations they score, and their own once
it is submitted.
"""

import frappe
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import flt, get_link_to_form

from ms_hrms.custom_hrms.doctype.employee_evaluation_template.employee_evaluation_template import (
	get_incentive_percent,
	get_template_for,
)

STATUS_MANAGER = "بانتظار تقييم المدير"
STATUS_HR = "بانتظار الموارد البشرية"
STATUS_APPROVED = "معتمد"
STATUS_CANCELLED = "ملغي"

# Who scores a part.
BY_MANAGER = "مدير الموظف"
BY_HR = "الموارد البشرية"
# What only HR may change on an evaluation.
HEADER_FIELDS = ("employee", "payroll_period", "template", "evaluator")
HR_ROLES = {"HR Manager", "HR User", "System Manager"}
INCENTIVE_FIELD = "custom_incentive_amount"
COMPONENT_FIELD = "custom_incentive_salary_component"


class EmployeeEvaluation(Document):
	ignore_linked_doctypes = ("Additional Salary",)

	def validate(self):
		self.set_period()
		self.validate_duplicate()
		if not self.template:
			self.template = get_template_for(self.employee)
		if not self.template:
			frappe.throw(_("لا يوجد قالب تقييم للموظف {0}: لا لمسماه ولا لقسمه، ولا يوجد قالب افتراضي.").format(self.employee))
		# An amended evaluation keeps the scores it was copied with.
		if (self.is_new() and not self.items) or (not self.is_new() and self.has_value_changed("template")):
			self.set_items()
		elif not self.incentive_slabs:
			# Made before the template had slabs.
			self.set_incentive_slabs(frappe.get_doc("Employee Evaluation Template", self.template))
		if self.is_new() and not any(row.evaluated_by == BY_MANAGER for row in self.items):
			# Nothing for the manager to score.
			self.status = STATUS_HR
		self.validate_changes()
		self.validate_scores()
		self.set_incentive_base()
		self.calculate()

	def on_update(self):
		self.sync_assignment()

	def before_submit(self):
		if not is_hr():
			frappe.throw(_("الموارد البشرية فقط تعتمد التقييم."), frappe.PermissionError)
		if self.status != STATUS_HR:
			frappe.throw(_("لم يرسل المدير تقييمه بعد."))
		if flt(self.incentive_amount) > 0 and not frappe.db.get_single_value("Payroll Settings", COMPONENT_FIELD):
			frappe.throw(_("حدد «مكون راتب الحوافز» في Payroll Settings."))
		self.status = STATUS_APPROVED

	def on_submit(self):
		assign_to.close_all_assignments(self.doctype, self.name, ignore_permissions=True)
		self.make_additional_salary()

	def on_cancel(self):
		if self.additional_salary and frappe.db.get_value("Additional Salary", self.additional_salary, "docstatus") == 1:
			additional_salary = frappe.get_doc("Additional Salary", self.additional_salary)
			additional_salary.flags.ignore_links = True
			additional_salary.flags.ignore_permissions = True
			additional_salary.cancel()
		self.db_set("status", STATUS_CANCELLED)

	# Setup ------------------------------------------------------------------------------

	def set_period(self):
		self.from_date, self.to_date = frappe.db.get_value(
			"Payroll Period", self.payroll_period, ["start_date", "end_date"]
		)

	def validate_duplicate(self):
		other = frappe.db.get_value(
			"Employee Evaluation",
			{
				"employee": self.employee,
				"payroll_period": self.payroll_period,
				"docstatus": ("<", 2),
				"name": ("!=", self.name),
			},
		)
		if other:
			frappe.throw(_("للموظف تقييم في نفس الفترة: {0}").format(get_link_to_form(self.doctype, other)))

	def set_items(self):
		template = frappe.get_doc("Employee Evaluation Template", self.template)
		self.set("parts", [])
		self.set("items", [])
		for part in template.parts:
			self.append(
				"parts",
				{
					"part_name": part.part_name,
					"weight": part.weight,
					"evaluated_by": part.evaluated_by,
					"notes": part.notes,
				},
			)
			for row in template.items:
				if row.part == part.part_name:
					self.append(
						"items",
						{"part": part.part_name, "evaluated_by": part.evaluated_by, "kra": row.kra, "weight": row.weight},
					)
		self.set_incentive_slabs(template)

	def set_incentive_slabs(self, template):
		if not template.incentive_slabs:
			frappe.throw(
				_("قالب التقييم {0} ليس له شرائح حافز؛ حددها في القالب أولًا.").format(
					get_link_to_form(template.doctype, template.name)
				)
			)
		self.set(
			"incentive_slabs",
			[
				{"from_score": row.from_score, "to_score": row.to_score, "incentive_percent": row.incentive_percent}
				for row in template.incentive_slabs
			],
		)

	def validate_changes(self):
		"""The items come from the template. The manager scores the items of the manager's
		parts while the evaluation waits for them, and HR scores those of HR's parts."""
		before = self.get_doc_before_save()
		if not before or frappe.session.user == "Administrator":
			return

		if self.status != before.status and not self.flags.status_action:
			frappe.throw(_("حالة التقييم تتغير بأزرار الإرسال والإرجاع فقط."))

		header_changed = any(self.get(f) != before.get(f) for f in HEADER_FIELDS)
		if header_changed and not is_hr():
			frappe.throw(_("بيانات التقييم الأساسية تعدّلها الموارد البشرية فقط."), frappe.PermissionError)
		if self.has_value_changed("template"):
			return

		layout = lambda doc: [  # noqa: E731
			(row.name, row.part, row.evaluated_by, row.kra, flt(row.weight)) for row in doc.items
		]
		parts = lambda doc: [  # noqa: E731
			(row.part_name, flt(row.weight), row.evaluated_by, row.notes or "") for row in doc.parts
		]
		slabs = lambda doc: [  # noqa: E731
			(flt(row.from_score), flt(row.to_score), flt(row.incentive_percent)) for row in doc.incentive_slabs
		]
		if layout(self) != layout(before) or parts(self) != parts(before):
			frappe.throw(_("أجزاء التقييم وبنوده تأتي من القالب ولا تُعدَّل في التقييم."))
		# Slabs copied now, onto an evaluation made before the template had them, are new.
		if before.incentive_slabs and slabs(self) != slabs(before):
			frappe.throw(_("شرائح الحافز تأتي من القالب ولا تُعدَّل في التقييم."))

		previous = {row.name: row for row in before.items}
		for row in self.items:
			old = previous[row.name]
			if (flt(row.score), (row.notes or "").strip()) == (flt(old.score), (old.notes or "").strip()):
				continue
			if row.evaluated_by == BY_MANAGER:
				if self.evaluator_user != frappe.session.user:
					frappe.throw(
						_("جزء {0} يقيّمه مدير الموظف فقط.").format(frappe.bold(row.part)), frappe.PermissionError
					)
				if self.status != STATUS_MANAGER:
					frappe.throw(_("أُرسل التقييم للموارد البشرية؛ لا يمكن تعديل تقييم المدير إلا بعد إرجاعه."))
			elif not is_hr():
				frappe.throw(
					_("جزء {0} تقيّمه الموارد البشرية فقط.").format(frappe.bold(row.part)), frappe.PermissionError
				)

	def validate_scores(self):
		for row in self.items:
			if not 0 <= flt(row.score) <= flt(row.weight):
				frappe.throw(
					_("درجة البند {0} يجب أن تكون بين 0 و {1} (وزن البند).").format(
						frappe.bold(row.kra), f"{flt(row.weight, 2):g}"
					)
				)

	def set_incentive_base(self):
		assignment = frappe.get_all(
			"Salary Structure Assignment",
			filters={"employee": self.employee, "docstatus": 1, "from_date": ("<=", self.to_date)},
			fields=["name", INCENTIVE_FIELD],
			order_by="from_date desc",
			limit=1,
		)
		self.salary_structure_assignment = assignment[0].name if assignment else None
		self.incentive_base = flt(assignment[0].get(INCENTIVE_FIELD)) if assignment else 0

	def calculate(self):
		"""An item is scored out of its weight, so a part's items add up to 100 at most; the
		part's score is that share of the part's weight, and the final score their sum."""
		final = 0
		for part in self.parts:
			score = sum(flt(row.score) for row in self.items if row.part == part.part_name) * flt(part.weight) / 100
			part.score = flt(score, 2)
			final += score
		self.final_score = flt(final, 2)
		self.incentive_percent = get_incentive_percent(self.final_score, self.incentive_slabs)
		self.incentive_amount = flt(
			flt(self.incentive_base) * self.incentive_percent / 100, self.precision("incentive_amount")
		)

	# Assignments ------------------------------------------------------------------------

	def sync_assignment(self):
		"""The manager has a ToDo while the evaluation waits for them."""
		if self.docstatus != 0:
			return
		open_users = {row.owner for row in assign_to.get({"doctype": self.doctype, "name": self.name})}
		wanted = {self.evaluator_user} if self.status == STATUS_MANAGER and self.evaluator_user else set()
		for user in open_users - wanted:
			assign_to._remove(self.doctype, self.name, user, ignore_permissions=True)
		for user in wanted - open_users:
			assign_to._add(
				{
					"doctype": self.doctype,
					"name": self.name,
					"assign_to": [user],
					"description": _("تقييم {0} عن فترة {1}").format(self.employee_name, self.payroll_period),
				},
				ignore_permissions=True,
			)

	# Payroll ----------------------------------------------------------------------------

	def make_additional_salary(self):
		if flt(self.incentive_amount) <= 0:
			frappe.msgprint(_("الحافز المستحق صفر، فلم تُنشأ Additional Salary."), alert=True)
			return
		additional_salary = frappe.get_doc(
			{
				"doctype": "Additional Salary",
				"employee": self.employee,
				"company": self.company,
				"currency": frappe.get_cached_value("Company", self.company, "default_currency"),
				"salary_component": frappe.db.get_single_value("Payroll Settings", COMPONENT_FIELD),
				"amount": self.incentive_amount,
				"payroll_date": self.to_date,
				"overwrite_salary_structure_amount": 0,
				"ref_doctype": self.doctype,
				"ref_docname": self.name,
			}
		)
		additional_salary.flags.ignore_permissions = True
		additional_salary.insert()
		additional_salary.submit()
		self.db_set("additional_salary", additional_salary.name)


def is_hr(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or bool(HR_ROLES & set(frappe.get_roles(user)))


# Actions --------------------------------------------------------------------------------


@frappe.whitelist()
def send_to_hr(name):
	"""The manager is done with their two parts."""
	doc = frappe.get_doc("Employee Evaluation", name)
	if doc.docstatus != 0 or doc.status != STATUS_MANAGER:
		frappe.throw(_("التقييم ليس بانتظار تقييم المدير."))
	if doc.evaluator_user != frappe.session.user and frappe.session.user != "Administrator":
		frappe.throw(_("يرسل التقييم مدير الموظف فقط."), frappe.PermissionError)
	doc.status = STATUS_HR
	doc.flags.status_action = True
	# The manager may no longer write it once it waits for HR.
	doc.flags.ignore_permissions = True
	doc.save()
	doc.add_comment("Info", _("أرسل المدير تقييمه للموارد البشرية."))


@frappe.whitelist()
def return_to_manager(name, reason=None):
	doc = frappe.get_doc("Employee Evaluation", name)
	if not is_hr():
		frappe.throw(_("الموارد البشرية فقط ترجع التقييم."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.status != STATUS_HR:
		frappe.throw(_("التقييم ليس بانتظار الموارد البشرية."))
	doc.status = STATUS_MANAGER
	doc.flags.status_action = True
	doc.save()
	doc.add_comment("Info", _("أُرجع التقييم للمدير: {0}").format(reason or ""))


# Permissions ----------------------------------------------------------------------------


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if is_hr(user):
		return ""
	user = frappe.db.escape(user)
	return f"""(`tabEmployee Evaluation`.evaluator_user = {user}
		or (`tabEmployee Evaluation`.docstatus = 1 and `tabEmployee Evaluation`.employee in (
			select name from `tabEmployee` where user_id = {user})))"""


def has_permission(doc, ptype=None, user=None, debug=False):
	"""Behind get_permission_query_conditions for single evaluations. It only takes away
	what the roles give; True leaves the roles to decide."""
	user = user or frappe.session.user
	if is_hr(user) or doc.is_new():
		return True
	scorer = doc.evaluator_user == user
	if ptype == "write":
		return scorer and doc.docstatus == 0 and doc.status == STATUS_MANAGER
	if ptype in ("read", "print", "email"):
		own = doc.docstatus == 1 and frappe.db.get_value("Employee", doc.employee, "user_id") == user
		return scorer or own
	return False


# Creating a period's evaluations --------------------------------------------------------


@frappe.whitelist()
def get_template(employee):
	frappe.has_permission("Employee Evaluation", "create", throw=True)
	return get_template_for(employee)


@frappe.whitelist()
def create_evaluations(payroll_period):
	"""An evaluation for each active employee of the period's company who has none in it."""
	frappe.has_permission("Employee Evaluation", "create", throw=True)
	company = frappe.db.get_value("Payroll Period", payroll_period, "company")
	existing = set(
		frappe.get_all(
			"Employee Evaluation",
			filters={"payroll_period": payroll_period, "docstatus": ("<", 2)},
			pluck="employee",
		)
	)
	result = frappe._dict(created=[], no_template=[], no_evaluator=[], no_incentive=[])
	for employee in frappe.get_all(
		"Employee",
		filters={"status": "Active", "company": company},
		fields=["name", "employee_name", "reports_to"],
		order_by="name",
	):
		if employee.name in existing:
			continue
		label = f"{employee.name}: {employee.employee_name}"
		template = get_template_for(employee.name)
		if not template:
			result.no_template.append(label)
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Employee Evaluation",
				"employee": employee.name,
				"payroll_period": payroll_period,
				"template": template,
				"evaluator": employee.reports_to,
			}
		).insert()
		result.created.append(doc.name)
		if not doc.evaluator_user:
			result.no_evaluator.append(label)
		if not doc.incentive_base:
			result.no_incentive.append(label)
	return result


# Setup ----------------------------------------------------------------------------------


def setup():
	"""The incentive amount on Salary Structure Assignment and the incentive component in
	Payroll Settings; run after every migrate."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Salary Structure Assignment": [
				{
					"fieldname": INCENTIVE_FIELD,
					"label": "مبلغ الحافز الشهري",
					"fieldtype": "Currency",
					"options": "currency",
					"insert_after": "variable",
					"description": "يُصرف منه كل شهر بنسبة النتيجة النهائية لتقييم الموظف.",
					"module": "Custom Hrms",
				}
			],
			"Payroll Settings": [
				{
					"fieldname": COMPONENT_FIELD,
					"label": "مكون راتب الحوافز",
					"fieldtype": "Link",
					"options": "Salary Component",
					"insert_after": "payroll_based_on",
					"description": "المكون الذي يُصرف عليه حافز تقييم الموظفين.",
					"module": "Custom Hrms",
				}
			],
		}
	)

	if frappe.db.get_single_value("Payroll Settings", COMPONENT_FIELD):
		return
	if not frappe.db.exists("Salary Component", "حوافز"):
		frappe.get_doc(
			{
				"doctype": "Salary Component",
				"salary_component": "حوافز",
				"salary_component_abbr": "INCV",
				"type": "Earning",
				"description": "حافز تقييم الموظفين الشهري",
			}
		).insert(ignore_permissions=True)
	frappe.db.set_single_value("Payroll Settings", COMPONENT_FIELD, "حوافز")
