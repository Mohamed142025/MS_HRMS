# Copyright (c) 2026, Mohamed Sayed and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document


class PermissionPolicy(Document):
    """
    Permission Policy controller.
    """

    def validate(self):
        """
        Validate Permission Policy configuration.
        """

        self.validate_scope()
        self.validate_limits()
        self.validate_duplicate_active_policy()

    def validate_limits(self):
        """Validate configured policy limits."""

        numeric_fields = (
            "max_permissions_per_day",
            "max_hours_per_day",
            "max_permissions_per_month",
            "max_hours_per_month",
        )

        for fieldname in numeric_fields:
            if float(self.get(fieldname) or 0) < 0:
                frappe.throw(
                    _("{0} cannot be negative.").format(
                        frappe.bold(frappe.unscrub(fieldname))
                    ),
                    title=_("Invalid Policy Limit"),
                )

        minimum = self.duration_to_seconds(
            self.get("min_permission_duration")
        )
        maximum = self.duration_to_seconds(
            self.get("max_permission_duration")
        )

        if minimum < 0 or maximum < 0:
            frappe.throw(
                _("Permission duration limits cannot be negative."),
                title=_("Invalid Duration Limits"),
            )

        if minimum and maximum and minimum > maximum:
            frappe.throw(
                _(
                    "Minimum Permission Duration cannot exceed "
                    "Maximum Permission Duration."
                ),
                title=_("Invalid Duration Limits"),
            )

    @staticmethod
    def duration_to_seconds(value):
        """Convert a Duration value to seconds."""

        if value is None or value == "":
            return 0.0

        try:
            return float(value)
        except (TypeError, ValueError):
            pass

        value = str(value).strip().lower()

        if ":" in value:
            parts = value.split(":")
            try:
                if len(parts) == 3:
                    hours, minutes, seconds = map(float, parts)
                    return hours * 3600 + minutes * 60 + seconds
                if len(parts) == 2:
                    minutes, seconds = map(float, parts)
                    return minutes * 60 + seconds
            except ValueError:
                pass

        matches = re.findall(
            r"([0-9]+(?:\.[0-9]+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)",
            value,
        )

        if matches:
            units = {
                "h": 3600, "hr": 3600, "hrs": 3600,
                "hour": 3600, "hours": 3600,
                "m": 60, "min": 60, "mins": 60,
                "minute": 60, "minutes": 60,
                "s": 1, "sec": 1, "secs": 1,
                "second": 1, "seconds": 1,
            }
            return sum(float(amount) * units[unit] for amount, unit in matches)

        frappe.throw(
            _("Unable to understand Duration value: {0}.").format(
                frappe.bold(value)
            ),
            title=_("Invalid Duration Value"),
        )

    # =========================================================================
    # Scope Validation
    # =========================================================================

    def validate_scope(self):
        """
        Validate the selected Permission Policy scope.

        Only the field related to `applies_to` can contain a value.
        """

        scope_fields = {
            "Department": "department",
            "Designation": "designation",
            "Employee Grade": "employee_grade",
            "Employee": "employee",
        }

        selected_field = scope_fields.get(self.applies_to)

        if self.applies_to == "All Employees":
            self._clear_unused_scope_fields()
            return

        if not selected_field:
            frappe.throw(
                _(
                    "Invalid Applies To value: {0}"
                ).format(
                    frappe.bold(self.applies_to)
                ),
                title=_("Invalid Policy Scope"),
            )

        if not self.get(selected_field):
            frappe.throw(
                _(
                    "{0} is required when Applies To is {1}."
                ).format(
                    frappe.bold(frappe.unscrub(selected_field)),
                    frappe.bold(self.applies_to),
                ),
                title=_("Missing Policy Scope"),
            )

        self._clear_unused_scope_fields(selected_field)

    # =========================================================================
    # Duplicate Active Policy
    # =========================================================================

    def validate_duplicate_active_policy(self):
        """
        Prevent more than one active Permission Policy
        for the same Company and Scope.
        """

        if not self.is_active:
            return

        filters = {
            "company": self.company,
            "applies_to": self.applies_to,
            "is_active": 1,
            "name": ["!=", self.name],
        }

        scope_fields = {
            "Department": "department",
            "Designation": "designation",
            "Employee Grade": "employee_grade",
            "Employee": "employee",
        }

        if self.applies_to in scope_fields:
            fieldname = scope_fields[self.applies_to]
            filters[fieldname] = self.get(fieldname)

        existing_policy = frappe.db.exists(
            "Permission Policy",
            filters,
        )

        if not existing_policy:
            return

        existing_policy_name = frappe.db.get_value(
            "Permission Policy",
            existing_policy,
            "policy_name",
        )

        frappe.throw(
            _(
                "An active Permission Policy already exists for "
                "{0}. Existing Policy: {1}"
            ).format(
                frappe.bold(self.applies_to),
                frappe.bold(
                    existing_policy_name or existing_policy
                ),
            ),
            title=_("Duplicate Active Policy"),
        )

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _clear_unused_scope_fields(self, selected_field=None):
        """
        Clear scope fields that are not applicable to the selected scope.
        """

        scope_fields = [
            "department",
            "designation",
            "employee_grade",
            "employee",
        ]

        for fieldname in scope_fields:
            if fieldname != selected_field and self.get(fieldname):
                self.set(fieldname, None)


