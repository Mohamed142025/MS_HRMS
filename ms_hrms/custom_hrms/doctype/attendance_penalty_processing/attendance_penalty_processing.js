frappe.ui.form.on("Attendance Penalty Processing", {
    refresh(frm) {
        frm.set_query("policy", () => ({
            filters: { enabled: 1 },
        }));
        frm.toggle_enable("get_attendance", !["Submitted", "Cancelled"].includes(frm.doc.status));
        frm.trigger("render_additional_salary_links");
    },
    render_additional_salary_links(frm) {
        const wrapper = frm.get_field("additional_salary_links").$wrapper;
        wrapper.empty();

        let names = [];
        try {
            names = JSON.parse(frm.doc.additional_salary_references || "[]");
        } catch {
            names = [];
        }

        if (!names.length) return;

        const links = names
            .map((name) => `<a href="${frappe.utils.get_form_link("Additional Salary", name)}">${frappe.utils.escape_html(name)}</a>`)
            .join("<br>");

        wrapper.html(links);
    },
    get_attendance(frm) {
        const run = () => {
            frm.call("get_attendance").then((response) => {
                if (!response.message) return;
                frappe.model.sync(response.message);
                frm.refresh();
                frm.dirty();
            });
        };
        if (frm.is_new()) {
            frm.save().then(run);
        } else {
            run();
        }
    },
    apply_on(frm) {
        if (frm.doc.apply_on !== "Department") frm.set_value("department", null);
        if (frm.doc.apply_on !== "Employee") frm.set_value("employee", null);
    },
    payroll_period(frm) {
        if (!frm.doc.payroll_period) return;
        frappe.db.get_value("Payroll Period", frm.doc.payroll_period, ["start_date", "end_date"]).then((response) => {
            const period = response.message;
            if (period) {
                frm.set_value("from_date", period.start_date);
                frm.set_value("to_date", period.end_date);
            }
        });
    },
    from_date(frm) {
        if (!frm.doc.to_date) frm.set_value("to_date", frm.doc.from_date);
    },
});
