from types import SimpleNamespace

from frappe.tests.utils import FrappeTestCase

from ms_hrms.custom_hrms.services.attendance_penalty import (
	calculate_deduction_amount,
	get_period_start,
	match_rule,
)


class TestAttendancePenalty(FrappeTestCase):
	def test_salary_deduction_amounts(self):
		policy = SimpleNamespace(salary_divisor=30, working_hours_per_day=8)
		self.assertEqual(calculate_deduction_amount("No Deduction", 1, 12000, policy), 0)
		self.assertEqual(calculate_deduction_amount("Minutes", 60, 12000, policy), 50)
		self.assertEqual(calculate_deduction_amount("Hour", 1, 12000, policy), 50)
		self.assertEqual(calculate_deduction_amount("Quarter Day", 1, 12000, policy), 100)
		self.assertEqual(calculate_deduction_amount("Half Day", 1, 12000, policy), 200)
		self.assertEqual(calculate_deduction_amount("Full Day", 1, 12000, policy), 400)

	def test_reset_period_start(self):
		self.assertEqual(str(get_period_start("2026-09-15", "Monthly")), "2026-09-01")
		self.assertEqual(str(get_period_start("2026-09-15", "Quarterly")), "2026-07-01")
		self.assertEqual(str(get_period_start("2026-09-15", "Yearly")), "2026-01-01")
		self.assertEqual(str(get_period_start("2026-09-15", "Never")), "1900-01-01")

	def test_rule_matching_prefers_tightest_limit(self):
		policy = SimpleNamespace(
			entry_rules=[
				SimpleNamespace(enabled=1, occurrence_number=1, max_late_minutes=0, deduction_type="Hour", deduction_value=1),
				SimpleNamespace(enabled=1, occurrence_number=1, max_late_minutes=30, deduction_type="No Deduction", deduction_value=0),
			]
		)
		rule = match_rule(policy, "Late Entry", 1, 20)
		self.assertEqual(rule.deduction_type, "No Deduction")
		self.assertIsNone(match_rule(policy, "Late Entry", 2, 20))
