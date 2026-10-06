from types import SimpleNamespace

from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from ms_hrms.custom_hrms.services.attendance_penalty import (
	calculate_deduction_amount,
	calculate_penalty,
	get_period_start,
	match_rule,
	tier_minutes,
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

	def test_minutes_multiplier_amount(self):
		policy = SimpleNamespace(salary_divisor=30, working_hours_per_day=8)
		# 12,000 / 30 / 8 = 50 an hour: 60 minutes × 4 = 4 hours = 200.
		self.assertEqual(calculate_deduction_amount("Minutes × Multiplier", 4, 12000, policy, 60), 200)
		self.assertEqual(calculate_deduction_amount("Minutes × Multiplier", 2, 12000, policy, 20), flt(50 * 40 / 60, 2))

	def test_tiers_from_shift_start_for_every_occurrence(self):
		def tiers():
			return [
				SimpleNamespace(enabled=1, occurrence_number=0, max_late_minutes=31, deduction_type="Minutes × Multiplier", deduction_value=2),
				SimpleNamespace(enabled=1, occurrence_number=0, max_late_minutes=45, deduction_type="Minutes × Multiplier", deduction_value=3),
				SimpleNamespace(enabled=1, occurrence_number=0, max_late_minutes=120, deduction_type="Minutes × Multiplier", deduction_value=4),
				SimpleNamespace(enabled=1, occurrence_number=0, max_late_minutes=0, deduction_type="Full Day", deduction_value=1),
			]

		policy = SimpleNamespace(
			name="test", entry_grace_period=15, exit_grace_period=5, tiers_from_shift_start=1,
			salary_divisor=30, working_hours_per_day=8, entry_rules=tiers(), exit_rules=tiers(),
		)
		cases = {
			("Late Entry", 10): ("No Deduction", 0),
			("Late Entry", 16): ("Minutes × Multiplier", 2),
			("Late Entry", 31): ("Minutes × Multiplier", 2),
			("Late Entry", 32): ("Minutes × Multiplier", 3),
			("Late Entry", 45): ("Minutes × Multiplier", 3),
			("Late Entry", 46): ("Minutes × Multiplier", 4),
			("Late Entry", 120): ("Minutes × Multiplier", 4),
			("Late Entry", 121): ("Full Day", 1),
			("Early Exit", 5): ("No Deduction", 0),
			("Early Exit", 6): ("Minutes × Multiplier", 2),
			("Early Exit", 40): ("Minutes × Multiplier", 3),
		}
		for occurrence in (1, 2, 7):
			for (penalty_type, minutes), expected in cases.items():
				result = calculate_penalty(policy, None, penalty_type, minutes, None, None, occurrence)
				self.assertEqual((result["deduction_type"], result["deduction_value"]), expected, (penalty_type, minutes, occurrence))
				if result["deduction_type"] == "Minutes × Multiplier":
					# The multiplier counts the whole lateness from the shift start.
					self.assertEqual(tier_minutes(policy, result["actual_minutes"], result["counted_minutes"]), minutes)

	def test_exact_occurrence_before_every_occurrence(self):
		policy = SimpleNamespace(
			entry_rules=[
				SimpleNamespace(enabled=1, occurrence_number=0, max_late_minutes=0, deduction_type="Hour", deduction_value=1),
				SimpleNamespace(enabled=1, occurrence_number=3, max_late_minutes=0, deduction_type="Full Day", deduction_value=1),
			]
		)
		self.assertEqual(match_rule(policy, "Late Entry", 3, 20).deduction_type, "Full Day")
		self.assertEqual(match_rule(policy, "Late Entry", 4, 20).deduction_type, "Hour")

	def test_tiers_after_grace_unchanged_without_the_option(self):
		policy = SimpleNamespace(
			entry_grace_period=15,
			entry_rules=[SimpleNamespace(enabled=1, occurrence_number=1, max_late_minutes=30, deduction_type="Hour", deduction_value=1)],
		)
		# 40 minutes late is 25 after grace: within the 30-minute tier, as before.
		self.assertEqual(calculate_penalty(policy, None, "Late Entry", 40, None, None, 1)["deduction_type"], "Hour")
