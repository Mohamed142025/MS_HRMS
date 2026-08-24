import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, get_datetime, now_datetime


class OvertimeRequest(Document):
    """
    Overtime Request Controller.

    Business Responsibilities
    --------------------------
    1. Synchronize Employee master data.
    2. Ensure the selected Employee belongs to the logged-in User.
    3. Validate overtime request information.
    4. Calculate requested overtime hours.
    5. Authorize Status changes based on:
           Department.custom_overtime_approver
    6. Prevent submitting Draft requests.
    7. Maintain approval audit information:
           approved_by
           approval_date
    8. Protect server-controlled audit fields.
    """

    # =========================================================================
    # Constants
    # =========================================================================

    STATUS_DRAFT = "Draft"
    STATUS_PENDING_APPROVAL = "Pending Approval"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"
    STATUS_CANCELLED = "Cancelled"

    STATUS_FIELD = "status"

    APPROVER_FIELD = "custom_overtime_approver"

    APPROVED_BY_FIELD = "approved_by"
    APPROVAL_DATE_FIELD = "approval_date"

    EMPLOYEE_USER_FIELD = "user_id"

    # =========================================================================
    # Document Lifecycle
    # =========================================================================

    def validate(self):
        """
        Main validation pipeline.

        All business rules are enforced server-side.
        """

        # ---------------------------------------------------------------------
        # Employee / User Validation
        # ---------------------------------------------------------------------

        self.validate_user_employee()

        self.validate_employee()

        # ---------------------------------------------------------------------
        # Overtime Validation
        # ---------------------------------------------------------------------

        self.validate_overtime_date()
        self.validate_overtime_type()
        self.validate_time_range()

        self.calculate_requested_hours()

        # ---------------------------------------------------------------------
        # Approval
        # ---------------------------------------------------------------------

        self.validate_status_change()
        self.set_status_audit_fields()

    # =========================================================================
    # Before Save
    # =========================================================================

    def before_save(self):
        """
        Protect server-controlled approval fields.
        """

        self.protect_audit_fields()

    # =========================================================================
    # Before Submit
    # =========================================================================

    def before_submit(self):
        """
        Prevent submitting an Overtime Request
        while Status is Draft.
        """

        if self.status == self.STATUS_DRAFT:

            frappe.throw(
                _(
                    "Overtime Request cannot be submitted while "
                    "Status is Draft."
                )
            )

    # =========================================================================
    # User / Employee Validation
    # =========================================================================

    def validate_user_employee(self):
        """
        Ensure the selected Employee belongs to the currently
        logged-in User.

        Business Rule
        -------------

        Employee.user_id must equal frappe.session.user.

        Example:

            Logged User:
                hr@gesc.com.eg

            Employee:
                EMP-00015

            Employee.user_id:
                hr@gesc.com.eg

        Allowed:

            hr@gesc.com.eg
                    ↓
            Employee linked to hr@gesc.com.eg

        Not Allowed:

            hr@gesc.com.eg
                    ↓
            Another Employee
        """

        current_user = frappe.session.user

        # ---------------------------------------------------------------------
        # Administrator
        # ---------------------------------------------------------------------

        if current_user == "Administrator":
            return

        # ---------------------------------------------------------------------
        # Guest
        # ---------------------------------------------------------------------

        if not current_user or current_user == "Guest":

            frappe.throw(
                _(
                    "Guest users are not allowed to create "
                    "Overtime Requests."
                )
            )

        # ---------------------------------------------------------------------
        # Employee Mandatory
        # ---------------------------------------------------------------------

        if not self.employee:

            frappe.throw(
                _(
                    "No Employee is linked to your User account."
                )
            )

        # ---------------------------------------------------------------------
        # Get Employee User
        # ---------------------------------------------------------------------

        employee_user = frappe.db.get_value(
            "Employee",
            self.employee,
            self.EMPLOYEE_USER_FIELD
        )

        # ---------------------------------------------------------------------
        # Employee has no User
        # ---------------------------------------------------------------------

        if not employee_user:

            frappe.throw(
                _(
                    "The selected Employee is not linked "
                    "to any User account."
                )
            )

        # ---------------------------------------------------------------------
        # Employee belongs to another User
        # ---------------------------------------------------------------------

        if employee_user != current_user:

            frappe.throw(
                _(
                    "You are not allowed to create an Overtime Request "
                    "for another Employee."
                )
            )

    # =========================================================================
    # Get Employee For Current User
    # =========================================================================

    @staticmethod
    def get_employee_for_current_user():
        """
        Return the active Employee linked to the currently
        logged-in User.

        Source:

            Employee.user_id

        Returns:

            Employee name

        or:

            None
        """

        current_user = frappe.session.user

        # ---------------------------------------------------------------------
        # Invalid Session
        # ---------------------------------------------------------------------

        if not current_user or current_user == "Guest":
            return None

        # ---------------------------------------------------------------------
        # Administrator
        # ---------------------------------------------------------------------

        if current_user == "Administrator":
            return None

        # ---------------------------------------------------------------------
        # Find Active Employee
        # ---------------------------------------------------------------------

        employee = frappe.db.get_value(
            "Employee",
            {
                "user_id": current_user,
                "status": "Active",
            },
            "name"
        )

        return employee or None

    # =========================================================================
    # Employee Validation
    # =========================================================================

    def validate_employee(self):
        """
        Validate Employee and synchronize employee master data.
        """

        if not self.employee:

            frappe.throw(
                _("Employee is mandatory.")
            )

        employee = frappe.get_cached_doc(
            "Employee",
            self.employee
        )

        if not employee:

            frappe.throw(
                _("Employee {0} was not found.").format(
                    frappe.bold(self.employee)
                )
            )

        # ---------------------------------------------------------------------
        # Synchronize Employee Master Data
        # ---------------------------------------------------------------------

        self.employee_name = employee.employee_name
        self.department = employee.department
        self.designation = employee.designation
        self.company = employee.company

        # ---------------------------------------------------------------------
        # Required Employee Information
        # ---------------------------------------------------------------------

        if not employee.department:

            frappe.throw(
                _(
                    "Employee {0} does not have a Department assigned."
                ).format(
                    frappe.bold(self.employee)
                )
            )

        if not employee.company:

            frappe.throw(
                _(
                    "Employee {0} does not have a Company assigned."
                ).format(
                    frappe.bold(self.employee)
                )
            )

    # =========================================================================
    # Overtime Date
    # =========================================================================

    def validate_overtime_date(self):
        """
        Validate Overtime Date.
        """

        if not self.overtime_date:

            frappe.throw(
                _("Overtime Date is mandatory.")
            )

    # =========================================================================
    # Overtime Type
    # =========================================================================

    def validate_overtime_type(self):
        """
        Validate Overtime Type.

        Allowed values:

            Normal Working Day
            Weekly Off
            Public Holiday
        """

        if not self.overtime_type:

            frappe.throw(
                _("Overtime Type is mandatory.")
            )

        allowed_types = {
            "Normal Working Day",
            "Weekly Off",
            "Public Holiday",
        }

        if self.overtime_type not in allowed_types:

            frappe.throw(
                _(
                    "Invalid Overtime Type: {0}"
                ).format(
                    frappe.bold(
                        self.overtime_type
                    )
                )
            )

    # =========================================================================
    # Time Validation
    # =========================================================================

    def validate_time_range(self):
        """
        Validate From Time and To Time.

        Overnight overtime is supported.

        Examples:

            18:00 -> 22:00
            22:00 -> 02:00
        """

        if not self.from_time:

            frappe.throw(
                _("From Time is mandatory.")
            )

        if not self.to_time:

            frappe.throw(
                _("To Time is mandatory.")
            )

        if self.from_time == self.to_time:

            frappe.throw(
                _(
                    "From Time and To Time cannot be the same."
                )
            )

    # =========================================================================
    # Requested Hours
    # =========================================================================

    def calculate_requested_hours(self):
        """
        Calculate Requested Hours from From Time and To Time.

        Supports overnight overtime.
        """

        if (
            not self.overtime_date
            or not self.from_time
            or not self.to_time
        ):

            self.requested_hours = 0
            return

        start_datetime = get_datetime(
            f"{self.overtime_date} {self.from_time}"
        )

        end_datetime = get_datetime(
            f"{self.overtime_date} {self.to_time}"
        )

        # ---------------------------------------------------------------------
        # Overnight Overtime
        # ---------------------------------------------------------------------

        if end_datetime < start_datetime:

            end_datetime = add_days(
                end_datetime,
                1
            )

        # ---------------------------------------------------------------------
        # Calculate Duration
        # ---------------------------------------------------------------------

        duration_seconds = (
            end_datetime - start_datetime
        ).total_seconds()

        requested_hours = (
            duration_seconds / 3600
        )

        if requested_hours <= 0:

            frappe.throw(
                _("Requested Hours must be greater than zero.")
            )

        self.requested_hours = round(
            requested_hours,
            2
        )

    # =========================================================================
    # Status Authorization
    # =========================================================================

    def validate_status_change(self):
        """
        Validate manual Status changes.

        Only users configured inside:

            Department.custom_overtime_approver

        can change Status.
        """

        # ---------------------------------------------------------------------
        # Status did not change
        # ---------------------------------------------------------------------

        if not self.has_value_changed(
            self.STATUS_FIELD
        ):
            return

        # ---------------------------------------------------------------------
        # Get Previous Document
        # ---------------------------------------------------------------------

        previous_doc = self.get_doc_before_save()

        if not previous_doc:
            return

        previous_status = previous_doc.get(
            self.STATUS_FIELD
        )

        current_status = self.get(
            self.STATUS_FIELD
        )

        # ---------------------------------------------------------------------
        # No Real Change
        # ---------------------------------------------------------------------

        if previous_status == current_status:
            return

        # ---------------------------------------------------------------------
        # Administrator Bypass
        # ---------------------------------------------------------------------

        if frappe.session.user == "Administrator":
            return

        # ---------------------------------------------------------------------
        # Check Overtime Approver
        # ---------------------------------------------------------------------

        if not self.is_overtime_approver():

            frappe.throw(
                _(
                    "You are not authorized to change the Status "
                    "of this Overtime Request. Only the configured "
                    "Overtime Approver for the employee's Department "
                    "can change the Status."
                )
            )

    # =========================================================================
    # Overtime Approver Authorization
    # =========================================================================

    def is_overtime_approver(self):
        """
        Check whether the current user exists inside:

            Department.custom_overtime_approver
        """

        current_user = frappe.session.user

        # ---------------------------------------------------------------------
        # Session Validation
        # ---------------------------------------------------------------------

        if not current_user:
            return False

        if current_user == "Guest":
            return False

        # ---------------------------------------------------------------------
        # Department Validation
        # ---------------------------------------------------------------------

        if not self.department:
            return False

        # ---------------------------------------------------------------------
        # Department Metadata
        # ---------------------------------------------------------------------

        department_meta = frappe.get_meta(
            "Department"
        )

        approver_field = department_meta.get_field(
            self.APPROVER_FIELD
        )

        if not approver_field:

            frappe.throw(
                _(
                    "Department does not contain the field "
                    "'{0}'."
                ).format(
                    frappe.bold(
                        self.APPROVER_FIELD
                    )
                )
            )

        # ---------------------------------------------------------------------
        # Validate Table Field
        # ---------------------------------------------------------------------

        if approver_field.fieldtype != "Table":

            frappe.throw(
                _(
                    "Department.{0} must be a Table field."
                ).format(
                    frappe.bold(
                        self.APPROVER_FIELD
                    )
                )
            )

        # ---------------------------------------------------------------------
        # Child DocType
        # ---------------------------------------------------------------------

        child_doctype = approver_field.options

        if not child_doctype:

            frappe.throw(
                _(
                    "No Child DocType is configured for "
                    "Department.{0}."
                ).format(
                    self.APPROVER_FIELD
                )
            )

        # ---------------------------------------------------------------------
        # Child Metadata
        # ---------------------------------------------------------------------

        child_meta = frappe.get_meta(
            child_doctype
        )

        # ---------------------------------------------------------------------
        # Find User Field
        # ---------------------------------------------------------------------

        user_field = None

        preferred_fields = (
            "user",
            "approver",
            "approver_user",
            "employee_user",
            "custom_user",
        )

        # ---------------------------------------------------------------------
        # Preferred Fields
        # ---------------------------------------------------------------------

        for fieldname in preferred_fields:

            field = child_meta.get_field(
                fieldname
            )

            if (
                field
                and field.fieldtype == "Link"
                and field.options == "User"
            ):

                user_field = field
                break

        # ---------------------------------------------------------------------
        # Automatic Detection
        # ---------------------------------------------------------------------

        if not user_field:

            for field in child_meta.fields:

                if (
                    field.fieldtype == "Link"
                    and field.options == "User"
                ):

                    user_field = field
                    break

        # ---------------------------------------------------------------------
        # User Field Not Found
        # ---------------------------------------------------------------------

        if not user_field:

            frappe.throw(
                _(
                    "The Child DocType {0} does not contain "
                    "a Link field to User."
                ).format(
                    frappe.bold(
                        child_doctype
                    )
                )
            )

        # ---------------------------------------------------------------------
        # Check Current User
        # ---------------------------------------------------------------------

        filters = {
            "parent": self.department,
            "parenttype": "Department",
            "parentfield": self.APPROVER_FIELD,
            user_field.fieldname: current_user,
        }

        return bool(
            frappe.db.exists(
                child_doctype,
                filters
            )
        )

    # =========================================================================
    # Approval Audit
    # =========================================================================

    def set_status_audit_fields(self):
        """
        Automatically maintain approval audit information.

        When Status changes to Approved:

            approved_by
                =
            current logged-in user

            approval_date
                =
            current server date/time
        """

        if not self.has_value_changed(
            self.STATUS_FIELD
        ):
            return

        previous_doc = self.get_doc_before_save()

        if not previous_doc:
            return

        previous_status = previous_doc.get(
            self.STATUS_FIELD
        )

        current_status = self.get(
            self.STATUS_FIELD
        )

        # =========================================================================
        # Approved
        # =========================================================================

        if (
            current_status == self.STATUS_APPROVED
            and previous_status != self.STATUS_APPROVED
        ):

            self.set_field_if_exists(
                self.APPROVED_BY_FIELD,
                frappe.session.user
            )

            self.set_field_if_exists(
                self.APPROVAL_DATE_FIELD,
                now_datetime()
            )

        # =========================================================================
        # Status changed away from Approved
        # =========================================================================

        elif (
            previous_status == self.STATUS_APPROVED
            and current_status != self.STATUS_APPROVED
        ):

            self.clear_field_if_exists(
                self.APPROVED_BY_FIELD
            )

            self.clear_field_if_exists(
                self.APPROVAL_DATE_FIELD
            )

    # =========================================================================
    # Set Field Helper
    # =========================================================================

    def set_field_if_exists(
        self,
        fieldname,
        value
    ):
        """
        Safely set a field if it exists.
        """

        if self.meta.has_field(
            fieldname
        ):

            setattr(
                self,
                fieldname,
                value
            )

    # =========================================================================
    # Clear Field Helper
    # =========================================================================

    def clear_field_if_exists(
        self,
        fieldname
    ):
        """
        Safely clear a field if it exists.
        """

        if self.meta.has_field(
            fieldname
        ):

            setattr(
                self,
                fieldname,
                None
            )

    # =========================================================================
    # Protect Audit Fields
    # =========================================================================

    def protect_audit_fields(self):
        """
        Prevent manual modification of:

            approved_by
            approval_date

        These values are controlled exclusively by the server.
        """

        previous_doc = self.get_doc_before_save()

        if not previous_doc:
            return

        protected_fields = (
            self.APPROVED_BY_FIELD,
            self.APPROVAL_DATE_FIELD,
        )

        # ---------------------------------------------------------------------
        # Determine Status Change
        # ---------------------------------------------------------------------

        status_changed = self.has_value_changed(
            self.STATUS_FIELD
        )

        previous_status = None
        current_status = None

        if status_changed:

            previous_status = previous_doc.get(
                self.STATUS_FIELD
            )

            current_status = self.get(
                self.STATUS_FIELD
            )

        # ---------------------------------------------------------------------
        # Protect Fields
        # ---------------------------------------------------------------------

        for fieldname in protected_fields:

            if not self.meta.has_field(
                fieldname
            ):
                continue

            if not self.has_value_changed(
                fieldname
            ):
                continue

            # -----------------------------------------------------------------
            # Allow server to populate approval fields
            # when Status changes to Approved.
            # -----------------------------------------------------------------

            if (
                status_changed
                and current_status == self.STATUS_APPROVED
                and previous_status != self.STATUS_APPROVED
            ):

                continue

            # -----------------------------------------------------------------
            # Restore original value
            # -----------------------------------------------------------------

            setattr(
                self,
                fieldname,
                previous_doc.get(
                    fieldname
                )
            )


# =============================================================================
# API
# =============================================================================

@frappe.whitelist()
def get_user_employee():
    """
    Return the active Employee linked to the currently
    logged-in User.

    This method is intended for the Overtime Request client script.

    Returns:

        {
            "employee": "EMP-00001"
        }

    or:

        {
            "employee": None
        }
    """

    current_user = frappe.session.user

    # -------------------------------------------------------------------------
    # Guest
    # -------------------------------------------------------------------------

    if not current_user or current_user == "Guest":

        return {
            "employee": None
        }

    # -------------------------------------------------------------------------
    # Administrator
    # -------------------------------------------------------------------------

    if current_user == "Administrator":

        return {
            "employee": None
        }

    # -------------------------------------------------------------------------
    # Find Active Employee
    # -------------------------------------------------------------------------

    employee = frappe.db.get_value(
        "Employee",
        {
            "user_id": current_user,
            "status": "Active",
        },
        "name"
    )

    return {
        "employee": employee or None
    }