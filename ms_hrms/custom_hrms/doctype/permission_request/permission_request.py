# Copyright (c) 2026, Mohamed Sayed and contributors
# For license information, please see license.txt

import re

import frappe

from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, time_diff_in_seconds

from ms_hrms.custom_hrms.doctype.permission_policy.permission_policy import (
    get_applicable_policy,
)


# =============================================================================
# Constants
# =============================================================================

COUNTED_STATUSES = (
    "Pending Approval",
    "Approved",
)

IGNORED_OVERLAP_STATUSES = (
    "Rejected",
    "Cancelled",
)


# =============================================================================
# Permission Request
# =============================================================================

class PermissionRequest(Document):
    """
    Permission Request Controller.

    Business Rules
    --------------

    Employee
    --------
    Normal users:
        Automatically use the Employee linked to their User.

    HR Manager / System Manager / Administrator:
        Can create requests for any active Employee.

    Status
    ------
    New Request:
        Draft

    Valid transitions:

        Draft -> Pending Approval

        Pending Approval -> Approved
        Pending Approval -> Rejected
        Pending Approval -> Cancelled

        Approved -> Cancelled

    Only Department Approvers can change the status.

    Permission Policy
    -----------------
    Policy is resolved using:

        Employee
        Designation
        Employee Grade
        Department
        All Employees

    Duration Limits
    ---------------
    Minimum and Maximum Permission Duration are ALWAYS validated
    before Save.

    This means they apply even when the request is still Draft.

    Example:

        Minimum = 15m
        Maximum = 2h

    A request of:

        10m -> Rejected
        15m -> Allowed
        30m -> Allowed
        2h  -> Allowed
        2h 1m -> Rejected

    Daily / Monthly Limits
    ----------------------
    These rules are checked only for:

        Pending Approval
        Approved

    Time Conflict
    -------------
    Draft requests are included.

    Pending Approval and Approved requests are included.

    Rejected and Cancelled requests are ignored.

    Boundary touching is allowed.

    Employee Checkin
    ----------------
    Late Arrival:
        IN at from_time

    Early Leave:
        OUT at to_time

    During Working Hours:
        OUT at from_time
        IN at to_time

    Cancellation
    ------------
    When a Permission Request becomes Cancelled,
    all Employee Checkins explicitly linked to this
    Permission Request are deleted.
    """

    # =========================================================================
    # Document Lifecycle
    # =========================================================================

    def before_validate(self):
        """
        Prepare the document before validation.
        """

        # ---------------------------------------------------------------------
        # New Permission Requests must enter the approval flow immediately.
        # ---------------------------------------------------------------------

        if self.is_new():
            self.status = "Pending Approval"

        # ---------------------------------------------------------------------
        # Normal users automatically use their linked Employee.
        #
        # HR Manager / System Manager / Administrator can select
        # another Employee.
        # ---------------------------------------------------------------------

        if not self.can_create_request_for_other_employee():
            self.set_employee_from_current_user()

        # ---------------------------------------------------------------------
        # Always refresh Employee related information.
        # ---------------------------------------------------------------------

        if self.employee:
            self.set_employee_details()

    def validate(self):
        """
        Execute all Permission Request validations.

        IMPORTANT:
            Everything inside this method happens BEFORE Save.
        """

        # =====================================================================
        # Basic Validation
        # =====================================================================

        self.validate_employee()
        self.validate_permission_date()
        self.validate_time_range()

        # =====================================================================
        # Calculate Duration
        # =====================================================================

        self.calculate_duration()

        # =====================================================================
        # Status
        # =====================================================================

        self.validate_status_transition()

        # =====================================================================
        # Resolve Permission Policy
        # =====================================================================

        self.resolve_permission_policy()

        # =====================================================================
        # IMPORTANT
        #
        # Duration Policy MUST be checked BEFORE Save.
        #
        # This applies to Draft as well.
        # =====================================================================

        self.validate_policy_duration_limits()

        # =====================================================================
        # Time Overlap
        # =====================================================================

        self.validate_permission_overlap()

        # =====================================================================
        # Daily / Monthly Policy Limits
        #
        # Only Pending Approval / Approved consume limits.
        # =====================================================================

        self.validate_policy_usage_limits()

    def on_update(self):
        """
        Execute post-save business actions.

        Approved:
            Create Employee Checkins.

        Cancelled:
            Delete Employee Checkins created by this Permission Request.
        """

        # ---------------------------------------------------------------------
        # Approved
        # ---------------------------------------------------------------------

        if self.has_been_approved():
            self.create_employee_checkins()

        # ---------------------------------------------------------------------
        # Cancelled
        # ---------------------------------------------------------------------

        if self.has_been_cancelled():
            self.delete_employee_checkins()

    def on_cancel(self):
        """
        Keep the custom status field aligned with Frappe document cancellation.
        """

        self.status = "Cancelled"

        if self.meta.has_field("approval_date"):
            self.approval_date = None

        self.db_update()
        self.delete_employee_checkins()

    # =========================================================================
    # Employee Resolution
    # =========================================================================

    def set_employee_from_current_user(self):
        """
        Resolve the active Employee linked to the current User.
        """

        current_user = frappe.session.user

        if not current_user or current_user == "Guest":
            frappe.throw(
                _("You must be logged in with a valid User account."),
                title=_("Authentication Required"),
            )

        employee = frappe.db.get_value(
            "Employee",
            {
                "user_id": current_user,
                "status": "Active",
            },
            "name",
        )

        if not employee:
            frappe.throw(
                _(
                    "No active Employee is linked to the current User "
                    "account: {0}."
                ).format(
                    frappe.bold(current_user)
                ),
                title=_("Employee Not Found"),
            )

        self.employee = employee

    def set_employee_details(self):
        """
        Always derive Employee information from Employee master.
        """

        employee_data = frappe.db.get_value(
            "Employee",
            self.employee,
            [
                "employee_name",
                "department",
                "designation",
            ],
            as_dict=True,
        )

        if not employee_data:
            frappe.throw(
                _("Employee {0} does not exist.").format(
                    frappe.bold(self.employee)
                ),
                title=_("Invalid Employee"),
            )

        self.employee_name = employee_data.employee_name
        self.department = employee_data.department
        self.designation = employee_data.designation

    def validate_employee(self):
        """
        Validate Employee selection server-side.

        Normal users:
            Only their own Employee.

        HR Manager / System Manager / Administrator:
            Can create requests for other Employees.
        """

        if not self.employee:
            frappe.throw(
                _("Employee is required."),
                title=_("Missing Employee"),
            )

        if self.can_create_request_for_other_employee():
            return

        current_user = frappe.session.user

        employee_user = frappe.db.get_value(
            "Employee",
            self.employee,
            "user_id",
        )

        if employee_user != current_user:
            frappe.throw(
                _(
                    "You are not allowed to create a Permission Request "
                    "for another Employee."
                ),
                title=_("Permission Denied"),
            )

    def can_create_request_for_other_employee(self):
        """
        Determine whether the current User can select another Employee.
        """

        current_user = frappe.session.user

        if current_user == "Administrator":
            return True

        roles = frappe.get_roles(current_user)

        return bool(
            "System Manager" in roles
            or "HR Manager" in roles
        )

    # =========================================================================
    # Permission Date
    # =========================================================================

    def validate_permission_date(self):
        """
        Validate Permission Date.
        """

        if not self.permission_date:
            frappe.throw(
                _("Permission Date is required."),
                title=_("Missing Permission Date"),
            )

    # =========================================================================
    # Time Validation
    # =========================================================================

    def validate_time_range(self):
        """
        Ensure From Time is strictly earlier than To Time.
        """

        if not self.from_time or not self.to_time:
            frappe.throw(
                _("From Time and To Time are required."),
                title=_("Missing Permission Time"),
            )

        duration_seconds = time_diff_in_seconds(
            f"2000-01-01 {self.to_time}",
            f"2000-01-01 {self.from_time}",
        )

        if duration_seconds <= 0:
            frappe.throw(
                _("From Time must be earlier than To Time."),
                title=_("Invalid Time Range"),
            )

    def calculate_duration(self):
        """
        Calculate Permission Request duration in seconds.
        """

        duration_seconds = time_diff_in_seconds(
            f"2000-01-01 {self.to_time}",
            f"2000-01-01 {self.from_time}",
        )

        if duration_seconds <= 0:
            frappe.throw(
                _("Permission duration must be greater than zero."),
                title=_("Invalid Duration"),
            )

        self.duration = duration_seconds

    # =========================================================================
    # Status Engine
    # =========================================================================

    def validate_status_transition(self):
        """
        Validate Permission Request status transitions.
        """

        # ---------------------------------------------------------------------
        # New document must always be Draft.
        # ---------------------------------------------------------------------

        if self.is_new():
            self.status = "Pending Approval"
            return

        previous_status = (
            self.get_db_value("status")
            or "Draft"
        )

        current_status = (
            self.status
            or "Draft"
        )

        # ---------------------------------------------------------------------
        # Normalize status values.
        # ---------------------------------------------------------------------

        previous_status = str(previous_status).strip()
        current_status = str(current_status).strip()

        # ---------------------------------------------------------------------
        # Always save normalized status.
        # ---------------------------------------------------------------------

        self.status = current_status

        if current_status == "Draft":
            frappe.throw(
                _(
                    "Permission Request cannot be saved as Draft. "
                    "It must be submitted for approval."
                ),
                title=_("Draft Not Allowed"),
            )

        # ---------------------------------------------------------------------
        # Nothing changed.
        # ---------------------------------------------------------------------

        if current_status == previous_status:
            return

        # ---------------------------------------------------------------------
        # Only Department Approvers can change status.
        # ---------------------------------------------------------------------

        if not self.is_department_approver():
            frappe.throw(
                _(
                    "Only the Department Approver can change the "
                    "Permission Request status."
                ),
                title=_("Approval Permission Denied"),
            )

        allowed_transitions = {

            "Draft": {
                "Pending Approval",
            },

            "Pending Approval": {
                "Approved",
                "Rejected",
                "Cancelled",
            },

            "Approved": {
                "Cancelled",
            },

            "Rejected": set(),

            "Cancelled": set(),
        }

        allowed_statuses = allowed_transitions.get(
            previous_status,
            set(),
        )

        if current_status not in allowed_statuses:
            frappe.throw(
                _(
                    "Invalid status transition: {0} → {1}."
                ).format(
                    frappe.bold(previous_status),
                    frappe.bold(current_status),
                ),
                title=_("Invalid Status Transition"),
            )

        if current_status == "Approved":
            self.approval_date = now_datetime()
        elif previous_status == "Approved":
            self.approval_date = None

    def is_department_approver(self):
        """
        Check whether current User is configured as an approver
        for the Employee's Department.
        """

        current_user = frappe.session.user

        if not current_user or current_user == "Guest":
            return False

        if not self.employee:
            return False

        department = frappe.db.get_value(
            "Employee",
            self.employee,
            "department",
        )

        if not department:
            return False

        approver_exists = frappe.db.sql(
            """
            SELECT
                dpa.name

            FROM `tabDepartment Approver` AS dpa

            INNER JOIN `tabDepartment` AS department
                ON department.name = dpa.parent

            WHERE
                dpa.parenttype = 'Department'
                AND dpa.parentfield = 'custom_permission_approver'
                AND department.name = %(department)s
                AND dpa.approver = %(user)s

            LIMIT 1
            """,
            {
                "department": department,
                "user": current_user,
            },
            as_dict=True,
        )

        return bool(approver_exists)

    # =========================================================================
    # Permission Policy Resolver
    # =========================================================================

    def resolve_permission_policy(self):
        """
        Resolve the applicable Permission Policy.
        """

        company = frappe.db.get_value(
            "Employee",
            self.employee,
            "company",
        )

        if not company:
            frappe.throw(
                _(
                    "Employee {0} is not linked to a Company."
                ).format(
                    frappe.bold(self.employee)
                ),
                title=_("Company Not Found"),
            )

        policy = get_applicable_policy(
            employee=self.employee,
            company=company,
        )

        if not policy:
            frappe.throw(
                _(
                    "No active Permission Policy was found for Employee "
                    "{0}."
                ).format(
                    frappe.bold(self.employee)
                ),
                title=_("Permission Policy Not Found"),
            )

        self.permission_policy = policy.name

    # =========================================================================
    # Duration Parser
    # =========================================================================

    @staticmethod
    def duration_to_seconds(value):
        """
        Convert a Frappe Duration value to seconds.

        Supported examples:

            900
            900.0
            "900"
            "15m"
            "2h"
            "1h 30m"
            "1h 30m 20s"
            "00:15:00"

        Frappe Duration fields are normally stored as seconds,
        but this helper also safely handles human-readable values.
        """

        if value is None:
            return 0.0

        # ---------------------------------------------------------------------
        # Numeric value
        # ---------------------------------------------------------------------

        if isinstance(value, (int, float)):
            return float(value)

        value = str(value).strip()

        if not value:
            return 0.0

        # ---------------------------------------------------------------------
        # Plain numeric string
        #
        # Example:
        #
        # "900"
        # ---------------------------------------------------------------------

        try:
            return float(value)
        except (TypeError, ValueError):
            pass

        # ---------------------------------------------------------------------
        # HH:MM:SS
        #
        # Example:
        #
        # 00:15:00
        # 02:00:00
        # ---------------------------------------------------------------------

        if ":" in value:

            parts = value.split(":")

            try:

                if len(parts) == 3:

                    hours = float(parts[0])
                    minutes = float(parts[1])
                    seconds = float(parts[2])

                    return (
                        hours * 3600
                        + minutes * 60
                        + seconds
                    )

                if len(parts) == 2:

                    minutes = float(parts[0])
                    seconds = float(parts[1])

                    return (
                        minutes * 60
                        + seconds
                    )

            except (TypeError, ValueError):
                pass

        # ---------------------------------------------------------------------
        # Human readable Duration
        #
        # Examples:
        #
        # 15m
        # 2h
        # 1h 30m
        # 1h 30m 20s
        # ---------------------------------------------------------------------

        normalized = value.lower()

        pattern = re.compile(
            r"([0-9]+(?:\.[0-9]+)?)\s*"
            r"(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)"
        )

        matches = pattern.findall(normalized)

        if matches:

            total_seconds = 0.0

            for amount, unit in matches:

                amount = float(amount)

                if unit in (
                    "h",
                    "hr",
                    "hrs",
                    "hour",
                    "hours",
                ):
                    total_seconds += amount * 3600

                elif unit in (
                    "m",
                    "min",
                    "mins",
                    "minute",
                    "minutes",
                ):
                    total_seconds += amount * 60

                elif unit in (
                    "s",
                    "sec",
                    "secs",
                    "second",
                    "seconds",
                ):
                    total_seconds += amount

            return total_seconds

        # ---------------------------------------------------------------------
        # Unknown value
        # ---------------------------------------------------------------------

        frappe.throw(
            _(
                "Unable to understand Permission Duration value: {0}."
            ).format(
                frappe.bold(value)
            ),
            title=_("Invalid Duration Value"),
        )

    # =========================================================================
    # Policy Duration Validation
    # =========================================================================

    def validate_policy_duration_limits(self):
        """
        Validate Minimum / Maximum Permission Duration.

        IMPORTANT:

        This validation happens BEFORE Save.

        It applies to ALL statuses, including:

            Draft
            Pending Approval
            Approved

        Example:

            Policy Minimum = 15m

            Requested = 10m

            Result:
                Save is blocked.
        """

        if not self.permission_policy:
            return

        policy = frappe.get_doc(
            "Permission Policy",
            self.permission_policy,
        )

        requested_seconds = self.duration_to_seconds(
            self.duration
        )

        # =====================================================================
        # Minimum Duration
        # =====================================================================

        minimum_duration = self.duration_to_seconds(
            policy.min_permission_duration
        )

        if minimum_duration > 0:

            if requested_seconds < minimum_duration:

                frappe.throw(
                    _(
                        "Permission Request cannot be saved because "
                        "the requested duration is below the minimum "
                        "allowed duration.<br><br>"
                        "<b>Minimum allowed:</b> {0}<br>"
                        "<b>Requested duration:</b> {1}"
                    ).format(
                        frappe.bold(
                            self.format_duration(
                                minimum_duration
                            )
                        ),
                        frappe.bold(
                            self.format_duration(
                                requested_seconds
                            )
                        ),
                    ),
                    title=_("Minimum Permission Duration"),
                )

        # =====================================================================
        # Maximum Duration
        # =====================================================================

        maximum_duration = self.duration_to_seconds(
            policy.max_permission_duration
        )

        if maximum_duration > 0:

            if requested_seconds > maximum_duration:

                frappe.throw(
                    _(
                        "Permission Request cannot be saved because "
                        "the requested duration exceeds the maximum "
                        "allowed duration.<br><br>"
                        "<b>Maximum allowed:</b> {0}<br>"
                        "<b>Requested duration:</b> {1}"
                    ).format(
                        frappe.bold(
                            self.format_duration(
                                maximum_duration
                            )
                        ),
                        frappe.bold(
                            self.format_duration(
                                requested_seconds
                            )
                        ),
                    ),
                    title=_("Maximum Permission Duration"),
                )

    # =========================================================================
    # Policy Usage Validation
    # =========================================================================

    def validate_policy_usage_limits(self):
        """
        Enforce Daily / Monthly Permission Policy limits.

        Only:

            Pending Approval
            Approved

        consume daily/monthly limits.
        """

        current_status = str(
            self.status or "Draft"
        ).strip()

        if current_status not in COUNTED_STATUSES:
            return

        if not self.permission_policy:
            return

        policy = frappe.get_doc(
            "Permission Policy",
            self.permission_policy,
        )

        self.validate_daily_permission_limit(policy)

        self.validate_daily_hours_limit(policy)

        self.validate_monthly_permission_limit(policy)

        self.validate_monthly_hours_limit(policy)

    # =========================================================================
    # Daily / Monthly Policy Limits
    # =========================================================================

    def validate_daily_permission_limit(self, policy):
        """
        Validate maximum Permission Requests per day.
        """

        maximum_permissions = policy.max_permissions_per_day

        if not maximum_permissions:
            return

        current_count = self.get_daily_permission_count()

        if current_count >= maximum_permissions:
            frappe.throw(
                _(
                    "The employee has already reached the maximum "
                    "of {0} Permission Requests allowed per day."
                ).format(
                    frappe.bold(maximum_permissions)
                ),
                title=_("Daily Permission Limit"),
            )

    def validate_daily_hours_limit(self, policy):
        """
        Validate maximum Permission hours per day.
        """

        maximum_hours = policy.max_hours_per_day

        if not maximum_hours:
            return

        used_seconds = self.get_daily_permission_seconds()

        requested_seconds = self.duration_to_seconds(
            self.duration
        )

        maximum_seconds = (
            float(maximum_hours) * 3600
        )

        if used_seconds + requested_seconds > maximum_seconds:

            frappe.throw(
                _(
                    "The employee cannot exceed {0} permission hours "
                    "per day.<br><br>"
                    "<b>Existing permission hours:</b> {1}<br>"
                    "<b>Requested duration:</b> {2}"
                ).format(
                    frappe.bold(
                        self.format_hours(
                            maximum_hours
                        )
                    ),
                    frappe.bold(
                        self.format_seconds_as_hours(
                            used_seconds
                        )
                    ),
                    frappe.bold(
                        self.format_seconds_as_hours(
                            requested_seconds
                        )
                    ),
                ),
                title=_("Daily Permission Hours Limit"),
            )

    def validate_monthly_permission_limit(self, policy):
        """
        Validate maximum Permission Requests per month.
        """

        maximum_permissions = (
            policy.max_permissions_per_month
        )

        if not maximum_permissions:
            return

        current_count = (
            self.get_monthly_permission_count()
        )

        if current_count >= maximum_permissions:

            frappe.throw(
                _(
                    "The employee has already reached the maximum "
                    "of {0} Permission Requests allowed per month."
                ).format(
                    frappe.bold(maximum_permissions)
                ),
                title=_("Monthly Permission Limit"),
            )

    def validate_monthly_hours_limit(self, policy):
        """
        Validate maximum Permission hours per month.
        """

        maximum_hours = (
            policy.max_hours_per_month
        )

        if not maximum_hours:
            return

        used_seconds = (
            self.get_monthly_permission_seconds()
        )

        requested_seconds = self.duration_to_seconds(
            self.duration
        )

        maximum_seconds = (
            float(maximum_hours) * 3600
        )

        if used_seconds + requested_seconds > maximum_seconds:

            frappe.throw(
                _(
                    "The employee cannot exceed {0} permission hours "
                    "per month.<br><br>"
                    "<b>Existing permission hours:</b> {1}<br>"
                    "<b>Requested duration:</b> {2}"
                ).format(
                    frappe.bold(
                        self.format_hours(
                            maximum_hours
                        )
                    ),
                    frappe.bold(
                        self.format_seconds_as_hours(
                            used_seconds
                        )
                    ),
                    frappe.bold(
                        self.format_seconds_as_hours(
                            requested_seconds
                        )
                    ),
                ),
                title=_("Monthly Permission Hours Limit"),
            )

    # =========================================================================
    # Permission Overlap
    # =========================================================================

    def validate_permission_overlap(self):
        """
        Prevent overlapping Permission Requests.

        Included:

            Draft
            Pending Approval
            Approved

        Ignored:

            Rejected
            Cancelled

        Boundary touching is allowed.
        """

        current_status = str(
            self.status or "Draft"
        ).strip()

        # ---------------------------------------------------------------------
        # Current request itself is Cancelled / Rejected.
        # ---------------------------------------------------------------------

        if current_status in IGNORED_OVERLAP_STATUSES:
            return

        if not self.employee:
            return

        if not self.permission_date:
            return

        if not self.from_time or not self.to_time:
            return

        # ---------------------------------------------------------------------
        # Search for overlapping request.
        #
        # Existing From < Current To
        #
        # AND
        #
        # Existing To > Current From
        #
        # Boundary touching is allowed.
        # ---------------------------------------------------------------------

        overlapping_request = frappe.db.sql(
            """
            SELECT
                name,
                from_time,
                to_time,
                status

            FROM `tabPermission Request`

            WHERE
                employee = %(employee)s

                AND permission_date = %(permission_date)s

                AND name != %(name)s

                AND TRIM(
                    COALESCE(status, 'Draft')
                ) NOT IN (
                    'Rejected',
                    'Cancelled'
                )

                AND from_time < %(to_time)s

                AND to_time > %(from_time)s

            ORDER BY
                from_time ASC

            LIMIT 1
            """,
            {
                "employee": self.employee,
                "permission_date": self.permission_date,
                "name": self.name or "",
                "from_time": self.from_time,
                "to_time": self.to_time,
            },
            as_dict=True,
        )

        if not overlapping_request:
            return

        existing = overlapping_request[0]

        existing_status = str(
            existing.status or "Draft"
        ).strip()

        # ---------------------------------------------------------------------
        # Second safety check.
        # ---------------------------------------------------------------------

        if existing_status in IGNORED_OVERLAP_STATUSES:
            return

        frappe.throw(
            _(
                "This Permission Request overlaps with an existing "
                "Permission Request ({0}) for the same Employee on "
                "{1} from {2} to {3}."
            ).format(
                frappe.bold(existing.name),
                frappe.bold(self.permission_date),
                frappe.bold(existing.from_time),
                frappe.bold(existing.to_time),
            ),
            title=_("Permission Time Conflict"),
        )

    # =========================================================================
    # Policy Query Helpers
    # =========================================================================

    def get_daily_permission_count(self):
        """
        Return number of counted Permission Requests for the day.
        """

        result = frappe.db.sql(
            """
            SELECT COUNT(name)

            FROM `tabPermission Request`

            WHERE
                employee = %(employee)s

                AND permission_date = %(permission_date)s

                AND TRIM(
                    COALESCE(status, 'Draft')
                ) IN (
                    'Pending Approval',
                    'Approved'
                )

                AND name != %(name)s
            """,
            {
                "employee": self.employee,
                "permission_date": self.permission_date,
                "name": self.name or "",
            },
        )

        return int(
            result[0][0] or 0
        )

    def get_daily_permission_seconds(self):
        """
        Return total Permission duration in seconds for the day.
        """

        result = frappe.db.sql(
            """
            SELECT COALESCE(
                SUM(duration),
                0
            )

            FROM `tabPermission Request`

            WHERE
                employee = %(employee)s

                AND permission_date = %(permission_date)s

                AND TRIM(
                    COALESCE(status, 'Draft')
                ) IN (
                    'Pending Approval',
                    'Approved'
                )

                AND name != %(name)s
            """,
            {
                "employee": self.employee,
                "permission_date": self.permission_date,
                "name": self.name or "",
            },
        )

        return float(
            result[0][0] or 0
        )

    def get_monthly_permission_count(self):
        """
        Return number of counted Permission Requests for the month.
        """

        result = frappe.db.sql(
            """
            SELECT COUNT(name)

            FROM `tabPermission Request`

            WHERE
                employee = %(employee)s

                AND YEAR(permission_date)
                    = YEAR(%(permission_date)s)

                AND MONTH(permission_date)
                    = MONTH(%(permission_date)s)

                AND TRIM(
                    COALESCE(status, 'Draft')
                ) IN (
                    'Pending Approval',
                    'Approved'
                )

                AND name != %(name)s
            """,
            {
                "employee": self.employee,
                "permission_date": self.permission_date,
                "name": self.name or "",
            },
        )

        return int(
            result[0][0] or 0
        )

    def get_monthly_permission_seconds(self):
        """
        Return total Permission duration in seconds for the month.
        """

        result = frappe.db.sql(
            """
            SELECT COALESCE(
                SUM(duration),
                0
            )

            FROM `tabPermission Request`

            WHERE
                employee = %(employee)s

                AND YEAR(permission_date)
                    = YEAR(%(permission_date)s)

                AND MONTH(permission_date)
                    = MONTH(%(permission_date)s)

                AND TRIM(
                    COALESCE(status, 'Draft')
                ) IN (
                    'Pending Approval',
                    'Approved'
                )

                AND name != %(name)s
            """,
            {
                "employee": self.employee,
                "permission_date": self.permission_date,
                "name": self.name or "",
            },
        )

        return float(
            result[0][0] or 0
        )

    # =========================================================================
    # Formatting Helpers
    # =========================================================================

    @staticmethod
    def format_duration(seconds):
        """
        Format seconds as human-readable duration.
        """

        seconds = int(
            float(seconds or 0)
        )

        hours, remainder = divmod(
            seconds,
            3600,
        )

        minutes, _ = divmod(
            remainder,
            60,
        )

        if hours and minutes:
            return _(
                "{0} hours {1} minutes"
            ).format(
                hours,
                minutes,
            )

        if hours:
            return _(
                "{0} hours"
            ).format(
                hours,
            )

        return _(
            "{0} minutes"
        ).format(
            minutes,
        )

    @staticmethod
    def format_seconds_as_hours(seconds):
        """
        Format seconds as decimal hours.
        """

        hours = float(
            seconds or 0
        ) / 3600

        return _(
            "{0:.2f} hours"
        ).format(
            hours,
        )

    @staticmethod
    def format_hours(hours):
        """
        Format configured policy hours.
        """

        return _(
            "{0:.2f} hours"
        ).format(
            float(hours),
        )

    # =========================================================================
    # Approval Detection
    # =========================================================================

    def has_been_approved(self):
        """
        Return True only when the document transitions into Approved.
        """

        current_status = str(
            self.status or ""
        ).strip()

        if current_status != "Approved":
            return False

        previous_doc = self.get_doc_before_save()

        if not previous_doc:
            return True

        previous_status = str(
            previous_doc.status or ""
        ).strip()

        return previous_status != "Approved"

    def has_been_cancelled(self):
        """
        Return True only when the document transitions into Cancelled.
        """

        current_status = str(
            self.status or ""
        ).strip()

        if current_status != "Cancelled":
            return False

        previous_doc = self.get_doc_before_save()

        if not previous_doc:
            return False

        previous_status = str(
            previous_doc.status or ""
        ).strip()

        return previous_status != "Cancelled"

    # =========================================================================
    # Employee Checkin
    # =========================================================================

    def create_employee_checkins(self):
        """
        Create Employee Checkin records according to Permission Type.
        """

        if not self.employee:
            frappe.throw(
                _(
                    "Cannot create Employee Checkin without an Employee."
                ),
                title=_("Missing Employee"),
            )

        checkins = self.get_required_checkins()

        for checkin_data in checkins:

            self.create_employee_checkin(
                log_type=checkin_data["log_type"],
                checkin_time=checkin_data["time"],
            )

    def get_required_checkins(self):
        """
        Build Employee Checkin records required by Permission Type.
        """

        if self.permission_type == "Late Arrival":

            return [
                {
                    "log_type": "IN",
                    "time": self.get_permission_datetime(
                        self.from_time
                    ),
                }
            ]

        if self.permission_type == "Early Leave":

            return [
                {
                    "log_type": "OUT",
                    "time": self.get_permission_datetime(
                        self.to_time
                    ),
                }
            ]

        if self.permission_type == "During Working Hours":

            return [
                {
                    "log_type": "OUT",
                    "time": self.get_permission_datetime(
                        self.from_time
                    ),
                },
                {
                    "log_type": "IN",
                    "time": self.get_permission_datetime(
                        self.to_time
                    ),
                },
            ]

        frappe.throw(
            _(
                "Unsupported Permission Type: {0}."
            ).format(
                frappe.bold(
                    self.permission_type
                )
            ),
            title=_("Invalid Permission Type"),
        )

    def get_permission_datetime(self, permission_time):
        """
        Combine Permission Date and Permission Time.
        """

        if not self.permission_date:
            frappe.throw(
                _("Permission Date is required."),
                title=_("Missing Permission Date"),
            )

        if not permission_time:
            frappe.throw(
                _("Permission time is required."),
                title=_("Missing Permission Time"),
            )

        return (
            f"{self.permission_date} "
            f"{permission_time}"
        )

    def create_employee_checkin(
        self,
        log_type,
        checkin_time,
    ):
        """
        Create one Employee Checkin.

        custom_permission_request is used for idempotency.
        """

        checkin_meta = frappe.get_meta("Employee Checkin")
        checkin_filters = {
            "employee": self.employee,
            "log_type": log_type,
            "time": checkin_time,
        }

        if checkin_meta.has_field("custom_permission_request"):
            checkin_filters["custom_permission_request"] = self.name

        existing_checkin = frappe.db.exists(
            "Employee Checkin",
            checkin_filters,
        )

        if existing_checkin:
            return existing_checkin

        checkin_data = {
            "doctype": "Employee Checkin",
            "employee": self.employee,
            "log_type": log_type,
            "time": checkin_time,
            "skip_auto_attendance": 0,
        }

        if checkin_meta.has_field("custom_permission_request"):
            checkin_data["custom_permission_request"] = self.name

        checkin = frappe.get_doc(checkin_data)

        checkin.insert(
            ignore_permissions=True,
            ignore_mandatory=False,
        )

        return checkin.name

    def delete_employee_checkins(self):
        """
        Delete all Employee Checkin records created by this
        Permission Request.

        Only Checkins explicitly linked to this
        Permission Request are deleted.
        """

        if not frappe.get_meta("Employee Checkin").has_field(
            "custom_permission_request"
        ):
            return

        checkin_names = frappe.get_all(
            "Employee Checkin",
            filters={
                "custom_permission_request": self.name,
            },
            pluck="name",
        )

        if not checkin_names:
            return

        for checkin_name in checkin_names:

            frappe.delete_doc(
                "Employee Checkin",
                checkin_name,
                ignore_permissions=True,
                force=True,
            )


