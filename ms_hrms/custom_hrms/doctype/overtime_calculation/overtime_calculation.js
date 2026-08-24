frappe.ui.form.on("Overtime Calculation", {

    // =========================================================================
    // Setup
    // =========================================================================

    setup(frm) {
        frm.trigger("setup_queries");
    },


    // =========================================================================
    // On Load
    // =========================================================================

    onload(frm) {
        frm.trigger("setup_queries");
        frm.trigger("toggle_apply_to_fields");
        frm.trigger("setup_buttons");
    },


    // =========================================================================
    // Refresh
    // =========================================================================

    refresh(frm) {
        frm.trigger("setup_queries");
        frm.trigger("toggle_apply_to_fields");
        frm.trigger("setup_buttons");
    },


    // =========================================================================
    // Apply To
    // =========================================================================

    apply_to(frm) {

        frm.trigger("toggle_apply_to_fields");
        frm.trigger("setup_queries");

        // Clear fields that are not relevant
        if (frm.doc.apply_to !== "Employee") {
            frm.set_value("employee", null);
        }

        if (frm.doc.apply_to !== "Department") {
            frm.set_value("department", null);
        }

        if (frm.doc.apply_to !== "Designation") {
            frm.set_value("designation", null);
        }

        if (frm.doc.apply_to !== "Employee Group") {
            frm.set_value("employee_group", null);
        }

        frm.trigger("check_duplicate");
    },


    // =========================================================================
    // Company
    // =========================================================================

    company(frm) {

        frm.trigger("setup_queries");

        if (
            frm.doc.overtime_policy &&
            frm.doc.company
        ) {

            frappe.db.get_value(
                "Overtime Policy",
                frm.doc.overtime_policy,
                "company"
            ).then(r => {

                if (
                    r.message &&
                    r.message.company &&
                    r.message.company !== frm.doc.company
                ) {

                    frm.set_value(
                        "overtime_policy",
                        null
                    );

                    frm.set_value(
                        "policy_status",
                        null
                    );

                    frm.set_value(
                        "calculation_basis",
                        null
                    );

                    frappe.show_alert({
                        message: __(
                            "The selected Overtime Policy belongs to another Company."
                        ),
                        indicator: "orange"
                    });
                }

                frm.trigger("check_duplicate");
            });
        } else {
            frm.trigger("check_duplicate");
        }
    },


    // =========================================================================
    // Payroll Period
    // =========================================================================

    payroll_period(frm) {

        if (!frm.doc.payroll_period) {

            frm.set_value(
                "from_date",
                null
            );

            frm.set_value(
                "to_date",
                null
            );

            return;
        }

        frappe.db.get_value(
            "Payroll Period",
            frm.doc.payroll_period,
            [
                "start_date",
                "end_date",
                "company"
            ]
        ).then(r => {

            const payroll_period = r.message;

            if (!payroll_period) {
                return;
            }

            // -----------------------------------------------------------------
            // Company Validation
            // -----------------------------------------------------------------

            if (
                frm.doc.company &&
                payroll_period.company &&
                payroll_period.company !== frm.doc.company
            ) {

                frappe.msgprint({
                    title: __("Invalid Payroll Period"),
                    message: __(
                        "The selected Payroll Period belongs to another Company."
                    ),
                    indicator: "red"
                });

                frm.set_value(
                    "payroll_period",
                    null
                );

                frm.set_value(
                    "from_date",
                    null
                );

                frm.set_value(
                    "to_date",
                    null
                );

                return;
            }

            // -----------------------------------------------------------------
            // Set From Date
            // -----------------------------------------------------------------

            if (payroll_period.start_date) {

                frm.set_value(
                    "from_date",
                    payroll_period.start_date
                );
            }

            // -----------------------------------------------------------------
            // Set To Date
            // -----------------------------------------------------------------

            if (payroll_period.end_date) {

                frm.set_value(
                    "to_date",
                    payroll_period.end_date
                );
            }

            // -----------------------------------------------------------------
            // Check Duplicate
            // -----------------------------------------------------------------

            frm.trigger("check_duplicate");
        });
    },


    // =========================================================================
    // Employee
    // =========================================================================

    employee(frm) {

        if (!frm.doc.employee) {
            frm.trigger("check_duplicate");
            return;
        }

        frappe.db.get_value(
            "Employee",
            frm.doc.employee,
            [
                "employee_name",
                "department",
                "designation",
                "employee_group",
                "company"
            ]
        ).then(r => {

            const employee = r.message;

            if (!employee) {
                return;
            }

            // -----------------------------------------------------------------
            // Employee Name
            // -----------------------------------------------------------------

            if (
                employee.employee_name &&
                frm.doc.employee_name !== employee.employee_name
            ) {

                frm.set_value(
                    "employee_name",
                    employee.employee_name
                );
            }

            // -----------------------------------------------------------------
            // Department
            // -----------------------------------------------------------------

            if (
                employee.department &&
                !frm.doc.department
            ) {

                frm.set_value(
                    "department",
                    employee.department
                );
            }

            // -----------------------------------------------------------------
            // Designation
            // -----------------------------------------------------------------

            if (
                employee.designation &&
                !frm.doc.designation
            ) {

                frm.set_value(
                    "designation",
                    employee.designation
                );
            }

            // -----------------------------------------------------------------
            // Company
            // -----------------------------------------------------------------

            if (
                employee.company &&
                !frm.doc.company
            ) {

                frm.set_value(
                    "company",
                    employee.company
                );
            }

            frm.trigger("check_duplicate");
        });
    },


    // =========================================================================
    // Department
    // =========================================================================

    department(frm) {

        if (
            frm.doc.apply_to === "Department" &&
            frm.doc.department
        ) {

            if (frm.doc.designation) {
                frm.set_value(
                    "designation",
                    null
                );
            }

            if (frm.doc.employee_group) {
                frm.set_value(
                    "employee_group",
                    null
                );
            }

            if (frm.doc.employee) {
                frm.set_value(
                    "employee",
                    null
                );
            }
        }

        frm.trigger("check_duplicate");
    },


    // =========================================================================
    // Designation
    // =========================================================================

    designation(frm) {

        if (
            frm.doc.apply_to === "Designation" &&
            frm.doc.designation
        ) {

            if (frm.doc.department) {
                frm.set_value(
                    "department",
                    null
                );
            }

            if (frm.doc.employee_group) {
                frm.set_value(
                    "employee_group",
                    null
                );
            }

            if (frm.doc.employee) {
                frm.set_value(
                    "employee",
                    null
                );
            }
        }

        frm.trigger("check_duplicate");
    },


    // =========================================================================
    // Employee Group
    // =========================================================================

    employee_group(frm) {

        if (
            frm.doc.apply_to === "Employee Group" &&
            frm.doc.employee_group
        ) {

            if (frm.doc.department) {
                frm.set_value(
                    "department",
                    null
                );
            }

            if (frm.doc.designation) {
                frm.set_value(
                    "designation",
                    null
                );
            }

            if (frm.doc.employee) {
                frm.set_value(
                    "employee",
                    null
                );
            }
        }

        frm.trigger("check_duplicate");
    },


    // =========================================================================
    // Overtime Policy
    // =========================================================================

    overtime_policy(frm) {

        if (!frm.doc.overtime_policy) {

            frm.set_value(
                "policy_status",
                null
            );

            frm.set_value(
                "calculation_basis",
                null
            );

            return;
        }

        frappe.db.get_value(
            "Overtime Policy",
            frm.doc.overtime_policy,
            [
                "company",
                "status",
                "calculation_basis",
                "calculation_salary_component"
            ]
        ).then(r => {

            const policy = r.message;

            if (!policy) {
                return;
            }

            // -----------------------------------------------------------------
            // Company Validation
            // -----------------------------------------------------------------

            if (
                frm.doc.company &&
                policy.company &&
                policy.company !== frm.doc.company
            ) {

                frappe.msgprint({
                    title: __("Invalid Overtime Policy"),
                    message: __(
                        "The selected Overtime Policy belongs to another Company."
                    ),
                    indicator: "red"
                });

                frm.set_value(
                    "overtime_policy",
                    null
                );

                frm.set_value(
                    "policy_status",
                    null
                );

                frm.set_value(
                    "calculation_basis",
                    null
                );

                return;
            }

            // -----------------------------------------------------------------
            // Policy Status
            // -----------------------------------------------------------------

            frm.set_value(
                "policy_status",
                policy.status
            );

            // -----------------------------------------------------------------
            // Calculation Basis
            // -----------------------------------------------------------------

            frm.set_value(
                "calculation_basis",
                policy.calculation_basis
            );

            // -----------------------------------------------------------------
            // Warning
            // -----------------------------------------------------------------

            if (
                policy.status !== "Active"
            ) {

                frappe.show_alert({
                    message: __(
                        "Selected Overtime Policy is not Active."
                    ),
                    indicator: "orange"
                });
            }
        });
    },


    // =========================================================================
    // From Date
    // =========================================================================

    from_date(frm) {

        frm.trigger(
            "validate_dates"
        );
    },


    // =========================================================================
    // To Date
    // =========================================================================

    to_date(frm) {

        frm.trigger(
            "validate_dates"
        );
    },


    // =========================================================================
    // Validate Dates
    // =========================================================================

    validate_dates(frm) {

        if (
            !frm.doc.from_date ||
            !frm.doc.to_date
        ) {
            return;
        }

        const from_date =
            frappe.datetime.str_to_obj(
                frm.doc.from_date
            );

        const to_date =
            frappe.datetime.str_to_obj(
                frm.doc.to_date
            );

        if (to_date < from_date) {

            frappe.msgprint({
                title: __("Invalid Period"),
                message: __(
                    "To Date cannot be earlier than From Date."
                ),
                indicator: "red"
            });

            frm.set_value(
                "to_date",
                null
            );

            return;
        }

        frm.trigger(
            "check_duplicate"
        );
    },


    // =========================================================================
    // Check Duplicate
    // =========================================================================

    check_duplicate(frm) {

        // Do not check incomplete documents
        if (
            frm.is_new() &&
            !frm.doc.company
        ) {
            return;
        }

        if (
            !frm.doc.payroll_period ||
            !frm.doc.apply_to
        ) {
            return;
        }

        const target_fields = {
            "Employee": "employee",
            "Department": "department",
            "Designation": "designation",
            "Employee Group": "employee_group"
        };

        const target_field =
            target_fields[frm.doc.apply_to];

        if (
            target_field &&
            !frm.doc[target_field]
        ) {
            return;
        }

        frappe.call({

            method:
                "ms_hrms.custom_hrms.doctype.overtime_calculation.overtime_calculation.check_duplicate",

            args: {
                name: frm.doc.name || "",
                company: frm.doc.company || "",
                payroll_period: frm.doc.payroll_period,
                apply_to: frm.doc.apply_to,
                employee: frm.doc.employee || "",
                employee_group: frm.doc.employee_group || "",
                designation: frm.doc.designation || "",
                department: frm.doc.department || ""
            },

            callback: function (r) {

                if (
                    r.message &&
                    r.message.exists
                ) {

                    frappe.msgprint({
                        title: __("Duplicate Overtime Calculation"),
                        message: r.message.message,
                        indicator: "red"
                    });

                    // Clear the selected target
                    if (target_field) {

                        frm.set_value(
                            target_field,
                            null
                        );
                    }
                }
            }
        });
    },


    // =========================================================================
    // Setup Queries
    // =========================================================================

    setup_queries(frm) {

        // ---------------------------------------------------------------------
        // Employee
        // ---------------------------------------------------------------------

        frm.set_query(
            "employee",
            () => {

                const filters = {
                    status: "Active"
                };

                if (frm.doc.company) {

                    filters.company =
                        frm.doc.company;
                }

                return {
                    filters: filters
                };
            }
        );


        // ---------------------------------------------------------------------
        // Department
        // ---------------------------------------------------------------------

        frm.set_query(
            "department",
            () => {

                const filters = {};

                if (frm.doc.company) {

                    filters.company =
                        frm.doc.company;
                }

                return {
                    filters: filters
                };
            }
        );


        // ---------------------------------------------------------------------
        // Designation
        // ---------------------------------------------------------------------

        frm.set_query(
            "designation",
            () => {

                return {};
            }
        );


        // ---------------------------------------------------------------------
        // Employee Group
        // ---------------------------------------------------------------------

        frm.set_query(
            "employee_group",
            () => {

                return {};
            }
        );


        // ---------------------------------------------------------------------
        // Payroll Period
        // ---------------------------------------------------------------------

        frm.set_query(
            "payroll_period",
            () => {

                const filters = {};

                if (frm.doc.company) {

                    filters.company =
                        frm.doc.company;
                }

                return {
                    filters: filters
                };
            }
        );


        // ---------------------------------------------------------------------
        // Overtime Policy
        // ---------------------------------------------------------------------

        frm.set_query(
            "overtime_policy",
            () => {

                const filters = {
                    status: "Active"
                };

                if (frm.doc.company) {

                    filters.company =
                        frm.doc.company;
                }

                return {
                    filters: filters
                };
            }
        );
    },


    // =========================================================================
    // Toggle Apply To Fields
    // =========================================================================

    toggle_apply_to_fields(frm) {

        const fields = [
            "employee",
            "employee_group",
            "designation",
            "department"
        ];

        fields.forEach(
            fieldname => {

                if (!frm.fields_dict[fieldname]) {
                    return;
                }

                frm.set_df_property(
                    fieldname,
                    "hidden",
                    1
                );

                frm.set_df_property(
                    fieldname,
                    "reqd",
                    0
                );
            }
        );


        if (
            frm.doc.apply_to === "Employee"
        ) {

            frm.set_df_property(
                "employee",
                "hidden",
                0
            );

            frm.set_df_property(
                "employee",
                "reqd",
                1
            );
        }

        else if (
            frm.doc.apply_to === "Department"
        ) {

            frm.set_df_property(
                "department",
                "hidden",
                0
            );

            frm.set_df_property(
                "department",
                "reqd",
                1
            );
        }

        else if (
            frm.doc.apply_to === "Designation"
        ) {

            frm.set_df_property(
                "designation",
                "hidden",
                0
            );

            frm.set_df_property(
                "designation",
                "reqd",
                1
            );
        }

        else if (
            frm.doc.apply_to === "Employee Group"
        ) {

            frm.set_df_property(
                "employee_group",
                "hidden",
                0
            );

            frm.set_df_property(
                "employee_group",
                "reqd",
                1
            );
        }
    },


    // =========================================================================
    // Setup Buttons
    // =========================================================================

    setup_buttons(frm) {

        frm.remove_custom_button(
            __("Collect Overtime"),
            __("Actions")
        );

        frm.remove_custom_button(
            __("Create Additional Salaries"),
            __("Actions")
        );


        // ---------------------------------------------------------------------
        // Collect Overtime
        // ---------------------------------------------------------------------

        if (
            !frm.is_new() &&
            frm.doc.docstatus === 0 &&
            frm.doc.status !== "Processed" &&
            frm.doc.status !== "Cancelled"
        ) {

            frm.add_custom_button(
                __("Collect Overtime"),
                () => {

                    frm.trigger(
                        "collect_overtime"
                    );

                },
                __("Actions")
            );
        }


        // ---------------------------------------------------------------------
        // Create Additional Salaries
        // ---------------------------------------------------------------------

        if (
            !frm.is_new() &&
            frm.doc.status === "Calculated" &&
            frm.doc.overtime_details &&
            frm.doc.overtime_details.length
        ) {

            frm.add_custom_button(
                __("Create Additional Salaries"),
                () => {

                    frm.trigger(
                        "create_additional_salaries"
                    );

                },
                __("Actions")
            );
        }
    },


    // =========================================================================
    // Collect Overtime
    // =========================================================================

    collect_overtime(frm) {

        const required_fields = [
            "company",
            "apply_to",
            "payroll_period",
            "from_date",
            "to_date",
            "overtime_policy"
        ];

        for (const fieldname of required_fields) {

            if (!frm.doc[fieldname]) {

                frappe.msgprint({
                    title: __("Missing Required Field"),
                    message: __(
                        "{0} is mandatory."
                    ).replace(
                        "{0}",
                        frm.meta.get_label(fieldname)
                    ),
                    indicator: "red"
                });

                return;
            }
        }


        // ---------------------------------------------------------------------
        // Apply To Validation
        // ---------------------------------------------------------------------

        const apply_to_mapping = {
            "Employee": "employee",
            "Department": "department",
            "Designation": "designation",
            "Employee Group": "employee_group"
        };

        const selected_field =
            apply_to_mapping[frm.doc.apply_to];

        if (
            selected_field &&
            !frm.doc[selected_field]
        ) {

            frappe.msgprint({
                title: __("Missing Required Field"),
                message: __(
                    "{0} is mandatory."
                ).replace(
                    "{0}",
                    frm.meta.get_label(selected_field)
                ),
                indicator: "red"
            });

            return;
        }


        // ---------------------------------------------------------------------
        // Date Validation
        // ---------------------------------------------------------------------

        const from_date =
            frappe.datetime.str_to_obj(
                frm.doc.from_date
            );

        const to_date =
            frappe.datetime.str_to_obj(
                frm.doc.to_date
            );

        if (to_date < from_date) {

            frappe.msgprint({
                title: __("Invalid Period"),
                message: __(
                    "To Date cannot be earlier than From Date."
                ),
                indicator: "red"
            });

            return;
        }


        // ---------------------------------------------------------------------
        // Build Details
        // ---------------------------------------------------------------------

        const build_details = () => {

            frappe.call({

                method:
                    "ms_hrms.custom_hrms.doctype.overtime_calculation.overtime_calculation.build_details",

                args: {
                    name: frm.doc.name
                },

                freeze: true,

                freeze_message: __(
                    "Collecting Overtime Requests..."
                ),

                callback: function (r) {

                    if (
                        r.message &&
                        r.message.status === "success"
                    ) {

                        frappe.show_alert({
                            message: __(
                                "{0} Overtime Details collected."
                            ).replace(
                                "{0}",
                                r.message.count
                            ),
                            indicator: "green"
                        });

                        frm.reload_doc();

                        return;
                    }

                    if (
                        r.message &&
                        r.message.status === "empty"
                    ) {

                        frappe.show_alert({
                            message: __(
                                "No Overtime Details found."
                            ),
                            indicator: "orange"
                        });

                        frm.reload_doc();
                    }
                }
            });
        };


        // ---------------------------------------------------------------------
        // Save First
        // ---------------------------------------------------------------------

        if (frm.is_dirty()) {

            frm.save()
                .then(() => {

                    build_details();

                })
                .catch(error => {

                    console.error(
                        "Overtime Calculation Save Error:",
                        error
                    );
                });

        } else {

            build_details();
        }
    },


    // =========================================================================
    // Create Additional Salaries
    // =========================================================================

    create_additional_salaries(frm) {

        frappe.confirm(
            __(
                "Are you sure you want to create Additional Salary for each employee?"
            ),
            () => {

                frappe.call({

                    method:
                        "ms_hrms.custom_hrms.doctype.overtime_calculation.overtime_calculation.create_additional_salaries",

                    args: {
                        name: frm.doc.name
                    },

                    freeze: true,

                    freeze_message: __(
                        "Creating Additional Salaries..."
                    ),

                    callback: function (r) {

                        if (
                            r.message &&
                            r.message.names &&
                            r.message.names.length
                        ) {

                            frappe.show_alert({
                                message: __(
                                    "{0} Additional Salary documents created."
                                ).replace(
                                    "{0}",
                                    r.message.names.length
                                ),
                                indicator: "green"
                            });

                        }

                        if (r.message) {
                            frm.reload_doc();
                        }
                    }
                });
            }
        );
    }

});