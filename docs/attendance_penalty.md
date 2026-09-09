# Attendance Late and Early Exit Policy

## 1. Scope

This feature lives entirely in the `ms_hrms` custom app. It does not modify Frappe or ERPNext core files.

It supports two independent penalty streams:

- `Late Entry`: employee checks in after the shift start.
- `Early Exit`: employee checks out before the shift end.

Each stream has its own grace period, occurrence counter, rules, and deduction amount.

## 2. Installation and activation

The app must be installed on the site together with HRMS:

```bash
bench --site gesc install-app hrms
bench --site gesc install-app ms_hrms --force
bench --site gesc migrate
bench build --app ms_hrms
bench --site gesc clear-cache
```

Verify the installation:

```bash
bench --site gesc list-apps
bench --site gesc execute "frappe.get_all('DocType', filters={'module':'Custom Hrms'}, fields=['name','istable'])"
```

The app hook loads the client script for `Attendance Penalty Processing` from:

```text
ms_hrms/custom_hrms/doctype/attendance_penalty_processing/attendance_penalty_processing.js
```

## 3. DocTypes

### Attendance Penalty Policy

Master configuration for a penalty policy.

Important fields:

- `policy_name`: unique policy name.
- `enabled`: policy availability.
- `apply_on`: `All Employees`, `Department`, or `Employee`.
- `department` / `employee`: scope value when selected.
- `reset_period`: `Monthly`, `Quarterly`, `Yearly`, or `Never`.
- `entry_grace_period`: allowed minutes after shift start.
- `exit_grace_period`: allowed minutes before shift end.
- `allowed_grace_occurrences`: shared number of grace events per employee and Payroll Period. `0` means unlimited.
- `deduction_based_on`: `Basic Salary`, `Gross Salary`, or `Salary Component`.
- `salary_component`: Salary Basis Component, required when salary basis is `Salary Component`.
- `deduction_salary_component`: the separate Salary Component used by generated Additional Salary.
- `salary_divisor`: default `30`.
- `working_hours_per_day`: default `8`.
- `entry_rules`: child table of entry rules.
- `exit_rules`: child table of exit rules.

The controller validates required scope fields, positive salary settings, duplicate occurrence numbers, and duplicate enabled policy scopes.

### Attendance Penalty Rule

Child table used by both `entry_rules` and `exit_rules`.

Fields:

- `occurrence_number`: employee occurrence number, starting at 1.
- `max_late_minutes`: maximum counted minutes accepted by this rule. `0` means no maximum.
- `deduction_type`: `No Deduction`, `Minutes`, `Hour`, `Quarter Day`, `Half Day`, or `Full Day`.
- `deduction_value`: multiplier or number of minutes/hours, depending on deduction type.
- `enabled`: whether the rule participates in matching.

If no enabled rule matches an occurrence, the detail is marked `Review Required` and submission is blocked.

### Attendance Penalty Processing

Operational document used by HR.

Header fields:

- `posting_date`
- `payroll_period`: required Payroll Period; its `start_date` and `end_date` define the calculation window.
- `from_date`, `to_date`
- `apply_on`, `department`, `employee`
- optional `policy` override
- `status`: `Draft`, `Calculated`, `Submitted`, or `Cancelled`
- entry, exit, and grand totals
- links to generated Additional Salary documents

The `Get Attendance` button calculates details but does not create payroll deductions.

### Attendance Penalty Detail

Audit line for one employee and one penalty event.

It stores the employee, Attendance link, date, shift window, check-in/check-out, penalty type, actual minutes, grace, counted minutes, occurrence number, matched rule, amount, policy, review flag, processing link, and remarks.

## 4. Policy priority

When no policy is explicitly selected on Processing, the service searches in this order:

1. Employee policy.
2. Department policy.
3. All Employees policy.

Only enabled policies are considered. The Policy controller rejects more than one enabled policy for the same scope.

When HR selects a policy explicitly on Processing, that policy is used after checking that it is enabled.

## 5. Grace period and counters

### Late Entry

```text
actual_late_minutes = max(0, checkin_time - shift_start)
```

If `actual_late_minutes <= entry_grace_period`:

- `counted_minutes = 0`
- `occurrence_number = 0`
- deduction is zero
- the event is not counted

The event consumes one of `allowed_grace_occurrences` when that field is greater than zero. Once the allowance is exhausted, another event inside the minute grace is processed as a real occurrence with `counted_minutes = 0`.

Otherwise:

```text
counted_minutes = actual_late_minutes - entry_grace_period
occurrence_number = previous submitted late entries in the reset period + 1
```

### Early Exit

```text
actual_early_exit_minutes = max(0, shift_end - checkout_time)
```

If `actual_early_exit_minutes <= exit_grace_period`, the event is ignored for counting and deduction.

The same shared grace-occurrence allowance is used for Early Exit; Late Entry and Early Exit consume the same allowance within the selected Payroll Period.

Otherwise, only the Early Exit counter is incremented. Late Entry and Early Exit counters never share occurrences.

### Payroll Period reset

