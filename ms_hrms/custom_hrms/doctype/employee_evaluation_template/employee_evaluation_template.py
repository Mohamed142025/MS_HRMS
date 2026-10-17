"""The items an employee is evaluated on, in parts the template defines: each part has a
weight and is scored either by the employee's manager or by HR.

An evaluation takes the template of the employee's designation, else of their department,
else the default template."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class EmployeeEvaluationTemplate(Document):
	def validate(self):
		self.validate_parts()
		self.validate_items()
		self.validate_unique_scope()

	def validate_parts(self):
		names = [(row.part_name or "").strip() for row in self.parts]
		for row, name in zip(self.parts, names):
			row.part_name = name
			if names.count(name) > 1:
				frappe.throw(_("الجزء {0} مكرر.").format(frappe.bold(name)))
			if flt(row.weight) <= 0:
				frappe.throw(_("وزن الجزء {0} يجب أن يكون أكبر من صفر.").format(frappe.bold(name)))
		total = flt(sum(flt(row.weight) for row in self.parts), 2)
		if total != 100:
			frappe.throw(_("مجموع أوزان الأجزاء يجب أن يكون 100%، وهو الآن {0}%.").format(total))

	def validate_items(self):
		parts = [row.part_name for row in self.parts]
		seen = set()
		for row in self.items:
			row.part = (row.part or "").strip()
			if row.part not in parts:
				frappe.throw(
					_("الصف {0}: الجزء {1} ليس من أجزاء القالب.").format(row.idx, frappe.bold(row.part))
				)
			if (row.part, row.kra) in seen:
				frappe.throw(_("البند {0} مكرر في جزء {1}.").format(frappe.bold(row.kra), row.part))
			seen.add((row.part, row.kra))

		for part in parts:
			rows = [row for row in self.items if row.part == part]
			if not rows:
				frappe.throw(_("الجزء {0} ليس له بنود.").format(frappe.bold(part)))
			total = flt(sum(flt(row.weight) for row in rows), 2)
			if total != 100:
				frappe.throw(
					_("مجموع أوزان بنود جزء {0} يجب أن يكون 100%، وهو الآن {1}%.").format(frappe.bold(part), total)
				)

	def validate_unique_scope(self):
		if self.disabled:
			return
		active = {"disabled": 0, "name": ("!=", self.name)}
		checks = [
			(self.is_default, {"is_default": 1}, _("يوجد قالب افتراضي آخر: {0}")),
			(self.designation, {"designation": self.designation}, _("يوجد قالب آخر لنفس المسمى الوظيفي: {0}")),
			(
				self.department and not self.designation,
				{"department": self.department, "designation": ("is", "not set")},
				_("يوجد قالب آخر لنفس القسم: {0}"),
			),
		]
		for applies, filters, message in checks:
			other = applies and frappe.db.get_value("Employee Evaluation Template", {**active, **filters})
			if other:
				frappe.throw(message.format(frappe.bold(other)))


def get_template_for(employee):
	"""The active template for this employee: of their designation, else their department,
	else the default one."""
	designation, department = frappe.db.get_value("Employee", employee, ["designation", "department"])
	for filters in (
		designation and {"designation": designation},
		department and {"department": department, "designation": ("is", "not set")},
		{"is_default": 1},
	):
		name = filters and frappe.db.get_value("Employee Evaluation Template", {"disabled": 0, **filters})
		if name:
			return name