# =============================================================================
# API
# =============================================================================

@frappe.whitelist()
def get_current_user_employee():
    """
    Return the active Employee linked to the current User.
    """

    current_user = frappe.session.user

    if not current_user or current_user == "Guest":
        frappe.throw(
            _("You must be logged in with a valid User account."),
            title=_("Authentication Required"),
        )

    employee = frappe.db.get_value(
        "Employee",
        {
            "user_id": current_user,
            "status": "Active",
        },
        [
            "name",
            "employee_name",
            "department",
            "designation",
        ],
        as_dict=True,
    )

    if not employee:
        frappe.throw(
            _(
                "No active Employee is linked to User {0}."
            ).format(
                frappe.bold(current_user)
            ),
            title=_("Employee Not Found"),
        )

    return employee


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_employee_query(
    doctype,
    txt,
    searchfield,
    start,
    page_len,
    filters=None,
):
    """
    Employee Link query for Permission Request.

    Normal User:
        Only own Employee.

    HR Manager / System Manager / Administrator:
        Any active Employee.
    """

    current_user = frappe.session.user

    if not current_user or current_user == "Guest":
        return []

    roles = frappe.get_roles(current_user)

    is_admin = current_user == "Administrator"

    is_system_manager = (
        "System Manager" in roles
    )

    is_hr_manager = (
        "HR Manager" in roles
    )

    # =========================================================================
    # HR Manager / System Manager / Administrator
    # =========================================================================

    if (
        is_admin
        or is_system_manager
        or is_hr_manager
    ):

        search_text = f"%{txt}%"

        return frappe.db.sql(
            """
            SELECT
                name,
                employee_name

            FROM `tabEmployee`

            WHERE
                status = 'Active'

                AND (
                    name LIKE %(txt)s
                    OR employee_name LIKE %(txt)s
                )

            ORDER BY employee_name

            LIMIT %(start)s, %(page_len)s
            """,
            {
                "txt": search_text,
                "start": start,
                "page_len": page_len,
            },
        )

    # =========================================================================
    # Normal User
    # =========================================================================

    employee = frappe.db.get_value(
        "Employee",
        {
            "user_id": current_user,
            "status": "Active",
        },
        [
            "name",
            "employee_name",
        ],
        as_dict=True,
    )

    if not employee:
        return []

    search_text = f"%{txt}%"

    return frappe.db.sql(
        """
        SELECT
            name,
            employee_name

        FROM `tabEmployee`

        WHERE
            name = %(employee)s

            AND (
                name LIKE %(txt)s
                OR employee_name LIKE %(txt)s
            )

        ORDER BY employee_name

        LIMIT %(start)s, %(page_len)s
        """,
        {
            "employee": employee.name,
            "txt": search_text,
            "start": start,
            "page_len": page_len,
        },
    )