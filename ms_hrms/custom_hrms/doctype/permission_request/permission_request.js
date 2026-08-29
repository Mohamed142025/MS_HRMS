// Copyright (c) 2026, Mohamed Sayed and contributors
// For license information, please see license.txt

frappe.ui.form.on("Permission Request", {
    onload(frm) {
        setup_employee_query(frm);

        if (frm.is_new()) {
            load_current_user_employee(frm);
        }
    },

    refresh(frm) {
        setup_employee_query(frm);

        if (frm.is_new() && !frm.doc.employee) {
            load_current_user_employee(frm);
        }
    },

    employee(frm) {
        if (frm.doc.employee) {
            fetch_employee_details(frm);
        }
    },

    from_time(frm) {
        calculate_duration(frm);
    },

    to_time(frm) {
        calculate_duration(frm);
    }
});

function setup_employee_query(frm) {
    frm.set_query("employee", function () {
        return {
            query:
                "ms_hrms.custom_hrms.doctype.permission_request.permission_request.get_employee_query"
        };
    });
}

function load_current_user_employee(frm) {
    frappe.call({
        method:
            "ms_hrms.custom_hrms.doctype.permission_request.permission_request.get_current_user_employee",
        freeze: true,
        freeze_message: __("Loading Employee...")
    }).then((response) => {
        const employee = response.message;

        if (!employee) {
            return;
        }

        frm.set_value("employee", employee.name);
        frm.set_value("employee_name", employee.employee_name);
        frm.set_value("department", employee.department);
        frm.set_value("designation", employee.designation);
    });
}

function fetch_employee_details(frm) {
    frappe.db.get_value(
        "Employee",
        frm.doc.employee,
        ["employee_name", "department", "designation"]
    ).then((response) => {
        const employee = response.message;

        if (!employee) {
            return;
        }

        frm.set_value("employee_name", employee.employee_name);
        frm.set_value("department", employee.department);
        frm.set_value("designation", employee.designation);
    });
}

function calculate_duration(frm) {
    if (!frm.doc.from_time || !frm.doc.to_time) {
        return;
    }

    const from_seconds = time_to_seconds(frm.doc.from_time);
    const to_seconds = time_to_seconds(frm.doc.to_time);

    frm.set_value(
        "duration",
        to_seconds > from_seconds ? to_seconds - from_seconds : 0
    );
}

function time_to_seconds(time) {
    const parts = time.split(":");
    const hours = parseInt(parts[0], 10) || 0;
    const minutes = parseInt(parts[1], 10) || 0;
    const seconds = parseInt(parts[2], 10) || 0;

    return hours * 3600 + minutes * 60 + seconds;
}
