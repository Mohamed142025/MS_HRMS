// Copyright (c) 2026, Mohamed Sayed and contributors
// For license information, please see license.txt

frappe.ui.form.on("Permission Policy", {
    refresh(frm) {
        toggle_scope_fields(frm);
    },

    applies_to(frm) {
        clear_unused_scope_fields(frm);
        toggle_scope_fields(frm);
    }
});

function get_scope_field(applies_to) {
    return {
        Department: "department",
        Designation: "designation",
        "Employee Grade": "employee_grade",
        Employee: "employee"
    }[applies_to];
}

function toggle_scope_fields(frm) {
    const selected_field = get_scope_field(frm.doc.applies_to);

    ["department", "designation", "employee_grade", "employee"].forEach(
        (fieldname) => frm.toggle_display(fieldname, fieldname === selected_field)
    );
}

function clear_unused_scope_fields(frm) {
    const selected_field = get_scope_field(frm.doc.applies_to);

    ["department", "designation", "employee_grade", "employee"].forEach(
        (fieldname) => {
            if (fieldname !== selected_field && frm.doc[fieldname]) {
                frm.set_value(fieldname, null);
            }
        }
    );
}
