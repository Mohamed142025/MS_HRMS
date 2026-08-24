import frappe

from datetime import datetime, timedelta
from math import ceil, floor

from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    add_days,
    flt,
    get_datetime,
    get_time,
    getdate,
    now_datetime,
)


class OvertimeCalculation(Document):

    def on_submit(self):

        additional_salaries = self.get_connected_additional_salaries()

        for salary in additional_salaries:

            if salary.docstatus == 0:
                frappe.get_doc(
                    "Additional Salary",
                    salary.name,
                ).submit()

    def on_cancel(self):

        additional_salaries = frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype": "Overtime Calculation",
                "ref_docname": self.name,
                "docstatus": ["!=", 2],
            },
            fields=["name", "docstatus"],
            limit_page_length=0,
        )

        submitted_salaries = [
            salary.name
            for salary in additional_salaries
            if salary.docstatus == 1
        ]

        if submitted_salaries:
            frappe.msgprint(
                _(
                    "The following Additional Salary records "
                    "will be cancelled: {0}"
                ).format(
                    frappe.bold(
                        ", ".join(submitted_salaries)
                    )
                ),
                title=_("Linked Documents Cancellation"),
                indicator="orange",
            )

        for salary in additional_salaries:

            if salary.docstatus == 1:
                additional_salary = frappe.get_doc(
                    "Additional Salary",
                    salary.name,
                )
                additional_salary.flags.ignore_links = True
                additional_salary.cancel()

    # =========================================================================
    # Constants
    # =========================================================================

    STATUS_DRAFT = "Draft"
    STATUS_CALCULATED = "Calculated"
    STATUS_PROCESSED = "Processed"
    STATUS_CANCELLED = "Cancelled"

    APPLY_ALL = "All Employees"
    APPLY_DEPARTMENT = "Department"
    APPLY_DESIGNATION = "Designation"
    APPLY_EMPLOYEE_GROUP = "Employee Group"
    APPLY_EMPLOYEE = "Employee"

    APPROVED_STATUS = "Approved"

    DETAIL_TABLE = "overtime_details"

    # =========================================================================
    # Validate
    # =========================================================================

    def validate(self):

        self.validate_company()
        self.validate_apply_to()
        self.validate_payroll_period()
        self.validate_period()
        self.validate_duplicate_calculation()
        self.validate_policy()
        self.validate_status()

        self.populate_policy_information()

        self.update_summary()

    # =========================================================================
    # Company
    # =========================================================================

    def validate_company(self):

        if not self.company:
            frappe.throw(
                _("Company is mandatory.")
            )

    # =========================================================================
    # Apply To
    # =========================================================================

    def validate_apply_to(self):

        if not self.apply_to:
            frappe.throw(
                _("Apply To is mandatory.")
            )

        allowed_values = {
            self.APPLY_ALL,
            self.APPLY_DEPARTMENT,
            self.APPLY_DESIGNATION,
            self.APPLY_EMPLOYEE_GROUP,
            self.APPLY_EMPLOYEE,
        }

        if self.apply_to not in allowed_values:
            frappe.throw(
                _("Invalid Apply To value: {0}").format(
                    frappe.bold(self.apply_to)
                )
            )

        field_mapping = {
            self.APPLY_DEPARTMENT: "department",
            self.APPLY_DESIGNATION: "designation",
            self.APPLY_EMPLOYEE_GROUP: "employee_group",
            self.APPLY_EMPLOYEE: "employee",
        }

        selected_field = field_mapping.get(
            self.apply_to
        )

        if selected_field and not self.get(selected_field):

            frappe.throw(
                _(
                    "{0} is mandatory when Apply To is {1}."
                ).format(
                    frappe.bold(
                        self.meta.get_label(selected_field)
                    ),
                    frappe.bold(self.apply_to),
                )
            )

    # =========================================================================
    # Payroll Period
    # =========================================================================

    def validate_payroll_period(self):

        if not self.payroll_period:

            frappe.throw(
                _("Payroll Period is mandatory.")
            )

        payroll_period = frappe.get_cached_doc(
            "Payroll Period",
            self.payroll_period,
        )

        if not payroll_period:

            frappe.throw(
                _(
                    "Payroll Period {0} was not found."
                ).format(
                    frappe.bold(self.payroll_period)
                )
            )

        # ---------------------------------------------------------------------
        # Company Validation
        # ---------------------------------------------------------------------

        if (
            payroll_period.company
            and payroll_period.company != self.company
        ):

            frappe.throw(
                _(
                    "Payroll Period {0} belongs to Company {1}, "
                    "not Company {2}."
                ).format(
                    frappe.bold(self.payroll_period),
                    frappe.bold(payroll_period.company),
                    frappe.bold(self.company),
                )
            )

        if not payroll_period.start_date:

            frappe.throw(
                _(
                    "Payroll Period {0} does not have a Start Date."
                ).format(
                    frappe.bold(self.payroll_period)
                )
            )

        if not payroll_period.end_date:

            frappe.throw(
                _(
                    "Payroll Period {0} does not have an End Date."
                ).format(
                    frappe.bold(self.payroll_period)
                )
            )

        payroll_from_date = getdate(
            payroll_period.start_date
        )

        payroll_to_date = getdate(
            payroll_period.end_date
        )

        if payroll_to_date < payroll_from_date:

            frappe.throw(
                _(
                    "Payroll Period {0} has an invalid date range."
                ).format(
                    frappe.bold(self.payroll_period)
                )
            )

        # ---------------------------------------------------------------------
        # Automatically Synchronize Dates
        # ---------------------------------------------------------------------

        self.from_date = payroll_from_date
        self.to_date = payroll_to_date

    # =========================================================================
    # Validate Duplicate Overtime Calculation
    # =========================================================================

    def validate_duplicate_calculation(self):

        if not self.payroll_period:
            return

        if not self.apply_to:
            return

        target_field_map = {
            self.APPLY_EMPLOYEE: "employee",
            self.APPLY_EMPLOYEE_GROUP: "employee_group",
            self.APPLY_DESIGNATION: "designation",
            self.APPLY_DEPARTMENT: "department",
        }

        target_field = target_field_map.get(
            self.apply_to
        )

        # ---------------------------------------------------------------------
        # All Employees
        # ---------------------------------------------------------------------

        if self.apply_to == self.APPLY_ALL:

            filters = {
                "company": self.company,
                "payroll_period": self.payroll_period,
                "apply_to": self.APPLY_ALL,
                "docstatus": ["!=", 2],
                "status": ["!=", self.STATUS_CANCELLED],
            }

            if not self.is_new():
                filters["name"] = ["!=", self.name]

            existing = frappe.get_all(
                "Overtime Calculation",
                filters=filters,
                fields=[
                    "name",
                    "status",
                    "payroll_period",
                ],
                order_by="creation desc",
                limit_page_length=1,
            )

            if existing:

                self.throw_duplicate_error(
                    existing[0]
                )

            return

        # ---------------------------------------------------------------------
        # Target Field
        # ---------------------------------------------------------------------

        if not target_field:
            return

        target_value = self.get(
            target_field
        )

        if not target_value:
            return

        filters = {
            "company": self.company,
            "payroll_period": self.payroll_period,
            "apply_to": self.apply_to,
            target_field: target_value,
            "docstatus": ["!=", 2],
            "status": ["!=", self.STATUS_CANCELLED],
        }

        # ---------------------------------------------------------------------
        # Exclude Current Document
        # ---------------------------------------------------------------------

        if not self.is_new():
            filters["name"] = [
                "!=",
                self.name,
            ]

        existing = frappe.get_all(
            "Overtime Calculation",
            filters=filters,
            fields=[
                "name",
                "status",
                "payroll_period",
                "apply_to",
                target_field,
            ],
            order_by="creation desc",
            limit_page_length=1,
        )

        if existing:

            self.throw_duplicate_error(
                existing[0]
            )

    # =========================================================================
    # Duplicate Error
    # =========================================================================

    def throw_duplicate_error(
        self,
        existing,
    ):

        target_field_map = {
            self.APPLY_EMPLOYEE: "employee",
            self.APPLY_EMPLOYEE_GROUP: "employee_group",
            self.APPLY_DESIGNATION: "designation",
            self.APPLY_DEPARTMENT: "department",
        }

        target_field = target_field_map.get(
            self.apply_to
        )

        target_value = None

        if target_field:
            target_value = self.get(
                target_field
            )

        target_label = (
            self.meta.get_label(target_field)
            if target_field
            else self.apply_to
        )

        message = _(
            "An Overtime Calculation already exists for "
            "Payroll Period {0} and {1} {2}.<br><br>"
            "Existing Overtime Calculation: {3}<br>"
            "Status: {4}"
        ).format(
            frappe.bold(self.payroll_period),
            frappe.bold(target_label),
            frappe.bold(target_value or self.apply_to),
            frappe.bold(existing.name),
            frappe.bold(existing.status),
        )

        frappe.throw(
            message,
            title=_(
                "Duplicate Overtime Calculation"
            ),
        )

    # =========================================================================
    # Period
    # =========================================================================

    def validate_period(self):

        if not self.from_date:

            frappe.throw(
                _("From Date is mandatory.")
            )

        if not self.to_date:

            frappe.throw(
                _("To Date is mandatory.")
            )

        from_date = getdate(
            self.from_date
        )

        to_date = getdate(
            self.to_date
        )

        if not from_date:

            frappe.throw(
                _("Invalid From Date.")
            )

        if not to_date:

            frappe.throw(
                _("Invalid To Date.")
            )

        if to_date < from_date:

            frappe.throw(
                _("To Date cannot be earlier than From Date.")
            )

        # ---------------------------------------------------------------------
        # Payroll Period Must Match Dates
        # ---------------------------------------------------------------------

        if self.payroll_period:

            payroll_period = frappe.get_cached_doc(
                "Payroll Period",
                self.payroll_period,
            )

            payroll_from = getdate(
                payroll_period.start_date
            )

            payroll_to = getdate(
                payroll_period.end_date
            )

            if (
                from_date != payroll_from
                or to_date != payroll_to
            ):

                frappe.throw(
                    _(
                        "From Date and To Date must match the selected "
                        "Payroll Period {0}: {1} to {2}."
                    ).format(
                        frappe.bold(
                            self.payroll_period
                        ),
                        frappe.bold(
                            payroll_from
                        ),
                        frappe.bold(
                            payroll_to
                        ),
                    )
                )

    # =========================================================================
    # Policy
    # =========================================================================

    def validate_policy(self):

        if not self.overtime_policy:

            frappe.throw(
                _("Overtime Policy is mandatory.")
            )

        policy = frappe.get_cached_doc(
            "Overtime Policy",
            self.overtime_policy,
        )

        if policy.company != self.company:

            frappe.throw(
                _(
                    "Overtime Policy {0} belongs to Company {1}, "
                    "not Company {2}."
                ).format(
                    frappe.bold(self.overtime_policy),
                    frappe.bold(policy.company),
                    frappe.bold(self.company),
                )
            )

        if policy.status != "Active":

            frappe.throw(
                _(
                    "Overtime Policy {0} is not Active."
                ).format(
                    frappe.bold(self.overtime_policy)
                )
            )

        calculation_from = getdate(
            self.from_date
        )

        calculation_to = getdate(
            self.to_date
        )

        policy_from = (
            getdate(policy.effective_from)
            if policy.effective_from
            else None
        )

        if (
            policy_from
            and calculation_from < policy_from
        ):

            frappe.throw(
                _(
                    "Calculation period starts on {0}, "
                    "but the selected Overtime Policy starts on {1}."
                ).format(
                    calculation_from,
                    policy_from,
                )
            )

        policy_to = (
            getdate(policy.effective_to)
            if policy.effective_to
            else None
        )

        if (
            policy_to
            and calculation_to > policy_to
        ):

            frappe.throw(
                _(
                    "Calculation period ends on {0}, "
                    "but the selected Overtime Policy ends on {1}."
                ).format(
                    calculation_to,
                    policy_to,
                )
            )

    # =========================================================================
    # Status
    # =========================================================================

    def validate_status(self):

        allowed_statuses = {
            self.STATUS_DRAFT,
            self.STATUS_CALCULATED,
            self.STATUS_PROCESSED,
            self.STATUS_CANCELLED,
        }

        if (
            self.status
            and self.status not in allowed_statuses
        ):

            frappe.throw(
                _("Invalid Overtime Calculation Status.")
            )

    # =========================================================================
    # Policy Information
    # =========================================================================

    def populate_policy_information(self):

        if not self.overtime_policy:
            return

        policy = frappe.get_cached_doc(
            "Overtime Policy",
            self.overtime_policy,
        )

        self.policy_status = (
            policy.status
        )

        self.calculation_basis = (
            policy.calculation_basis
        )

    # =========================================================================
    # Get Target Employees
    # =========================================================================

    def get_target_employees(self):

        filters = {
            "company": self.company,
            "status": "Active",
        }

        if self.apply_to == self.APPLY_DEPARTMENT:

            filters["department"] = (
                self.department
            )

        elif self.apply_to == self.APPLY_DESIGNATION:

            filters["designation"] = (
                self.designation
            )

        elif self.apply_to == self.APPLY_EMPLOYEE_GROUP:

            filters["employee_group"] = (
                self.employee_group
            )

        elif self.apply_to == self.APPLY_EMPLOYEE:

            filters["name"] = (
                self.employee
            )

        return frappe.get_all(
            "Employee",
            filters=filters,
            fields=[
                "name",
                "employee_name",
                "department",
                "designation",
                "employee_group",
                "company",
            ],
            order_by="name asc",
        )

    # =========================================================================
    # Collect Overtime Requests
    # =========================================================================

    def collect_overtime_requests(self):

        filters = {
            "status": self.APPROVED_STATUS,
            "overtime_date": [
                "between",
                [
                    self.from_date,
                    self.to_date,
                ],
            ],
            "company": self.company,
            "docstatus": ["!=", 2],
        }

        if self.apply_to == self.APPLY_EMPLOYEE:

            filters["employee"] = (
                self.employee
            )

        elif self.apply_to in {
            self.APPLY_DEPARTMENT,
            self.APPLY_DESIGNATION,
            self.APPLY_EMPLOYEE_GROUP,
        }:

            employees = (
                self.get_target_employees()
            )

            employee_names = [
                employee.name
                for employee in employees
            ]

            if not employee_names:
                return []

            filters["employee"] = [
                "in",
                employee_names,
            ]

        return frappe.get_all(
            "Overtime Request",
            filters=filters,
            fields=[
                "name",
                "employee",
                "employee_name",
                "department",
                "designation",
                "company",
                "overtime_date",
                "overtime_type",
                "from_time",
                "to_time",
                "requested_hours",
                "project",
                "cost_center",
            ],
            order_by="overtime_date asc, employee asc",
        )

    # =========================================================================
    # Calculate Actual Hours
    # =========================================================================

    @staticmethod
    def get_actual_check_out(employee, overtime_date):

        checkins = frappe.get_all(
            "Employee Checkin",
            filters={
                "employee": employee,
                "time": [
                    "between",
                    [
                        f"{overtime_date} 00:00:00",
                        f"{add_days(overtime_date, 1)} 23:59:59",
                    ],
                ],
                "log_type": "OUT",
            },
            fields=["time", "shift_start", "shift_end"],
            order_by="time desc",
            limit_page_length=20,
        )

        for checkin in checkins:

            if (
                checkin.shift_end
                and checkin.shift_start
                and getdate(checkin.shift_start) == getdate(overtime_date)
            ):
                return checkin

        return None

    @staticmethod
    def get_shift_end(employee, overtime_date):

        check_out = OvertimeCalculation.get_actual_check_out(
            employee,
            overtime_date,
        )

        if check_out:
            return get_datetime(check_out.shift_end)

        assignments = frappe.get_all(
            "Shift Assignment",
            filters={
                "employee": employee,
                "start_date": ["<=", overtime_date],
                "docstatus": 1,
            },
            or_filters=[
                ["end_date", ">=", overtime_date],
                ["end_date", "is", "not set"],
            ],
            fields=["shift_type"],
            order_by="start_date desc, creation desc",
            limit_page_length=1,
        )

        if assignments:
            shift = frappe.get_cached_doc(
                "Shift Type",
                assignments[0].shift_type,
            )
            shift_start = datetime.combine(
                getdate(overtime_date),
                get_time(shift.start_time),
            )
            shift_end = datetime.combine(
                getdate(overtime_date),
                get_time(shift.end_time),
            )
            if shift_end <= shift_start:
                shift_end += timedelta(days=1)
            return shift_end

        return None

    @classmethod
    def calculate_actual_hours(cls, request):

        if (
            not request.overtime_date
            or not request.from_time
            or not request.to_time
        ):
            return 0

        start = get_datetime(
            f"{request.overtime_date} {request.from_time}"
        )

        end = get_datetime(
            f"{request.overtime_date} {request.to_time}"
        )

        if not start or not end:
            return 0

        if end < start:
            end = add_days(
                end,
                1
            )

        check_out = cls.get_actual_check_out(
            request.employee,
            getdate(request.overtime_date),
        )

        if not check_out:
            return 0

        shift_end = cls.get_shift_end(
            request.employee,
            getdate(request.overtime_date),
        )

        if shift_end:
            actual_end = get_datetime(check_out.time)
            overtime_start = max(start, shift_end)
            overtime_end = min(actual_end, end)
            hours = max(
                (overtime_end - overtime_start).total_seconds() / 3600,
                0,
            )
        else:
            return 0

        return round(
            hours,
            2,
        )

    # =========================================================================
    # Calculate Request Amount
    # =========================================================================

    @staticmethod
    def apply_policy_limits_and_rounding(hours, policy):

        hours = max(flt(hours), 0)

        minimum = flt(policy.minimum_overtime)
        maximum = flt(policy.maximum_overtime)

        if minimum > 0 and hours < minimum:
            return 0

        if maximum > 0:
            hours = min(hours, maximum)

        if not policy.enable_rounding:
            return round(hours, 2)

        interval = flt(policy.rounding_interval)

        if interval <= 0:
            return round(hours, 2)

        units = hours / interval

        if policy.rounding_rule == "Round Up":
            units = ceil(units)
        elif policy.rounding_rule == "Round Down":
            units = floor(units)
        else:
            units = floor(units + 0.5)

        rounded_hours = round(units * interval, 2)

        if maximum > 0:
            rounded_hours = min(rounded_hours, maximum)

        return rounded_hours

    def calculate_request_amount(
        self,
        request,
        actual_hours,
    ):

        policy = frappe.get_cached_doc(
            "Overtime Policy",
            self.overtime_policy,
        )

        rules = []

        for rule in policy.overtime_policy_rule:

            if not rule.enabled:
                continue

            if (
                rule.overtime_type
                != request.overtime_type
            ):
                continue

            rules.append(rule)

        if not rules:

            frappe.throw(
                _(
                    "No active Overtime Policy Rule exists "
                    "for Overtime Type {0}."
                ).format(
                    frappe.bold(
                        request.overtime_type
                    )
                )
            )

        rules.sort(
            key=lambda row: flt(
                row.from_hour
            )
        )

        actual_hours = self.apply_policy_limits_and_rounding(
            actual_hours,
            policy,
        )

        if actual_hours <= 0:
            return 0, 0, 0, 0

        hourly_rate = self.get_hourly_rate(
            request.employee,
            policy,
        )

        total_calculated_hours = 0
        total_amount = 0
        weighted_multiplier = 0

        for rule in rules:

            from_hour = flt(
                rule.from_hour
            )

            to_hour = flt(
                rule.to_hour
            )

            multiplier = flt(
                rule.multiplier
            )

            if to_hour <= from_hour:
                continue

            applicable_from = max(
                0,
                from_hour,
            )

            applicable_to = min(
                actual_hours,
                to_hour,
            )

            if applicable_to <= applicable_from:
                continue

            hours = (
                applicable_to
                - applicable_from
            )

            total_calculated_hours += (
                hours
            )

            total_amount += (
                hours
                * hourly_rate
                * multiplier
            )

            weighted_multiplier += (
                hours
                * multiplier
            )

        representative_multiplier = 0

        if total_calculated_hours:

            representative_multiplier = (
                weighted_multiplier
                / total_calculated_hours
            )

        return (
            round(
                total_calculated_hours,
                2,
            ),
            round(
                total_amount,
                2,
            ),
            round(
                representative_multiplier,
                4,
            ),
            round(
                hourly_rate,
                2,
            ),
        )

    # =========================================================================
    # Hourly Rate
    # =========================================================================

    def get_hourly_rate(
        self,
        employee,
        policy,
    ):

        basis = (
            policy.calculation_basis
        )

        if basis == "Fixed Hourly Rate":

            rate = flt(
                policy.fixed_hourly_rate
            )

            if rate <= 0:

                frappe.throw(
                    _(
                        "Fixed Hourly Rate must be greater than zero."
                    )
                )

            return rate

        if basis == "Salary Component":

            component = (
                self.get_calculation_salary_component(
                    policy
                )
            )

            amount = (
                self.get_salary_component_amount(
                    employee,
                    component,
                )
            )

            return (
                self.convert_monthly_to_hourly(
                    amount
                )
            )

        salary = (
            self.get_employee_salary(
                employee,
                basis,
            )
        )

        return (
            self.convert_monthly_to_hourly(
                salary
            )
        )

    # =========================================================================
    # Calculation Salary Component
    # =========================================================================

    @staticmethod
    def get_calculation_salary_component(
        policy,
    ):

        component = getattr(
            policy,
            "calculation_salary_component",
            None,
        )

        if not component:

            component = getattr(
                policy,
                "salary_component",
                None,
            )

        if not component:

            frappe.throw(
                _(
                    "Calculation Salary Component is mandatory "
                    "when Calculation Basis is Salary Component."
                )
            )

        return component

    # =========================================================================
    # Salary Component Amount
    # =========================================================================

    def get_salary_component_amount(
        self,
        employee,
        component,
    ):

        assignment = frappe.db.get_value(
            "Salary Structure Assignment",
            {
                "employee": employee,
                "docstatus": 1,
                "from_date": [
                    "<=",
                    self.to_date,
                ],
            },
            [
                "name",
                "salary_structure",
            ],
            order_by="from_date desc",
            as_dict=True,
        )

        if not assignment:

            frappe.throw(
                _(
                    "No active Salary Structure Assignment "
                    "was found for Employee {0}."
                ).format(
                    frappe.bold(employee)
                )
            )

        amount = frappe.db.get_value(
            "Salary Detail",
            {
                "parent": assignment.salary_structure,
                "parenttype": "Salary Structure",
                "parentfield": "earnings",
                "salary_component": component,
            },
            "amount",
        )

        amount = flt(amount)

        if amount <= 0:

            frappe.throw(
                _(
                    "Salary Component {0} has no valid amount "
                    "for Employee {1}."
                ).format(
                    frappe.bold(component),
                    frappe.bold(employee),
                )
            )

        return amount

    # =========================================================================
    # Employee Salary
    # =========================================================================

    def get_employee_salary(
        self,
        employee,
        basis,
    ):

        assignment = frappe.db.get_value(
            "Salary Structure Assignment",
            {
                "employee": employee,
                "docstatus": 1,
                "from_date": [
                    "<=",
                    self.to_date,
                ],
            },
            [
                "salary_structure",
                "base",
            ],
            order_by="from_date desc",
            as_dict=True,
        )

        if not assignment:

            frappe.throw(
                _(
                    "No active Salary Structure Assignment "
                    "was found for Employee {0}."
                ).format(
                    frappe.bold(employee)
                )
            )

        if basis == "Basic Salary":

            return flt(
                assignment.base
            )

        if basis == "Gross Salary":

            earnings = frappe.get_all(
                "Salary Detail",
                filters={
                    "parent": assignment.salary_structure,
                    "parenttype": "Salary Structure",
                    "parentfield": "earnings",
                },
                pluck="amount",
            )

            return sum(
                flt(amount)
                for amount in earnings
            )

        frappe.throw(
            _(
                "Unsupported Calculation Basis: {0}"
            ).format(
                frappe.bold(basis)
            )
        )

    # =========================================================================
    # Monthly To Hourly
    # =========================================================================

    @staticmethod
    def convert_monthly_to_hourly(
        monthly_salary,
    ):

        if flt(monthly_salary) <= 0:
            return 0

        monthly_hours = 240

        return (
            flt(monthly_salary)
            / monthly_hours
        )

    # =========================================================================
    # Additional Salary Component
    # =========================================================================

    def get_salary_component(self):

        policy = frappe.get_cached_doc(
            "Overtime Policy",
            self.overtime_policy,
        )

        return (
            self.get_calculation_salary_component(
                policy
            )
        )

    # =========================================================================
    # Check Existing Additional Salaries
    # =========================================================================

    def get_existing_additional_salaries(
        self,
        employees=None,
    ):

        if self.is_new():
            return []

        if employees is None:

            employees = []

            for row in self.overtime_details or []:

                if row.employee:
                    employees.append(
                        row.employee
                    )

        employees = list(
            set(employees)
        )

        if not employees:
            return []

        return frappe.get_all(
            "Additional Salary",
            filters={
                "employee": [
                    "in",
                    employees,
                ],
                "ref_doctype": "Overtime Calculation",
                "ref_docname": self.name,
                "docstatus": ["!=", 2],
            },
            fields=[
                "name",
                "employee",
                "company",
                "salary_component",
                "amount",
                "payroll_date",
                "docstatus",
                "ref_doctype",
                "ref_docname",
            ],
            order_by="creation desc",
        )

    # =========================================================================
    # Validate Existing Additional Salaries
    # =========================================================================

    def validate_no_existing_additional_salaries(
        self,
        employees,
    ):

        if self.is_new():
            return

        employees = list(
            set(
                employee
                for employee in employees
                if employee
            )
        )

        if not employees:
            return

        existing = (
            self.get_existing_additional_salaries(
                employees
            )
        )

        if not existing:
            return

        existing_by_employee = {}

        for row in existing:

            existing_by_employee.setdefault(
                row.employee,
                []
            ).append(row)

        messages = []

        for employee, rows in (
            existing_by_employee.items()
        ):

            employee_name = (
                frappe.db.get_value(
                    "Employee",
                    employee,
                    "employee_name",
                )
                or employee
            )

            additional_names = ", ".join(
                row.name
                for row in rows
            )

            messages.append(
                _(
                    "Employee {0}: Additional Salary {1}"
                ).format(
                    frappe.bold(
                        employee_name
                    ),
                    frappe.bold(
                        additional_names
                    ),
                )
            )

        frappe.throw(
            _(
                "Additional Salary has already been created "
                "for this Overtime Calculation.<br><br>{0}"
            ).format(
                "<br>".join(messages)
            )
        )

    # =========================================================================
    # Get Connected Additional Salaries
    # =========================================================================

    def get_connected_additional_salaries(self):

        if self.is_new():
            return []

        return frappe.get_all(
            "Additional Salary",
            filters={
                "ref_doctype": "Overtime Calculation",
                "ref_docname": self.name,
                "docstatus": ["!=", 2],
            },
            fields=[
                "name",
                "employee",
                "company",
                "salary_component",
                "amount",
                "payroll_date",
                "docstatus",
                "creation",
            ],
            order_by="creation desc",
        )

    # =========================================================================
    # Get Connected Additional Salary Count
    # =========================================================================

    def get_additional_salary_count(self):

        if self.is_new():
            return 0

        return frappe.db.count(
            "Additional Salary",
            {
                "ref_doctype": "Overtime Calculation",
                "ref_docname": self.name,
                "docstatus": ["!=", 2],
            },
        )

    # =========================================================================
    # Summary
    # =========================================================================

    def update_summary(self):

        details = (
            self.get(
                self.DETAIL_TABLE
            )
            or []
        )

        employees = {
            row.employee
            for row in details
            if row.employee
        }

        requests = {
            row.overtime_request
            for row in details
            if row.overtime_request
        }

        self.total_employees = len(
            employees
        )

        self.total_requests = len(
            requests
        )

        self.total_requested_hours = round(
            sum(
                flt(
                    row.requested_hours
                )
                for row in details
            ),
            2,
        )

        self.total_actual_hours = round(
            sum(
                flt(
                    row.actual_hours
                )
                for row in details
            ),
            2,
        )

        self.total_calculated_hours = round(
            sum(
                flt(
                    row.calculated_hours
                )
                for row in details
            ),
            2,
        )

        self.total_overtime_amount = round(
            sum(
                flt(
                    row.overtime_amount
                )
                for row in details
            ),
            2,
        )

    # =========================================================================
    # Create Additional Salaries - Internal
    # =========================================================================

    def _create_additional_salaries(self):

        self.check_permission(
            "write"
        )

        self.reload()

        if self.status != self.STATUS_CALCULATED:

            frappe.throw(
                _(
                    "Additional Salary can only be created "
                    "after calculation is completed."
                )
            )

        if not self.overtime_details:

            frappe.throw(
                _("There are no Overtime Details.")
            )

        salary_component = (
            self.get_salary_component()
        )

        grouped = {}

        for row in self.overtime_details:

            if row.processed:
                continue

            if not row.employee:
                continue

            amount = flt(
                row.overtime_amount
            )

            if amount <= 0:
                continue

            grouped.setdefault(
                row.employee,
                0,
            )

            grouped[row.employee] += amount

        if not grouped:

            frappe.throw(
                _(
                    "All Overtime Details have already "
                    "been processed."
                )
            )

        # =====================================================================
        # IMPORTANT
        # Check ALL employees BEFORE creating anything
        # =====================================================================

        self.validate_no_existing_additional_salaries(
            grouped.keys()
        )

        created = {}

        # =====================================================================
        # Create Additional Salary
        # =====================================================================

        for employee, amount in grouped.items():

            additional_salary = frappe.get_doc(
                {
                    "doctype": "Additional Salary",
                    "employee": employee,
                    "company": self.company,
                    "salary_component": salary_component,
                    "amount": round(
                        amount,
                        2,
                    ),
                    "payroll_date": self.to_date,
                    "overwrite_salary_structure_amount": 0,

                    # ---------------------------------------------------------
                    # Connection
                    # ---------------------------------------------------------

                    "ref_doctype": "Overtime Calculation",
                    "ref_docname": self.name,
                }
            )

            additional_salary.insert(
                ignore_permissions=False
            )

            created[
                employee
            ] = additional_salary.name

        # =====================================================================
        # Mark Details As Processed
        # =====================================================================

        for row in self.overtime_details:

            if row.employee not in created:
                continue

            if row.processed:
                continue

            row.processed = 1

            row.additional_salary = (
                created[row.employee]
            )

        self.status = (
            self.STATUS_PROCESSED
        )

        self.processed_by = (
            frappe.session.user
        )

        self.processed_on = (
            now_datetime()
        )

        self.save(
            ignore_permissions=False
        )

        frappe.db.commit()

        return list(
            created.values()
        )


