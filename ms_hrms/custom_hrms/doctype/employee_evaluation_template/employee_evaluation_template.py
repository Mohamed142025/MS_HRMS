"""The items an employee is evaluated on, in parts the template defines: each part has a
weight and is scored either by the employee's manager or by HR. The incentive slabs set the
share of the incentive paid for each range of the final score.

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
		self.validate_incentive_slabs()
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

	def validate_incentive_slabs(self):
		"""The slabs run from 0 to 100 with no gap or overlap, in order."""
		if not self.incentive_slabs:
			frappe.throw(_("حدد شرائح الحافز: نسبة الصرف لكل مدى من النتيجة النهائية."))
		self.incentive_slabs.sort(key=lambda row: (flt(row.from_score), flt(row.to_score)))
		expected = 0
		for idx, row in enumerate(self.incentive_slabs, start=1):
			row.idx = idx
			start, end = flt(row.from_score, 2), flt(row.to_score, 2)
			if start != expected:
				frappe.throw(
					_("شرائح الحافز يجب أن تكون متصلة: الشريحة {0} تبدأ من {1} والمتوقع {2}.").format(
						idx, f"{start:g}", f"{expected:g}"
					)
				)
			if end <= start:
				frappe.throw(_("الشريحة {0}: «إلى درجة» يجب أن تكون أكبر من «من درجة».").format(idx))
			if not 0 <= flt(row.incentive_percent) <= 100:
				frappe.throw(_("الشريحة {0}: نسبة الصرف يجب أن تكون بين 0 و 100.").format(idx))
			expected = end
		if expected != 100:
			frappe.throw(_("آخر شريحة حافز يجب أن تنتهي عند 100، وهي تنتهي عند {0}.").format(f"{expected:g}"))

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


def get_incentive_percent(score, slabs):
	"""The share of the incentive paid for this final score: a slab takes its lower bound,
	so a score on the edge of two slabs falls in the upper one, and the last takes 100."""
	score = flt(score, 2)
	for row in slabs:
		if flt(row.from_score) <= score < flt(row.to_score) or (row is slabs[-1] and score == flt(row.to_score)):
			return flt(row.incentive_percent)
	return 0


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
