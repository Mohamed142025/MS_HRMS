# Copyright (c) 2026, Mohamed Sayed and Contributors
# See license.txt

# import frappe
from frappe.tests import IntegrationTestCase


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestOvertimePolicy(IntegrationTestCase):
	"""
	Integration tests for OvertimePolicy.
	Use this class for testing interactions between multiple components.
	"""

	pass