# =============================================================================
# Build Details
# =============================================================================

def clear_additional_salary_links(doc, method=None):

    if doc.ref_doctype != "Overtime Calculation" or not doc.ref_docname:
        return

    if not frappe.db.exists(
        "Overtime Calculation",
        doc.ref_docname,
    ):
        return

    frappe.db.set_value(
        "Overtime Calculation Detail",
        {
            "additional_salary": doc.name,
            "parent": doc.ref_docname,
            "parenttype": "Overtime Calculation",
        },
        "processed",
        0,
        update_modified=False,
    )

    frappe.db.set_value(
        "Overtime Calculation Detail",
        {
            "additional_salary": doc.name,
        },
        "additional_salary",
        None,
        update_modified=False,
    )

    remaining = frappe.db.count(
        "Additional Salary",
        {
            "ref_doctype": "Overtime Calculation",
            "ref_docname": doc.ref_docname,
            "name": ["!=", doc.name],
            "docstatus": ["!=", 2],
        },
    )

    parent = frappe.get_doc(
        "Overtime Calculation",
        doc.ref_docname,
    )

    if not remaining and parent.docstatus != 2:
        frappe.db.set_value(
            "Overtime Calculation",
            doc.ref_docname,
            {
                "status": OvertimeCalculation.STATUS_CALCULATED,
                "processed_by": None,
                "processed_on": None,
            },
            update_modified=False,
        )

