from frappe import _


def get_data():
	"""Connections: the checkins each import made (Employee Checkin.custom_biometric_import)."""
	return {
		"fieldname": "custom_biometric_import",
		"transactions": [{"label": _("البصمات"), "items": ["Employee Checkin"]}],
	}
