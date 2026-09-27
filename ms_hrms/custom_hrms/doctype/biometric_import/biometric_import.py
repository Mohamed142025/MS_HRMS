# Copyright (c) 2026, Mohamed Sayed and contributors
# For license information, please see license.txt

"""An upload of the biometric device's sheet. The work is in
ms_hrms.custom_hrms.services.biometric_import; the import itself runs in the background."""

import frappe
from frappe import _
from frappe.model.document import Document

from ms_hrms.custom_hrms.services import biometric_import as service

JOB = "ms_hrms.custom_hrms.doctype.biometric_import.biometric_import.run_job"


class BiometricImport(Document):
	def validate(self):
		if self.is_new() or self.has_value_changed("import_file") or self.has_value_changed("date_order"):
			if self.status not in (service.DRAFT, None, ""):
				frappe.throw(_("الملف ده اترفع خلاص. لرفع شيت تاني اعمل استيراد جديد."))

	def on_trash(self):
		if self.status != service.DRAFT:
			frappe.throw(_("الاستيراد اترفع، فما يتمسحش. البصمات اللي اترفعت مربوطة بيه."))

	@frappe.whitelist()
	def get_preview(self):
		self.check_permission("write")
		return service.preview(self)

	@frappe.whitelist()
	def start_import(self, correct_absences=0):
		self._check_can_import(correct_absences)
		if self.status != service.DRAFT:
			frappe.throw(_("الملف ده اترفع خلاص."))
		return self._enqueue("run", correct_absences)

	@frappe.whitelist()
	def get_retry_preview(self):
		self.check_permission("write")
		return service.retry_preview(self)

	@frappe.whitelist()
	def retry_pending(self, correct_absences=0):
		self._check_can_import(correct_absences)
		if self.status != service.WAITING:
			frappe.throw(_("مفيش بصمات مستنية."))
		return self._enqueue("retry", correct_absences)

	@frappe.whitelist()
	def ignore_codes(self, codes):
		self.check_permission("write")
		service.ignore_codes(self, frappe.parse_json(codes) if isinstance(codes, str) else codes)
		self.save()
		return self.status

	def _check_can_import(self, correct_absences):
		self.check_permission("write")
		if not frappe.has_permission("Employee Checkin", "create"):
			frappe.throw(_("محتاج صلاحية إنشاء Employee Checkin."), frappe.PermissionError)
		if frappe.utils.cint(correct_absences) and not frappe.has_permission("Attendance", "cancel"):
			frappe.throw(_("تصحيح الغياب محتاج صلاحية إلغاء Attendance."), frappe.PermissionError)

	def _enqueue(self, mode, correct_absences):
		previous = self.status
		self.db_set("status", service.RUNNING, notify=True)
		frappe.enqueue(
			JOB,
			queue="long",
			timeout=3600,
			enqueue_after_commit=True,
			job_id=f"biometric_import::{self.name}",
			deduplicate=True,
			name=self.name,
			mode=mode,
			previous=previous,
			correct_absences=frappe.utils.cint(correct_absences),
		)
		return service.RUNNING


def run_job(name, mode, previous, correct_absences=0):
	doc = frappe.get_doc("Biometric Import", name)
	try:
		doc.status = previous
		(service.run if mode == "run" else service.retry)(doc, bool(correct_absences))
		doc.flags.ignore_validate = True
		doc.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep: a background job
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Biometric Import {name}")
		frappe.db.set_value("Biometric Import", name, "status", previous)
		frappe.db.commit()  # nosemgrep
		frappe.publish_realtime("biometric_import_done", {"name": name, "error": 1}, user=frappe.session.user)
		return
	frappe.publish_realtime("biometric_import_done", {"name": name}, user=frappe.session.user)