@frappe.whitelist()
def build_details(name):

    if not name:

        frappe.throw(
            _("Overtime Calculation name is required.")
        )

    doc = frappe.get_doc(
        "Overtime Calculation",
        name,
    )

    doc.check_permission(
        "write"
    )

    if doc.docstatus == 1:

        frappe.throw(
            _(
                "Submitted Overtime Calculation "
                "cannot be recalculated."
            )
        )

    if doc.status in {
        OvertimeCalculation.STATUS_PROCESSED,
        OvertimeCalculation.STATUS_CANCELLED,
    }:

        frappe.throw(
            _(
                "Overtime Calculation with status {0} "
                "cannot be recalculated."
            ).format(
                frappe.bold(
                    doc.status
                )
            )
        )

    doc.validate()

    # =========================================================================
    # Clear Old Details
    # =========================================================================

    doc.set(
        OvertimeCalculation.DETAIL_TABLE,
        []
    )

    # =========================================================================
    # Collect Requests
    # =========================================================================

    requests = (
        doc.collect_overtime_requests()
    )

    if not requests:

        frappe.throw(
            _(
                "No Approved Overtime Requests were found "
                "for the selected Employee / criteria "
                "and calculation period."
            )
        )

    # =========================================================================
    # Process Requests
    # =========================================================================

    existing_requests = set()

    for request in requests:

        if request.name in existing_requests:
            continue

        existing_requests.add(
            request.name
        )

        actual_hours = (
            doc.calculate_actual_hours(
                request
            )
        )

        if actual_hours > 0:
            (
                calculated_hours,
                amount,
                multiplier,
                hourly_rate,
            ) = doc.calculate_request_amount(
                request,
                actual_hours,
            )
        else:
            calculated_hours = 0
            amount = 0
            multiplier = 0
            hourly_rate = 0

        detail = doc.append(
            OvertimeCalculation.DETAIL_TABLE,
            {},
        )

        detail.employee = (
            request.employee
        )

        detail.employee_name = (
            request.employee_name
        )

        detail.department = (
            request.department
        )

        detail.designation = (
            request.designation
        )

        detail.overtime_request = (
            request.name
        )

        detail.overtime_type = (
            request.overtime_type
        )

        detail.overtime_date = (
            request.overtime_date
        )

        detail.from_time = (
            request.from_time
        )

        detail.to_time = (
            request.to_time
        )

        detail.requested_hours = flt(
            request.requested_hours
        )

        detail.actual_hours = flt(
            actual_hours
        )

        detail.dvertime_duration = round(
            actual_hours * 3600
        )

        detail.calculated_hours = flt(
            calculated_hours
        )

        detail.multiplier = flt(
            multiplier
        )

        detail.hourly_rate = flt(
            hourly_rate
        )

        detail.overtime_amount = flt(
            amount
        )

        detail.salary_component = (
            doc.get_salary_component()
        )

        detail.processed = 0

    # =========================================================================
    # Validate Results
    # =========================================================================

    if not doc.overtime_details:

        frappe.throw(
            _(
                "Overtime Requests were found, "
                "but none of them generated a valid calculation."
            )
        )

    # =========================================================================
    # Status
    # =========================================================================

    doc.status = (
        OvertimeCalculation.STATUS_CALCULATED
    )

    doc.update_summary()

    doc.save(
        ignore_permissions=True
    )

    frappe.db.commit()

    return {
        "status": "success",
        "count": len(
            doc.overtime_details
        ),
        "name": doc.name,
        "employee": doc.employee,
        "total_employees": doc.total_employees,
        "total_requests": doc.total_requests,
        "total_requested_hours": doc.total_requested_hours,
        "total_actual_hours": doc.total_actual_hours,
        "total_calculated_hours": doc.total_calculated_hours,
        "total_overtime_amount": doc.total_overtime_amount,
    }


