// Copyright (c) 2026, Mohamed Sayed and contributors
// For license information, please see license.txt

frappe.ui.form.on("Overtime Policy", {

    // =========================================================================
    // SETUP
    // =========================================================================

    setup(frm) {
        frm.trigger("setup_link_filters");
    },


    // =========================================================================
    // REFRESH
    // =========================================================================

    refresh(frm) {

        frm.trigger("setup_link_filters");
        frm.trigger("setup_applicability");
        frm.trigger("setup_calculation_basis");
        frm.trigger("setup_rounding");

        if (frm.is_new()) {
            frm.trigger("set_default_values");
        }
    },


    // =========================================================================
    // DEFAULT VALUES
    // =========================================================================

    set_default_values(frm) {

        if (!frm.doc.status) {
            frm.set_value("status", "Draft");
        }

        if (!frm.doc.apply_to) {
            frm.set_value("apply_to", "All Employees");
        }

        if (
            frm.doc.priority === undefined ||
            frm.doc.priority === null
        ) {
            frm.set_value("priority", 10);
        }

        if (
            frm.doc.allow_fractional_hours === undefined ||
            frm.doc.allow_fractional_hours === null
        ) {
            frm.set_value("allow_fractional_hours", 1);
        }

        if (!frm.doc.calculation_basis) {
            frm.set_value(
                "calculation_basis",
                "Basic Salary"
            );
        }
    },


    // =========================================================================
    // LINK FILTERS
    // =========================================================================

    setup_link_filters(frm) {

        // ---------------------------------------------------------------------
        // Company
        // ---------------------------------------------------------------------

        frm.set_query("company", () => {
            return {};
        });


        // ---------------------------------------------------------------------
        // Department
        // ---------------------------------------------------------------------

        frm.set_query("department", () => {

            const filters = {};

            if (frm.doc.company) {
                filters.company = frm.doc.company;
            }

            return {
                filters: filters
            };
        });


        // ---------------------------------------------------------------------
        // Designation
        // ---------------------------------------------------------------------

        frm.set_query("designation", () => {
            return {};
        });


        // ---------------------------------------------------------------------
        // Employee Group
        // ---------------------------------------------------------------------

        frm.set_query("employee_group", () => {
            return {};
        });


        // ---------------------------------------------------------------------
        // Employee
        // ---------------------------------------------------------------------

        frm.set_query("employee", () => {

            const filters = {};

            if (frm.doc.company) {
                filters.company = frm.doc.company;
            }

            if (frm.doc.department) {
                filters.department = frm.doc.department;
            }

            if (frm.doc.designation) {
                filters.designation = frm.doc.designation;
            }

            return {
                filters: filters
            };
        });


        // ---------------------------------------------------------------------
        // Calculation Salary Component
        // ---------------------------------------------------------------------

        if (frm.fields_dict.calculation_salary_component) {

            frm.set_query(
                "calculation_salary_component",
                () => {

                    return {
                        filters: {
                            type: "Earning"
                        }
                    };
                }
            );
        }


        // ---------------------------------------------------------------------
        // Overtime Salary Component
        // ---------------------------------------------------------------------

        if (frm.fields_dict.salary_component) {

            frm.set_query(
                "salary_component",
                () => {

                    return {
                        filters: {
                            type: "Earning"
                        }
                    };
                }
            );
        }
    },


    // =========================================================================
    // COMPANY
    // =========================================================================

    company(frm) {

        frm.trigger("setup_link_filters");

        /*
         * Do not clear salary_component automatically.
         *
         * It is the Overtime output component and is independent
         * from the calculation basis.
         */

        if (frm.doc.apply_to === "Employee") {
            frm.set_value("employee", null);
        }

        if (frm.doc.apply_to === "Department") {
            frm.set_value("department", null);
        }
    },


    // =========================================================================
    // APPLY TO
    // =========================================================================

    apply_to(frm) {

        const fields_by_type = {

            "All Employees": [
                "department",
                "designation",
                "employee_group",
                "employee"
            ],

            "Department": [
                "designation",
                "employee_group",
                "employee"
            ],

            "Designation": [
                "department",
                "employee_group",
                "employee"
            ],

            "Employee Group": [
                "department",
                "designation",
                "employee"
            ],

            "Employee": [
                "department",
                "designation",
                "employee_group"
            ]
        };

        const fields_to_clear =
            fields_by_type[frm.doc.apply_to] || [];

        fields_to_clear.forEach(fieldname => {

            if (frm.doc[fieldname]) {
                frm.set_value(fieldname, null);
            }
        });

        frm.trigger("setup_applicability");
        frm.trigger("setup_link_filters");
    },


    // =========================================================================
    // APPLICABILITY UI
    // =========================================================================

    setup_applicability(frm) {

        const fields = [
            "department",
            "designation",
            "employee_group",
            "employee"
        ];

        fields.forEach(fieldname => {

            if (frm.fields_dict[fieldname]) {
                frm.toggle_display(
                    fieldname,
                    false
                );
            }
        });


        switch (frm.doc.apply_to) {

            case "Department":

                frm.toggle_display(
                    "department",
                    true
                );

                break;


            case "Designation":

                frm.toggle_display(
                    "designation",
                    true
                );

                break;


            case "Employee Group":

                frm.toggle_display(
                    "employee_group",
                    true
                );

                break;


            case "Employee":

                frm.toggle_display(
                    "employee",
                    true
                );

                break;
        }
    },


    // =========================================================================
    // CALCULATION BASIS
    // =========================================================================

    calculation_basis(frm) {

        frm.trigger(
            "setup_calculation_basis"
        );

        /*
         * IMPORTANT
         * ---------------------------------------------------------------------
         *
         * We DO NOT clear salary_component.
         *
         * salary_component = final Overtime Salary Component.
         *
         * It is independent from calculation_basis.
         *
         * calculation_salary_component = source used to calculate
         * the hourly rate and is only relevant for:
         *
         *     Calculation Basis = Salary Component
         */


        /*
         * Fixed Hourly Rate is only relevant for
         * Fixed Hourly Rate basis.
         */

        if (
            frm.doc.calculation_basis !==
            "Fixed Hourly Rate"
        ) {

            if (frm.doc.fixed_hourly_rate) {

                frm.set_value(
                    "fixed_hourly_rate",
                    null
                );
            }
        }


        /*
         * Calculation Salary Component is only relevant
         * when Calculation Basis = Salary Component.
         *
         * We intentionally do NOT clear it.
         *
         * This allows the user to switch:
         *
         * Basic Salary
         *      ↓
         * Salary Component
         *
         * and keep the previously selected source component.
         */
    },


    // =========================================================================
    // CALCULATION BASIS UI
    // =========================================================================

    setup_calculation_basis(frm) {

        const basis =
            frm.doc.calculation_basis;


        // ---------------------------------------------------------------------
        // Calculation Salary Component
        // ---------------------------------------------------------------------

        const show_calculation_component =
            basis === "Salary Component";


        if (
            frm.fields_dict.calculation_salary_component
        ) {

            frm.toggle_display(
                "calculation_salary_component",
                show_calculation_component
            );

            frm.set_df_property(
                "calculation_salary_component",
                "reqd",
                show_calculation_component ? 1 : 0
            );
        }


        // ---------------------------------------------------------------------
        // Fixed Hourly Rate
        // ---------------------------------------------------------------------

        const show_fixed_hourly_rate =
            basis === "Fixed Hourly Rate";


        if (frm.fields_dict.fixed_hourly_rate) {

            frm.toggle_display(
                "fixed_hourly_rate",
                show_fixed_hourly_rate
            );

            frm.set_df_property(
                "fixed_hourly_rate",
                "reqd",
                show_fixed_hourly_rate ? 1 : 0
            );
        }


        // ---------------------------------------------------------------------
        // Salary Component
        // ---------------------------------------------------------------------
        //
        // IMPORTANT:
        //
        // This is the FINAL overtime salary component.
        //
        // It must ALWAYS remain visible and required.
        //

        if (frm.fields_dict.salary_component) {

            frm.toggle_display(
                "salary_component",
                true
            );

            frm.set_df_property(
                "salary_component",
                "reqd",
                1
            );

            frm.set_df_property(
                "salary_component",
                "read_only",
                0
            );
        }
    },


    // =========================================================================
    // CALCULATION SALARY COMPONENT
    // =========================================================================

    calculation_salary_component(frm) {

        if (
            frm.doc.calculation_salary_component &&
            frm.doc.calculation_basis !==
            "Salary Component"
        ) {

            frappe.msgprint({
                title: __("Calculation Salary Component"),
                message: __(
                    "This component will only be used when Calculation Basis is Salary Component."
                ),
                indicator: "orange"
            });
        }
    },


    // =========================================================================
    // OVERTIME SALARY COMPONENT
    // =========================================================================

    salary_component(frm) {

        /*
         * This component is the destination/output component
         * for the calculated overtime amount.
         */

        if (!frm.doc.salary_component) {
            return;
        }

        /*
         * No dependency on calculation_basis.
         *
         * It remains valid for:
         *
         * Basic Salary
         * Gross Salary
         * Salary Component
         * Fixed Hourly Rate
         */
    },


    // =========================================================================
    // FIXED HOURLY RATE
    // =========================================================================

    fixed_hourly_rate(frm) {

        if (
            frm.doc.calculation_basis ===
            "Fixed Hourly Rate"
        ) {

            if (
                frm.doc.fixed_hourly_rate &&
                frm.doc.fixed_hourly_rate <= 0
            ) {

                frappe.msgprint({
                    title: __("Invalid Hourly Rate"),
                    message: __(
                        "Fixed Hourly Rate must be greater than zero."
                    ),
                    indicator: "red"
                });
            }
        }
    },


    // =========================================================================
    // ROUNDING
    // =========================================================================

    enable_rounding(frm) {

        frm.trigger("setup_rounding");

        if (!frm.doc.enable_rounding) {

            frm.set_value(
                "rounding_rule",
                null
            );

            frm.set_value(
                "rounding_interval",
                null
            );
        }
    },


    // =========================================================================
    // ROUNDING UI
    // =========================================================================

    setup_rounding(frm) {

        const enabled =
            Boolean(frm.doc.enable_rounding);


        if (frm.fields_dict.rounding_rule) {

            frm.toggle_display(
                "rounding_rule",
                enabled
            );

            frm.set_df_property(
                "rounding_rule",
                "reqd",
                enabled ? 1 : 0
            );
        }


        if (frm.fields_dict.rounding_interval) {

            frm.toggle_display(
                "rounding_interval",
                enabled
            );

            frm.set_df_property(
                "rounding_interval",
                "reqd",
                enabled ? 1 : 0
            );
        }
    },


    // =========================================================================
    // VALIDATION
    // =========================================================================

    validate(frm) {

        // ---------------------------------------------------------------------
        // Effective Dates
        // ---------------------------------------------------------------------

        if (
            frm.doc.effective_from &&
            frm.doc.effective_to &&
            frm.doc.effective_to <
            frm.doc.effective_from
        ) {

            frappe.throw({
                title: __("Invalid Effective Dates"),
                message: __(
                    "Effective To cannot be earlier than Effective From."
                )
            });
        }


        // ---------------------------------------------------------------------
        // Priority
        // ---------------------------------------------------------------------

        if (
            frm.doc.priority !== undefined &&
            frm.doc.priority !== null &&
            frm.doc.priority < 0
        ) {

            frappe.throw({
                title: __("Invalid Priority"),
                message: __(
                    "Priority cannot be negative."
                )
            });
        }


        // ---------------------------------------------------------------------
        // Minimum Overtime
        // ---------------------------------------------------------------------

        if (
            frm.doc.minimum_overtime !== undefined &&
            frm.doc.minimum_overtime !== null &&
            frm.doc.minimum_overtime < 0
        ) {

            frappe.throw({
                title: __("Invalid Minimum Overtime"),
                message: __(
                    "Minimum Overtime cannot be negative."
                )
            });
        }


        // ---------------------------------------------------------------------
        // Maximum Overtime
        // ---------------------------------------------------------------------

        if (
            frm.doc.maximum_overtime !== undefined &&
            frm.doc.maximum_overtime !== null &&
            frm.doc.maximum_overtime < 0
        ) {

            frappe.throw({
                title: __("Invalid Maximum Overtime"),
                message: __(
                    "Maximum Overtime cannot be negative."
                )
            });
        }


        // ---------------------------------------------------------------------
        // Overtime Range
        // ---------------------------------------------------------------------

        if (
            frm.doc.minimum_overtime &&
            frm.doc.maximum_overtime &&
            frm.doc.maximum_overtime <
            frm.doc.minimum_overtime
        ) {

            frappe.throw({
                title: __("Invalid Overtime Range"),
                message: __(
                    "Maximum Overtime cannot be less than Minimum Overtime."
                )
            });
        }


        // ---------------------------------------------------------------------
        // Overtime Salary Component
        // ---------------------------------------------------------------------
        //
        // This is ALWAYS required.
        //

        if (!frm.doc.salary_component) {

            frappe.throw({
                title: __("Missing Salary Component"),
                message: __(
                    "Please configure the Salary Component used to record the Overtime amount."
                )
            });
        }


        // ---------------------------------------------------------------------
        // Calculation Salary Component
        // ---------------------------------------------------------------------
        //
        // Required ONLY when:
        //
        // Calculation Basis = Salary Component
        //

        if (
            frm.doc.calculation_basis ===
            "Salary Component"
        ) {

            if (
                !frm.doc.calculation_salary_component
            ) {

                frappe.throw({
                    title: __(
                        "Missing Calculation Salary Component"
                    ),
                    message: __(
                        "Please select the Salary Component used as the calculation source."
                    )
                });
            }
        }


        // ---------------------------------------------------------------------
        // Fixed Hourly Rate
        // ---------------------------------------------------------------------

        if (
            frm.doc.calculation_basis ===
            "Fixed Hourly Rate"
        ) {

            if (
                !frm.doc.fixed_hourly_rate ||
                frm.doc.fixed_hourly_rate <= 0
            ) {

                frappe.throw({
                    title: __("Invalid Hourly Rate"),
                    message: __(
                        "Fixed Hourly Rate must be greater than zero."
                    )
                });
            }
        }


        // ---------------------------------------------------------------------
        // Rounding
        // ---------------------------------------------------------------------

        if (frm.doc.enable_rounding) {

            if (!frm.doc.rounding_rule) {

                frappe.throw({
                    title: __("Missing Rounding Rule"),
                    message: __(
                        "Please select a Rounding Rule."
                    )
                });
            }


            if (
                !frm.doc.rounding_interval ||
                frm.doc.rounding_interval <= 0
            ) {

                frappe.throw({
                    title: __("Invalid Rounding Interval"),
                    message: __(
                        "Rounding Interval must be greater than zero."
                    )
                });
            }
        }
    }
});