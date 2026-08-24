import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class OvertimePolicy(Document):
    """
    Overtime Policy Controller.

    Responsibilities
    ----------------
    1. Validate policy master data.
    2. Validate applicability.
    3. Validate effective dates.
    4. Validate calculation basis.
    5. Validate calculation salary component.
    6. Validate overtime salary component.
    7. Validate fixed hourly rate.
    8. Validate rounding configuration.
    9. Validate overtime rules.
    10. Prevent overlapping overtime rules.
    """

    # =========================================================================
    # CONSTANTS
    # =========================================================================

    STATUS_DRAFT = "Draft"
    STATUS_ACTIVE = "Active"
    STATUS_INACTIVE = "Inactive"

    APPLY_TO_ALL = "All Employees"
    APPLY_TO_DEPARTMENT = "Department"
    APPLY_TO_DESIGNATION = "Designation"
    APPLY_TO_EMPLOYEE_GROUP = "Employee Group"
    APPLY_TO_EMPLOYEE = "Employee"

    CALC_BASIC = "Basic Salary"
    CALC_GROSS = "Gross Salary"
    CALC_COMPONENT = "Salary Component"
    CALC_FIXED = "Fixed Hourly Rate"

    ROUND_NEAREST = "Nearest"
    ROUND_UP = "Round Up"
    ROUND_DOWN = "Round Down"

    # =========================================================================
    # VALIDATE
    # =========================================================================

    def validate(self):
        """
        Main server-side validation pipeline.
        """

        self.validate_basic_information()
        self.validate_effective_dates()
        self.validate_applicability()
        self.validate_calculation_settings()
        self.validate_rounding_settings()
        self.validate_overtime_rules()

    # =========================================================================
    # BASIC INFORMATION
    # =========================================================================

    def validate_basic_information(self):
        """
        Validate basic policy information.
        """

        if not self.policy_name:
            frappe.throw(
                _("Policy Name is mandatory.")
            )

        if not self.company:
            frappe.throw(
                _("Company is mandatory.")
            )

        allowed_statuses = {
            self.STATUS_DRAFT,
            self.STATUS_ACTIVE,
            self.STATUS_INACTIVE,
        }

        if self.status not in allowed_statuses:

            frappe.throw(
                _(
                    "Invalid Status: {0}"
                ).format(
                    frappe.bold(self.status)
                )
            )

    # =========================================================================
    # EFFECTIVE DATES
    # =========================================================================

    def validate_effective_dates(self):
        """
        Validate effective date range.
        """

        if not self.effective_from:
            frappe.throw(
                _("Effective From is mandatory.")
            )

        effective_from = getdate(
            self.effective_from
        )

        if self.effective_to:

            effective_to = getdate(
                self.effective_to
            )

            if effective_to < effective_from:

                frappe.throw(
                    _(
                        "Effective To cannot be earlier than Effective From."
                    )
                )

    # =========================================================================
    # APPLICABILITY
    # =========================================================================

    def validate_applicability(self):
        """
        Validate Apply To configuration.
        """

        allowed_values = {
            self.APPLY_TO_ALL,
            self.APPLY_TO_DEPARTMENT,
            self.APPLY_TO_DESIGNATION,
            self.APPLY_TO_EMPLOYEE_GROUP,
            self.APPLY_TO_EMPLOYEE,
        }

        if self.apply_to not in allowed_values:

            frappe.throw(
                _(
                    "Invalid Apply To value: {0}"
                ).format(
                    frappe.bold(self.apply_to)
                )
            )


        # ---------------------------------------------------------------------
        # All Employees
        # ---------------------------------------------------------------------

        if self.apply_to == self.APPLY_TO_ALL:
            return


        # ---------------------------------------------------------------------
        # Department
        # ---------------------------------------------------------------------

        if (
            self.apply_to == self.APPLY_TO_DEPARTMENT
            and not self.department
        ):

            frappe.throw(
                _(
                    "Department is mandatory for this Policy."
                )
            )


        # ---------------------------------------------------------------------
        # Designation
        # ---------------------------------------------------------------------

        if (
            self.apply_to == self.APPLY_TO_DESIGNATION
            and not self.designation
        ):

            frappe.throw(
                _(
                    "Designation is mandatory for this Policy."
                )
            )


        # ---------------------------------------------------------------------
        # Employee Group
        # ---------------------------------------------------------------------

        if (
            self.apply_to == self.APPLY_TO_EMPLOYEE_GROUP
            and not self.employee_group
        ):

            frappe.throw(
                _(
                    "Employee Group is mandatory for this Policy."
                )
            )


        # ---------------------------------------------------------------------
        # Employee
        # ---------------------------------------------------------------------

        if (
            self.apply_to == self.APPLY_TO_EMPLOYEE
            and not self.employee
        ):

            frappe.throw(
                _(
                    "Employee is mandatory for this Policy."
                )
            )


        # ---------------------------------------------------------------------
        # Employee Company
        # ---------------------------------------------------------------------

        if self.apply_to == self.APPLY_TO_EMPLOYEE:

            employee_company = frappe.db.get_value(
                "Employee",
                self.employee,
                "company"
            )

            if (
                employee_company
                and employee_company != self.company
            ):

                frappe.throw(
                    _(
                        "Employee {0} does not belong to Company {1}."
                    ).format(
                        frappe.bold(self.employee),
                        frappe.bold(self.company)
                    )
                )

    # =========================================================================
    # CALCULATION SETTINGS
    # =========================================================================

    def validate_calculation_settings(self):
        """
        Validate calculation basis and all related fields.
        """

        allowed_basis = {
            self.CALC_BASIC,
            self.CALC_GROSS,
            self.CALC_COMPONENT,
            self.CALC_FIXED,
        }

        if self.calculation_basis not in allowed_basis:

            frappe.throw(
                _(
                    "Invalid Calculation Basis: {0}"
                ).format(
                    frappe.bold(self.calculation_basis)
                )
            )


        # =====================================================================
        # OVERTIME SALARY COMPONENT
        # =====================================================================
        #
        # IMPORTANT:
        #
        # salary_component is the component where the final overtime
        # amount will be recorded.
        #
        # It is REQUIRED for ALL calculation bases.
        #

        if not self.salary_component:

            frappe.throw(
                _(
                    "Please configure Salary Component in Overtime Policy before processing."
                )
            )

        self.validate_salary_component(
            self.salary_component,
            "Overtime Salary Component"
        )


        # =====================================================================
        # BASIC SALARY
        # =====================================================================

        if self.calculation_basis == self.CALC_BASIC:

            # No additional field required.

            return


        # =====================================================================
        # GROSS SALARY
        # =====================================================================

        if self.calculation_basis == self.CALC_GROSS:

            # No additional field required.

            return


        # =====================================================================
        # SALARY COMPONENT
        # =====================================================================
        #
        # calculation_salary_component is the component used as the
        # source for calculating the hourly rate.
        #

        if self.calculation_basis == self.CALC_COMPONENT:

            if not self.calculation_salary_component:

                frappe.throw(
                    _(
                        "Calculation Salary Component is mandatory when "
                        "Calculation Basis is Salary Component."
                    )
                )

            self.validate_salary_component(
                self.calculation_salary_component,
                "Calculation Salary Component"
            )

            return


        # =====================================================================
        # FIXED HOURLY RATE
        # =====================================================================

        if self.calculation_basis == self.CALC_FIXED:

            if flt(self.fixed_hourly_rate) <= 0:

                frappe.throw(
                    _(
                        "Fixed Hourly Rate must be greater than zero."
                    )
                )

            return

    # =========================================================================
    # SALARY COMPONENT VALIDATION
    # =========================================================================

    def validate_salary_component(
        self,
        salary_component,
        field_label="Salary Component"
    ):
        """
        Validate that a Salary Component exists and is an Earning.
        """

        component_type = frappe.db.get_value(
            "Salary Component",
            salary_component,
            "type"
        )

        if not component_type:

            frappe.throw(
                _(
                    "{0} {1} was not found."
                ).format(
                    field_label,
                    frappe.bold(salary_component)
                )
            )

        if component_type != "Earning":

            frappe.throw(
                _(
                    "{0} {1} must be an Earning component."
                ).format(
                    field_label,
                    frappe.bold(salary_component)
                )
            )

    # =========================================================================
    # ROUNDING
    # =========================================================================

    def validate_rounding_settings(self):
        """
        Validate rounding configuration.
        """

        if not self.enable_rounding:
            return

        allowed_rules = {
            self.ROUND_NEAREST,
            self.ROUND_UP,
            self.ROUND_DOWN,
        }

        if self.rounding_rule not in allowed_rules:

            frappe.throw(
                _(
                    "Invalid Rounding Rule: {0}"
                ).format(
                    frappe.bold(self.rounding_rule)
                )
            )

        if flt(self.rounding_interval) <= 0:

            frappe.throw(
                _(
                    "Rounding Interval must be greater than zero."
                )
            )

    # =========================================================================
    # OVERTIME RULES
    # =========================================================================

    def validate_overtime_rules(self):
        """
        Validate all overtime policy rules.
        """

        if not self.overtime_policy_rule:

            frappe.throw(
                _(
                    "At least one Overtime Policy Rule is required."
                )
            )

        for row in self.overtime_policy_rule:

            self.validate_rule_row(row)

        self.validate_no_overlapping_rules()

    # =========================================================================
    # RULE ROW VALIDATION
    # =========================================================================

    def validate_rule_row(self, row):
        """
        Validate one overtime policy rule.
        """

        if not row.overtime_type:

            frappe.throw(
                _(
                    "Overtime Type is mandatory in row {0}."
                ).format(
                    row.idx
                )
            )


        if flt(row.from_hour) < 0:

            frappe.throw(
                _(
                    "From Hour cannot be negative in row {0}."
                ).format(
                    row.idx
                )
            )


        if flt(row.to_hour) <= flt(row.from_hour):

            frappe.throw(
                _(
                    "To Hour must be greater than From Hour in row {0}."
                ).format(
                    row.idx
                )
            )


        if flt(row.multiplier) <= 0:

            frappe.throw(
                _(
                    "Multiplier must be greater than zero in row {0}."
                ).format(
                    row.idx
                )
            )

    # =========================================================================
    # OVERLAPPING RULES
    # =========================================================================

    def validate_no_overlapping_rules(self):
        """
        Prevent overlapping hour ranges for the same Overtime Type.
        """

        rules_by_type = {}

        for row in self.overtime_policy_rule:

            if not row.enabled:
                continue

            overtime_type = row.overtime_type

            rules_by_type.setdefault(
                overtime_type,
                []
            ).append(row)


        for overtime_type, rules in rules_by_type.items():

            sorted_rules = sorted(
                rules,
                key=lambda rule: flt(rule.from_hour)
            )

            previous_rule = None

            for current_rule in sorted_rules:

                if previous_rule:

                    previous_to = flt(
                        previous_rule.to_hour
                    )

                    current_from = flt(
                        current_rule.from_hour
                    )

                    if current_from < previous_to:

                        frappe.throw(
                            _(
                                "Overlapping Overtime Rules detected "
                                "for {0}: Row {1} overlaps with Row {2}."
                            ).format(
                                frappe.bold(overtime_type),
                                current_rule.idx,
                                previous_rule.idx
                            )
                        )

                previous_rule = current_rule

    # =========================================================================
    # ACTIVE POLICY CONFLICT
    # =========================================================================

    def validate_active_policy_conflict(self):
        """
        Reserved for future policy resolver.

        This will later prevent multiple active policies
        with conflicting applicability and effective dates.
        """

        if self.status != self.STATUS_ACTIVE:
            return

        # Reserved for future implementation.