The occurrence counter is shared by Late Entry and Early Exit and resets at the selected Payroll Period. Processing dates are taken from that Payroll Period, so an Early Exit after a counted Late Entry is not treated as occurrence 1.

The policy `reset_period` remains available as a legacy fallback for older data without a Payroll Period. New Processing documents must select a Payroll Period.

Only submitted Processing details are counted as previous occurrences.

## 6. Rule matching

The engine matches:

1. penalty type rule list;
2. occurrence number;
3. maximum counted minutes, where `0` means unlimited.

When multiple rules match, the tightest non-zero maximum is selected. If nothing matches, the detail is flagged for HR review and cannot be submitted until resolved.

This handles the first-late special case without guessing. For example, a first late up to 30 counted minutes can use a `No Deduction` rule, while a first late above 30 minutes becomes `Review Required` unless another matching rule is configured.

## 7. Salary calculation

The service obtains the salary basis from the latest submitted Salary Slip overlapping the processing period. If no matching slip exists, Basic Salary falls back to the latest submitted Salary Structure Assignment.

The selected basis is:

- `Basic Salary`: Salary Slip `base`, or Assignment `base` as fallback.
- `Gross Salary`: Salary Slip `gross_pay`.
- `Salary Component`: the matching earning row on the Salary Slip.

The formulas are:

```text
Daily Rate  = Salary Basis / Salary Divisor
Hourly Rate = Daily Rate / Working Hours Per Day
Minutes     = Hourly Rate * Deduction Value / 60
Hour        = Hourly Rate * Deduction Value
Quarter Day = Daily Rate / 4 * Deduction Value, default multiplier 1
Half Day    = Daily Rate / 2 * Deduction Value, default multiplier 1
Full Day    = Daily Rate * Deduction Value, default multiplier 1
```

With salary `12,000`, divisor `30`, and 8 hours:

```text
Daily Rate  = 400
Hourly Rate = 50
Quarter Day = 100
Half Day    = 200
Full Day    = 400
```

## 8. Processing workflow

1. Create and enable an Attendance Penalty Policy.
2. Add Entry Rules and Exit Rules.
3. Create Attendance Penalty Processing.
4. Select dates and employee scope.
5. Optionally select a specific policy.
6. Click `Get Attendance`.
7. Review every generated detail and totals.
8. Resolve every `Review Required` row.
9. Submit the Processing document.
10. The app creates one submitted Additional Salary per employee with a positive total.
11. Standard ERPNext payroll reads Additional Salary while creating Salary Slips.

No Additional Salary is created while Processing is Draft or Calculated.

## 9. Additional Salary and duplicates

The app creates or reuses the Salary Component named `Late Attendance Deduction` as a deduction component.

Each generated Additional Salary contains:

- employee
- company
- salary component
- amount
- payroll date
- reference to `Attendance Penalty Processing` when the standard reference fields exist

Before submission, Attendance links are checked against submitted Processing documents. The same Attendance cannot be processed twice.

On cancellation, submitted Additional Salary documents created by the Processing document are cancelled.

## 10. Source data

The current implementation reads submitted/available `Attendance` rows for the selected date range and uses `Employee Checkin` entries to fill missing `in_time` or `out_time` values for an existing Attendance row.

Shift start and end are taken from the Attendance shift, then the employee default shift. Overnight shifts are supported when the end time is earlier than or equal to the start time.

## 11. Code map

```text
custom_hrms/doctype/attendance_penalty_policy/
  attendance_penalty_policy.json   DocType schema
  attendance_penalty_policy.py     validation and duplicate scope checks

custom_hrms/doctype/attendance_penalty_rule/
  attendance_penalty_rule.json     child rule schema

custom_hrms/doctype/attendance_penalty_detail/
  attendance_penalty_detail.json   processing child row schema

custom_hrms/doctype/attendance_penalty_processing/
  attendance_penalty_processing.json  operational schema
  attendance_penalty_processing.py    lifecycle and payroll integration
  attendance_penalty_processing.js    Get Attendance client action

custom_hrms/services/attendance_penalty.py
  policy selection, reset periods, attendance loading,
  grace/counter logic, rule matching, salary calculations,
  and Salary Component creation
```

## 12. Validation commands

```bash
python3 -m compileall -q apps/ms_hrms/ms_hrms/custom_hrms
node --check apps/ms_hrms/ms_hrms/custom_hrms/doctype/attendance_penalty_processing/attendance_penalty_processing.js
bench --site gesc migrate
bench --site gesc clear-cache
bench build --app ms_hrms
```

The focused test module is:

```text
ms_hrms.custom_hrms.services.test_attendance_penalty
```

If `bench run-tests` reports that tests are disabled, enable them only on a development site:

```bash
bench --site gesc set-config allow_tests true
```

## 13. Important operational notes

- The feature is implemented in `ms_hrms`; no ERPNext/Frappe core file is changed.
- HR users need `HR Manager` permission for the two parent DocTypes.
- Processing must be reviewed before submission.
- A zero-value event remains visible in details when it is outside the grace period but has `No Deduction`, which preserves the audit trail.
- A policy without a matching rule never receives an automatic guessed deduction.