# =============================================================================
# Check Duplicate - Client Side
# =============================================================================

@frappe.whitelist()
def check_duplicate(
    name=None,
    company=None,
    payroll_period=None,
    apply_to=None,
    employee=None,
    employee_group=None,
    designation=None,
    department=None,
):

    if not company:
        return {
            "exists": False
        }

    if not payroll_period:
        return {
            "exists": False
        }

    if not apply_to:
        return {
            "exists": False
        }

    target_field_map = {
        OvertimeCalculation.APPLY_EMPLOYEE:
            "employee",

        OvertimeCalculation.APPLY_EMPLOYEE_GROUP:
            "employee_group",

        OvertimeCalculation.APPLY_DESIGNATION:
            "designation",

        OvertimeCalculation.APPLY_DEPARTMENT:
            "department",
    }

    target_field = (
        target_field_map.get(
            apply_to
        )
    )

    filters = {
        "company": company,
        "payroll_period": payroll_period,
        "apply_to": apply_to,
        "docstatus": ["!=", 2],
        "status": [
            "!=",
            OvertimeCalculation.STATUS_CANCELLED,
        ],
    }

    # -------------------------------------------------------------------------
    # Exclude Current Document
    # -------------------------------------------------------------------------

    if name:
        filters["name"] = [
            "!=",
            name,
        ]

    # -------------------------------------------------------------------------
    # All Employees
    # -------------------------------------------------------------------------

    if apply_to == OvertimeCalculation.APPLY_ALL:

        existing = frappe.get_all(
            "Overtime Calculation",
            filters=filters,
            fields=[
                "name",
                "status",
                "payroll_period",
            ],
            order_by="creation desc",
            limit_page_length=1,
        )

    # -------------------------------------------------------------------------
    # Specific Target
    # -------------------------------------------------------------------------

    elif target_field:

        target_value = locals().get(
            target_field
        )

        if not target_value:

            return {
                "exists": False
            }

        filters[target_field] = (
            target_value
        )

        existing = frappe.get_all(
            "Overtime Calculation",
            filters=filters,
            fields=[
                "name",
                "status",
                "payroll_period",
                target_field,
            ],
            order_by="creation desc",
            limit_page_length=1,
        )

    else:

        return {
            "exists": False
        }

    if not existing:

        return {
            "exists": False
        }

    row = existing[0]

    target_label = (
        frappe.get_meta(
            "Overtime Calculation"
        ).get_label(
            target_field
        )
        if target_field
        else apply_to
    )

    target_value = (
        row.get(target_field)
        if target_field
        else apply_to
    )

    message = _(
        "An Overtime Calculation already exists for "
        "Payroll Period {0} and {1} {2}.<br><br>"
        "Existing Overtime Calculation: {3}<br>"
        "Status: {4}"
    ).format(
        frappe.bold(
            payroll_period
        ),
        frappe.bold(
            target_label
        ),
        frappe.bold(
            target_value or apply_to
        ),
        frappe.bold(
            row.name
        ),
        frappe.bold(
            row.status
        ),
    )

    return {
        "exists": True,
        "name": row.name,
        "status": row.status,
        "message": message,
    }


# =============================================================================
# Get Additional Salaries
# =============================================================================

@frappe.whitelist()
def get_additional_salaries(name):

    if not name:

        frappe.throw(
            _("Overtime Calculation name is required.")
        )

    doc = frappe.get_doc(
        "Overtime Calculation",
        name,
    )

    doc.check_permission(
        "read"
    )

    salaries = (
        doc.get_connected_additional_salaries()
    )

    return {
        "count": len(salaries),
        "data": salaries,
    }


# =============================================================================
# Create Additional Salaries - PUBLIC WHITELISTED METHOD
# =============================================================================

@frappe.whitelist()
def create_additional_salaries(name):

    if not name:

        frappe.throw(
            _("Overtime Calculation name is required.")
        )

    doc = frappe.get_doc(
        "Overtime Calculation",
        name,
    )

    doc.check_permission(
        "write"
    )

    created = (
        doc._create_additional_salaries()
    )

    return {
        "count": len(created),
        "names": created,
    }