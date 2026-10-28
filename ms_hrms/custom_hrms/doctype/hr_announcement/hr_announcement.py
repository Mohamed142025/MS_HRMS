"""An announcement from HR, sent to the employee app (and its push notifications) to every
active employee with a user, or those of one department, when it is submitted."""

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class HRAnnouncement(Document):
	def on_submit(self):
		from ms_hrms.app_notifications import send_announcement

		self.db_set({"recipients": send_announcement(self), "sent_on": now_datetime()})