# =============================================================================
# Policy Resolver
# =============================================================================

def get_applicable_policy(employee, company=None):
    """
    Resolve the most specific active Permission Policy for an Employee.

    Resolution order:

        Employee
        ↓
        Designation
        ↓
        Employee Grade
        ↓
        Department
        ↓
        All Employees

    Employee Grade is resolved only when the Employee DocType
    actually contains an employee_grade field.
    """

    if not employee:
        return None

    employee_meta = frappe.get_meta("Employee")

    employee_fields = [
        "name",
        "company",
        "department",
        "designation",
    ]

    has_employee_grade = bool(
        employee_meta.get_field("employee_grade")
    )

    if has_employee_grade:
        employee_fields.append("employee_grade")

    employee_data = frappe.db.get_value(
        "Employee",
        employee,
        employee_fields,
        as_dict=True,
    )

    if not employee_data:
        frappe.throw(
            _("Employee {0} does not exist.").format(
                frappe.bold(employee)
            ),
            title=_("Employee Not Found"),
        )

    company = company or employee_data.company

    # =========================================================================
    # 1. Employee
    # =========================================================================

    policy = _get_policy(
        applies_to="Employee",
        target_field="employee",
        target_value=employee_data.name,
        company=company,
    )

    if policy:
        return policy

    # =========================================================================
    # 2. Designation
    # =========================================================================

    if employee_data.designation:
        policy = _get_policy(
            applies_to="Designation",
            target_field="designation",
            target_value=employee_data.designation,
            company=company,
        )

        if policy:
            return policy

    # =========================================================================
    # 3. Employee Grade
    # =========================================================================

    if (
        has_employee_grade
        and employee_data.get("employee_grade")
    ):
        policy = _get_policy(
            applies_to="Employee Grade",
            target_field="employee_grade",
            target_value=employee_data.employee_grade,
            company=company,
        )

        if policy:
            return policy

    # =========================================================================
    # 4. Department
    # =========================================================================

    if employee_data.department:
        policy = _get_policy(
            applies_to="Department",
            target_field="department",
            target_value=employee_data.department,
            company=company,
        )

        if policy:
            return policy

    # =========================================================================
    # 5. All Employees
    # =========================================================================

    return _get_policy(
        applies_to="All Employees",
        company=company,
    )


def _get_policy(
    applies_to,
    target_field=None,
    target_value=None,
    company=None,
):
    """
    Return the active Permission Policy matching the requested scope.
    """

    filters = {
        "is_active": 1,
        "applies_to": applies_to,
    }

    if company:
        filters["company"] = company

    if target_field and target_value:
        filters[target_field] = target_value

    policies = frappe.get_all(
        "Permission Policy",
        filters=filters,
        fields=[
            "name",
            "policy_name",
            "is_active",
            "company",
            "applies_to",
            "department",
            "designation",
            "employee_grade",
            "employee",
            "max_permissions_per_day",
            "max_hours_per_day",
            "max_permissions_per_month",
            "max_hours_per_month",
            "min_permission_duration",
            "max_permission_duration",
        ],
        order_by="modified desc, name asc",
        limit_page_length=1,
    )

    return policies[0] if policies else None