frappe.ui.form.on("Overtime Request", {

    // =========================================================================
    // Setup
    // =========================================================================

    setup(frm) {

        // ---------------------------------------------------------------------
        // Employee Filter
        //
        // Normal User:
        //     Show only the Employee linked to current User.
        //
        // Administrator:
        //     Can select any active Employee.
        // ---------------------------------------------------------------------

        frm.set_query("employee", () => {

            if (frappe.session.user === "Administrator") {

                return {
                    filters: {
                        status: "Active"
                    }
                };
            }

            return {
                filters: {
                    user_id: frappe.session.user,
                    status: "Active"
                }
            };
        });


        // ---------------------------------------------------------------------
        // Project Filter
        // ---------------------------------------------------------------------

        frm.set_query("project", () => {

            const filters = {};

            if (frm.doc.company) {
                filters.company = frm.doc.company;
            }

            return {
                filters: filters
            };
        });


        // ---------------------------------------------------------------------
        // Cost Center Filter
        // ---------------------------------------------------------------------

        frm.set_query("cost_center", () => {

            const filters = {};

            if (frm.doc.company) {
                filters.company = frm.doc.company;
            }

            return {
                filters: filters
            };
        });
    },


    // =========================================================================
    // Onload
    // =========================================================================

    onload(frm) {

        // ---------------------------------------------------------------------
        // Only execute for new documents
        // ---------------------------------------------------------------------

        if (!frm.is_new()) {
            return;
        }


        // ---------------------------------------------------------------------
        // Administrator
        //
        // Administrator can select Employee manually.
        // ---------------------------------------------------------------------

        if (frappe.session.user === "Administrator") {
            return;
        }


        // ---------------------------------------------------------------------
        // Find Employee linked to current logged-in User
        //
        // Employee.user_id = frappe.session.user
        // ---------------------------------------------------------------------

        frappe.db.get_value(
            "Employee",
            {
                user_id: frappe.session.user,
                status: "Active"
            },
            [
                "name",
                "employee_name",
                "department",
                "designation",
                "company"
            ]
        ).then((response) => {

            const employee = response.message;


            // -----------------------------------------------------------------
            // No Employee linked to current User
            // -----------------------------------------------------------------

            if (
                !employee ||
                !employee.name
            ) {

                frm.set_value(
                    "employee",
                    null
                );

                frm.set_df_property(
                    "employee",
                    "read_only",
                    0
                );

                frappe.show_alert({
                    message: __(
                        "No active Employee is linked to your User account."
                    ),
                    indicator: "orange"
                });

                return;
            }


            // -----------------------------------------------------------------
            // Automatically Set Employee
            // -----------------------------------------------------------------

            frm.set_value(
                "employee",
                employee.name
            );


            // -----------------------------------------------------------------
            // Automatically Set Employee Information
            // -----------------------------------------------------------------

            frm.set_value(
                "employee_name",
                employee.employee_name
            );

            frm.set_value(
                "department",
                employee.department
            );

            frm.set_value(
                "designation",
                employee.designation
            );

            frm.set_value(
                "company",
                employee.company
            );


            // -----------------------------------------------------------------
            // Employee becomes Read Only
            // -----------------------------------------------------------------

            frm.set_df_property(
                "employee",
                "read_only",
                1
            );


            // -----------------------------------------------------------------
            // Refresh Company Filters
            // -----------------------------------------------------------------

            frm.trigger(
                "refresh_company_filters"
            );
        });
    },


    // =========================================================================
    // Refresh
    // =========================================================================

    refresh(frm) {

        frm.trigger(
            "setup_form_state"
        );

        frm.trigger(
            "setup_status_behavior"
        );

        frm.trigger(
            "setup_approval_fields"
        );

        frm.trigger(
            "setup_submit_behavior"
        );

        frm.trigger(
            "setup_employee_behavior"
        );
    },


    // =========================================================================
    // Employee
    // =========================================================================

    employee(frm) {

        // ---------------------------------------------------------------------
        // Employee Cleared
        // ---------------------------------------------------------------------

        if (!frm.doc.employee) {

            frm.set_value(
                "employee_name",
                null
            );

            frm.set_value(
                "department",
                null
            );

            frm.set_value(
                "designation",
                null
            );

            frm.set_value(
                "company",
                null
            );

            return;
        }


        // ---------------------------------------------------------------------
        // Get Employee Master Data
        // ---------------------------------------------------------------------

        frappe.db.get_value(
            "Employee",
            frm.doc.employee,
            [
                "employee_name",
                "department",
                "designation",
                "company"
            ]
        ).then((response) => {

            const employee = response.message;

            if (!employee) {
                return;
            }


            // Employee Name

            frm.set_value(
                "employee_name",
                employee.employee_name
            );


            // Department

            frm.set_value(
                "department",
                employee.department
            );


            // Designation

            frm.set_value(
                "designation",
                employee.designation
            );


            // Company

            frm.set_value(
                "company",
                employee.company
            );


            // Refresh dependent filters

            frm.trigger(
                "refresh_company_filters"
            );
        });
    },


    // =========================================================================
    // Employee Behavior
    // =========================================================================

    setup_employee_behavior(frm) {

        // ---------------------------------------------------------------------
        // Administrator
        // ---------------------------------------------------------------------

        if (
            frappe.session.user === "Administrator"
        ) {
            return;
        }


        // ---------------------------------------------------------------------
        // Existing Document
        //
        // Employee cannot be changed after creation.
        // ---------------------------------------------------------------------

        if (!frm.is_new()) {

            frm.set_df_property(
                "employee",
                "read_only",
                1
            );

            return;
        }


        // ---------------------------------------------------------------------
        // New Document
        //
        // If Employee was automatically selected,
        // keep it read-only.
        // ---------------------------------------------------------------------

        if (frm.doc.employee) {

            frm.set_df_property(
                "employee",
                "read_only",
                1
            );
        }
    },


    // =========================================================================
    // Company
    // =========================================================================

    company(frm) {

        frm.trigger(
            "refresh_company_filters"
        );
    },


    // =========================================================================
    // Refresh Company Filters
    // =========================================================================

    refresh_company_filters(frm) {

        // ---------------------------------------------------------------------
        // Project
        // ---------------------------------------------------------------------

        frm.set_query("project", () => {

            const filters = {};

            if (frm.doc.company) {
                filters.company = frm.doc.company;
            }

            return {
                filters: filters
            };
        });


        // ---------------------------------------------------------------------
        // Cost Center
        // ---------------------------------------------------------------------

        frm.set_query("cost_center", () => {

            const filters = {};

            if (frm.doc.company) {
                filters.company = frm.doc.company;
            }

            return {
                filters: filters
            };
        });
    },


    // =========================================================================
    // Overtime Date
    // =========================================================================

    overtime_date(frm) {

        frm.trigger(
            "calculate_requested_hours"
        );
    },


    // =========================================================================
    // From Time
    // =========================================================================

    from_time(frm) {

        frm.trigger(
            "calculate_requested_hours"
        );
    },


    // =========================================================================
    // To Time
    // =========================================================================

    to_time(frm) {

        frm.trigger(
            "calculate_requested_hours"
        );
    },


    // =========================================================================
    // Calculate Requested Hours
    // =========================================================================

    calculate_requested_hours(frm) {

        if (
            !frm.doc.overtime_date ||
            !frm.doc.from_time ||
            !frm.doc.to_time
        ) {

            frm.set_value(
                "requested_hours",
                0
            );

            return;
        }


        // ---------------------------------------------------------------------
        // Start DateTime
        // ---------------------------------------------------------------------

        const start =
            frappe.datetime.str_to_obj(
                `${frm.doc.overtime_date} ${frm.doc.from_time}`
            );


        // ---------------------------------------------------------------------
        // End DateTime
        // ---------------------------------------------------------------------

        let end =
            frappe.datetime.str_to_obj(
                `${frm.doc.overtime_date} ${frm.doc.to_time}`
            );


        if (!start || !end) {
            return;
        }


        // ---------------------------------------------------------------------
        // Overnight Overtime
        //
        // Example:
        //
        // 22:00 -> 02:00
        //
        // = 4 Hours
        // ---------------------------------------------------------------------

        if (end < start) {

            end.setDate(
                end.getDate() + 1
            );
        }


        // ---------------------------------------------------------------------
        // Calculate Duration
        // ---------------------------------------------------------------------

        const difference =
            (
                end.getTime() -
                start.getTime()
            ) /
            (1000 * 60 * 60);


        // ---------------------------------------------------------------------
        // Invalid Duration
        // ---------------------------------------------------------------------

        if (difference <= 0) {

            frm.set_value(
                "requested_hours",
                0
            );

            frappe.msgprint({
                title: __(
                    "Invalid Overtime Time"
                ),
                message: __(
                    "To Time must be different from From Time."
                ),
                indicator: "red"
            });

            return;
        }


        // ---------------------------------------------------------------------
        // Set Requested Hours
        // ---------------------------------------------------------------------

        frm.set_value(
            "requested_hours",
            Number(
                difference.toFixed(2)
            )
        );
    },


    // =========================================================================
    // Status
    // =========================================================================

    status(frm) {

        // ---------------------------------------------------------------------
        // Pending Approval
        // ---------------------------------------------------------------------

        if (
            frm.doc.status === "Pending Approval"
        ) {

            frappe.show_alert({
                message: __(
                    "Overtime Request has been sent for approval."
                ),
                indicator: "orange"
            });
        }


        // ---------------------------------------------------------------------
        // Approved
        // ---------------------------------------------------------------------

        if (
            frm.doc.status === "Approved"
        ) {

            frappe.show_alert({
                message: __(
                    "Overtime Request has been approved."
                ),
                indicator: "green"
            });
        }


        // ---------------------------------------------------------------------
        // Rejected
        // ---------------------------------------------------------------------

        if (
            frm.doc.status === "Rejected"
        ) {

            frappe.show_alert({
                message: __(
                    "Overtime Request has been rejected."
                ),
                indicator: "red"
            });
        }


        // ---------------------------------------------------------------------
        // Cancelled
        // ---------------------------------------------------------------------

        if (
            frm.doc.status === "Cancelled"
        ) {

            frappe.show_alert({
                message: __(
                    "Overtime Request has been cancelled."
                ),
                indicator: "red"
            });
        }


        // ---------------------------------------------------------------------
        // Refresh UI
        // ---------------------------------------------------------------------

        frm.trigger(
            "setup_form_state"
        );

        frm.trigger(
            "setup_approval_fields"
        );

        frm.trigger(
            "setup_submit_behavior"
        );
    },


    // =========================================================================
    // Status Behavior
    // =========================================================================

    setup_status_behavior(frm) {

        if (!frm.fields_dict.status) {
            return;
        }


        // ---------------------------------------------------------------------
        // Status remains manually editable.
        //
        // Python is responsible for authorization.
        //
        // Department.custom_overtime_approver
        // ---------------------------------------------------------------------

        frm.set_df_property(
            "status",
            "read_only",
            0
        );
    },


    // =========================================================================
    // Approval Fields
    // =========================================================================

    setup_approval_fields(frm) {

        // ---------------------------------------------------------------------
        // Approved By
        // ---------------------------------------------------------------------

        if (
            frm.fields_dict.approved_by
        ) {

            frm.set_df_property(
                "approved_by",
                "read_only",
                1
            );
        }


        // ---------------------------------------------------------------------
        // Approval Date
        // ---------------------------------------------------------------------

        if (
            frm.fields_dict.approval_date
        ) {

            frm.set_df_property(
                "approval_date",
                "read_only",
                1
            );
        }
    },


    // =========================================================================
    // Form State
    // =========================================================================

    setup_form_state(frm) {

        // ---------------------------------------------------------------------
        // Server Controlled Fields
        // ---------------------------------------------------------------------

        const server_controlled_fields = [
            "approved_by",
            "approval_date"
        ];


        server_controlled_fields.forEach(
            (fieldname) => {

                if (
                    frm.fields_dict[fieldname]
                ) {

                    frm.set_df_property(
                        fieldname,
                        "read_only",
                        1
                    );
                }
            }
        );


        // ---------------------------------------------------------------------
        // Locked Statuses
        // ---------------------------------------------------------------------

        const locked_statuses = [
            "Approved",
            "Rejected",
            "Cancelled"
        ];


        if (
            !frm.is_new() &&
            locked_statuses.includes(
                frm.doc.status
            )
        ) {

            const protected_fields = [

                "employee",
                "overtime_date",
                "overtime_type",

                "from_time",
                "to_time",

                "requested_hours",

                "reason",

                "project",
                "cost_center"
            ];


            protected_fields.forEach(
                (fieldname) => {

                    if (
                        frm.fields_dict[fieldname]
                    ) {

                        frm.set_df_property(
                            fieldname,
                            "read_only",
                            1
                        );
                    }
                }
            );
        }
    },


    // =========================================================================
    // Submit Behavior
    // =========================================================================

    setup_submit_behavior(frm) {

        // ---------------------------------------------------------------------
        // Draft
        //
        // Draft cannot be submitted.
        // ---------------------------------------------------------------------

        if (
            frm.doc.status === "Draft"
        ) {

            frm.page.clear_primary_action();

            return;
        }


        // ---------------------------------------------------------------------
        // Enable Submit
        // ---------------------------------------------------------------------

        if (
            frm.doc.docstatus === 0 &&
            frm.doc.status !== "Draft"
        ) {

            frm.page.set_primary_action(
                __("Submit"),
                () => {

                    frm.savesubmit();
                }
            );
        }
    },


    // =========================================================================
    // Before Save
    // =========================================================================

    before_save(frm) {

        // ---------------------------------------------------------------------
        // Allowed Statuses
        // ---------------------------------------------------------------------

        const allowed_statuses = [
            "Draft",
            "Pending Approval",
            "Approved",
            "Rejected",
            "Cancelled"
        ];


        if (
            frm.doc.status &&
            !allowed_statuses.includes(
                frm.doc.status
            )
        ) {

            frappe.throw({
                title: __(
                    "Invalid Status"
                ),
                message: __(
                    "The selected Status is not valid."
                )
            });
        }


        // ---------------------------------------------------------------------
        // Requested Hours
        // ---------------------------------------------------------------------

        if (
            frm.doc.overtime_date &&
            frm.doc.from_time &&
            frm.doc.to_time
        ) {

            frm.trigger(
                "calculate_requested_hours"
            );
        }
    }
});